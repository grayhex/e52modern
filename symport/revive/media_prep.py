"""Media to Nokia (#41): prepare video, music and pictures for a chosen S60 model and copy them safely.

Everything runs on the server in a bounded, sandboxed process (FFmpeg through the resource-limiting
worker; Pillow for pictures) with size, duration, pixel and time limits, a small queue and a
time-to-live for temporary files. Presets are *theoretical* defaults for the model's screen and
generic S60 3rd/5th Edition capability: none has been verified on hardware and each says so.
The three outcomes are kept apart: ``exported`` (a file you can download), ``transferred`` (copied
through the Recovery Safety Net, read back, never overwriting) and ``played-on-device`` (only what you
report after trying it).
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from symport.catalog.service import now
from symport.phone.registry import registry

MAX_INPUT = 48 * 1024**2
MAX_OUTPUT = 48 * 1024**2
MAX_DURATION = 600
MAX_PIXELS = 40_000_000
TTL = 3600
MAX_JOBS = 6
QUEUE_LIMIT = 2
VIDEO_TIMEOUT = 240
FORMATS = 'mp3,wav,aac,mov,mp4,m4a,3gp,3g2,mj2,flac,ogg,matroska,webm,asf,aiff,avi,mpegts,flv'
TARGETS = ('nokia-e52', 'nokia-e72', 'nokia-n95', 'nokia-n95-8gb', 'nokia-n97-mini')
OUTCOMES = ('exported', 'transferred', 'played-on-device')
THEORETICAL = {'hardware': 'not-tested', 'basis': 'theoretical: generic S60 capability and the model screen, not measured on this model'}

VIDEO = {
    'mp4-qvga-h264': {'title': {'en': 'MP4 · H.264 baseline · 320×240 · AAC', 'ru': 'MP4 · H.264 baseline · 320×240 · AAC'}, 'ext': 'mp4', 'fmt': 'mp4',
                      'w': 320, 'h': 240, 'fps': 25, 'vbps': 384_000, 'abps': 96_000, 'ar': 44100, 'ac': 2,
                      'v': ['-c:v', 'libx264', '-profile:v', 'baseline', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-b:v', '384k', '-maxrate', '448k', '-bufsize', '768k'],
                      'a': ['-c:a', 'aac', '-b:a', '96k', '-ar', '44100', '-ac', '2']},
    '3gp-qcif-mpeg4': {'title': {'en': '3GP · MPEG-4 · 176×144 · AAC', 'ru': '3GP · MPEG-4 · 176×144 · AAC'}, 'ext': '3gp', 'fmt': '3gp',
                       'w': 176, 'h': 144, 'fps': 15, 'vbps': 128_000, 'abps': 64_000, 'ar': 22050, 'ac': 1,
                       'v': ['-c:v', 'mpeg4', '-b:v', '128k', '-pix_fmt', 'yuv420p'],
                       'a': ['-c:a', 'aac', '-b:a', '64k', '-ar', '22050', '-ac', '1']},
}
AUDIO = {
    'mp3-128': {'title': {'en': 'MP3 · 128 kbps · stereo · 44.1 kHz', 'ru': 'MP3 · 128 кбит/с · стерео · 44,1 кГц'}, 'ext': 'mp3', 'fmt': 'mp3', 'abps': 128_000,
                'a': ['-c:a', 'libmp3lame', '-b:a', '128k', '-ar', '44100', '-ac', '2', '-id3v2_version', '3']},
    'mp3-64-mono': {'title': {'en': 'MP3 · 64 kbps · mono · 32 kHz (small)', 'ru': 'MP3 · 64 кбит/с · моно · 32 кГц (малый размер)'}, 'ext': 'mp3', 'fmt': 'mp3', 'abps': 64_000,
                    'a': ['-c:a', 'libmp3lame', '-b:a', '64k', '-ar', '32000', '-ac', '1', '-id3v2_version', '3']},
    'aac-96': {'title': {'en': 'AAC (M4A) · 96 kbps · stereo', 'ru': 'AAC (M4A) · 96 кбит/с · стерео'}, 'ext': 'm4a', 'fmt': 'ipod', 'abps': 96_000,
               'a': ['-c:a', 'aac', '-b:a', '96k', '-ar', '44100', '-ac', '2']},
}
IMAGE = {
    'wallpaper-jpeg': {'title': {'en': 'Wallpaper · JPEG · cropped to the screen', 'ru': 'Обои · JPEG · обрезка под экран'}, 'ext': 'jpg', 'mode': 'cover', 'fmt': 'JPEG'},
    'photo-fit-jpeg': {'title': {'en': 'Photo · JPEG · fitted inside the screen', 'ru': 'Фото · JPEG · вписано в экран'}, 'ext': 'jpg', 'mode': 'fit', 'fmt': 'JPEG'},
    'photo-fit-png': {'title': {'en': 'Photo · PNG · fitted inside the screen', 'ru': 'Фото · PNG · вписано в экран'}, 'ext': 'png', 'mode': 'fit', 'fmt': 'PNG'},
}
PRESETS = {'video': VIDEO, 'audio': AUDIO, 'image': IMAGE}
NAME = re.compile(r'[^A-Za-z0-9._-]+')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_name(name: str, ext: str) -> str:
    stem = NAME.sub('_', Path(str(name)).stem).strip('._-')[:40] or 'media'
    return f'{stem}.{ext}'


class MediaPrep:
    def __init__(self, service):
        self.service = service
        self.root = service.root / 'media-prep'
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        self.sources: dict[str, dict] = {}
        self.queue: list[str] = []
        self.runner: threading.Thread | None = None
        self.timeout = VIDEO_TIMEOUT
        service.scenarios['media'] = self._plan_scenario
        service.safety.gates['media'] = self._gate

    # ---- housekeeping ---------------------------------------------------------------------------------
    def cleanup(self):
        with self.lock:
            for key in [k for k, v in {**self.sources, **self.jobs}.items() if v['expires'] < time.monotonic() and v.get('state') not in ('running',)]:
                shutil.rmtree(self.root / key, ignore_errors=True)
                self.sources.pop(key, None)
                self.jobs.pop(key, None)
            if self.root.is_dir():
                for path in self.root.iterdir():
                    if path.is_dir() and path.name not in self.sources and path.name not in self.jobs:
                        shutil.rmtree(path, ignore_errors=True)

    def _folder(self, key) -> Path:
        folder = self.root / key
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        return folder

    # ---- sandboxed tools ---------------------------------------------------------------------------------
    def run(self, tool: str, args: list[str], timeout: float) -> bytes:
        exe = shutil.which(tool)
        if not exe:
            raise ValueError(f'{tool} is unavailable; use the Docker image with FFmpeg.')
        if sys.platform != 'linux':
            raise ValueError('Media preparation requires the Linux backend.')
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as log:
            try:
                result = subprocess.run([sys.executable, '-m', 'symport.audio.worker', exe, *args], stdin=subprocess.DEVNULL, stdout=out, stderr=log,
                                        timeout=timeout, check=False, env={**os.environ, 'LC_ALL': 'C', 'OMP_NUM_THREADS': '2'})
            except subprocess.TimeoutExpired as exc:
                raise ValueError('Processing timed out: choose a shorter file or a lighter preset.') from exc
            log.seek(0, 2)
            out.seek(0, 2)
            if result.returncode or log.tell() > 4 * 1024**2 or out.tell() > 1024**2:
                raise ValueError('The file could not be decoded or converted. Choose a supported audio, video or picture file.')
            out.seek(0)
            return out.read()

    def probe_av(self, path: Path) -> dict:
        raw = self.run('ffprobe', ['-v', 'error', '-max_alloc', '67108864', '-protocol_whitelist', 'file', '-format_whitelist', FORMATS,
                                   '-show_entries', 'format=duration,format_name:stream=codec_type,codec_name,width,height,sample_rate,channels',
                                   '-of', 'json', str(path)], 20)
        meta = json.loads(raw)
        streams = meta.get('streams', [])
        video = next((s for s in streams if s.get('codec_type') == 'video'), None)
        audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        try:
            duration = float(meta.get('format', {}).get('duration', 'nan'))
        except ValueError:
            duration = math.nan
        if not (video or audio) or not math.isfinite(duration) or not 0.1 <= duration <= MAX_DURATION:
            raise ValueError('Choose a file with audio or video lasting 0.1 second to 10 minutes.')
        kind = 'video' if video else 'audio'
        return {'kind': kind, 'duration': duration, 'container': meta['format'].get('format_name'),
                'video': {k: video.get(k) for k in ('codec_name', 'width', 'height')} if video else None,
                'audio': {k: audio.get(k) for k in ('codec_name', 'sample_rate', 'channels')} if audio else None}

    def probe_image(self, raw: bytes) -> dict | None:
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover
            return None
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('The picture is larger than 40 megapixels.')
                return {'kind': 'image', 'width': image.width, 'height': image.height, 'format': image.format}
        except ValueError:
            raise
        except Exception:  # noqa: BLE001 - any decoder failure means "not a picture"
            return None

    # ---- actions ------------------------------------------------------------------------------------------
    def presets(self, data):
        model = data.get('model')
        reg = registry().get(model)
        if model not in TARGETS or not reg:
            raise ValueError('Choose a supported phone model')
        screen = reg.get('screen') or {}
        out = {}
        for kind, table in PRESETS.items():
            out[kind] = [{'id': k, 'title': v['title'], **THEORETICAL, 'ext': v['ext']} for k, v in table.items()]
        return {'model': model, 'screen': screen, 'screen_modes': reg.get('screen_modes') or [], 'presets': out,
                'statement': 'Every preset is theoretical for this model: none has been verified on hardware.'}

    def upload(self, data):
        self.cleanup()
        try:
            raw = base64.b64decode(data.get('content', ''), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('Damaged upload: not valid base64') from exc
        if not raw or len(raw) > MAX_INPUT:
            raise ValueError('Choose a file between 1 byte and 48 MiB.')
        with self.lock:
            if len(self.sources) + len(self.jobs) >= MAX_JOBS:
                raise ValueError('Too many temporary files: discard some first.')
        key = secrets.token_hex(16)
        folder = self._folder(key)
        try:
            image = self.probe_image(raw)
            source = folder / 'input.bin'
            source.write_bytes(raw)
            source.chmod(0o600)
            meta = image or self.probe_av(source)
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        info = {'id': key, 'name': str(data.get('name') or 'media')[:120], 'size': len(raw), 'sha256': sha(raw), **meta}
        with self.lock:
            self.sources[key] = {**info, 'expires': time.monotonic() + TTL}
        return info

    def _source(self, key):
        item = self.sources.get(key) if isinstance(key, str) else None
        if not item or item['expires'] < time.monotonic():
            raise ValueError('The source expired or is unknown; upload it again.')
        return item

    def estimate(self, source, preset_id, kind) -> int:
        p = PRESETS[kind][preset_id]
        if kind == 'video':
            return int((p['vbps'] + p['abps']) * source['duration'] / 8)
        if kind == 'audio':
            return int(p['abps'] * source['duration'] / 8)
        return 0

    def convert(self, data):
        self.cleanup()
        source = self._source(data.get('source'))
        model, preset_id = data.get('model'), data.get('preset')
        reg = registry().get(model)
        if model not in TARGETS or not reg:
            raise ValueError('Choose a supported phone model')
        kind = source['kind']
        if preset_id not in PRESETS[kind]:
            raise ValueError(f'This preset does not fit a {kind} source')
        rotate = data.get('rotate', 0)
        if rotate not in (0, 90, 180, 270):
            raise ValueError('Rotation must be 0, 90, 180 or 270')
        with self.lock:
            if len(self.queue) >= QUEUE_LIMIT or len(self.sources) + len(self.jobs) >= MAX_JOBS + 2:
                raise ValueError('The conversion queue is full; try again shortly.')
            key = secrets.token_hex(16)
            self.jobs[key] = {'id': key, 'state': 'queued', 'stage': 'queued', 'source': source['id'], 'model': model, 'preset': preset_id, 'kind': kind,
                              'rotate': rotate, 'estimate': self.estimate(source, preset_id, kind), 'created': now(), 'expires': time.monotonic() + TTL,
                              'name': source['name'], 'outcomes': {'exported': False, 'transferred': False, 'played-on-device': 'not-tested'}}
            self.sources[source['id']]['expires'] = max(self.sources[source['id']]['expires'], time.monotonic() + TTL)
            self.queue.append(key)
            if not self.runner or not self.runner.is_alive():
                self.runner = threading.Thread(target=self._work, daemon=True, name='media-prep')
                self.runner.start()
        return self.view(key)

    def _work(self):
        while True:
            with self.lock:
                if not self.queue:
                    return
                key = self.queue.pop(0)
                job = self.jobs.get(key)
                if not job:
                    continue
                job.update(state='running', stage='converting')
            try:
                self._convert(job)
                job.update(state='done', stage='ready')
            except Exception as exc:  # noqa: BLE001
                job.update(state='failed', stage='failed', error=str(exc)[:300])

    def _convert(self, job):
        source = self.sources[job['source']]
        folder = self._folder(job['id'])
        src = self.root / source['id'] / 'input.bin'
        kind, preset = job['kind'], PRESETS[job['kind']][job['preset']]
        out = folder / ('output.' + preset['ext'])
        if kind == 'image':
            self._convert_image(src, out, preset, job)
        else:
            base = ['-hide_banner', '-loglevel', 'error', '-nostdin', '-n', '-max_alloc', '67108864', '-threads', '2', '-protocol_whitelist', 'file',
                    '-format_whitelist', FORMATS, '-i', str(src), '-map_metadata', '-1', '-sn', '-dn']
            if kind == 'video':
                rot = {90: 'transpose=1', 180: 'hflip,vflip', 270: 'transpose=2', 0: ''}[job['rotate']]
                w, h = preset['w'], preset['h']
                scale = f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={preset["fps"]}'
                args = [*base, '-map', '0:v:0', '-map', '0:a:0?', '-vf', ','.join(x for x in (rot, scale) if x), *preset['v'], *preset['a'], '-f', preset['fmt'], str(out)]
            else:
                args = [*base, '-map', '0:a:0', '-vn', *preset['a'], '-f', preset['fmt'], str(out)]
            self.run('ffmpeg', args, self.timeout)
        if not out.is_file() or out.stat().st_size == 0:
            raise ValueError('The conversion produced no output.')
        if out.stat().st_size > MAX_OUTPUT:
            out.unlink()
            raise ValueError('The result is larger than 48 MiB; use a lighter preset or a shorter file.')
        raw = out.read_bytes()
        job['output'] = {'name': safe_name(job['name'], preset['ext']), 'size': len(raw), 'sha256': sha(raw), 'ext': preset['ext'], 'path': str(out)}
        job['preview'] = self._preview(src, kind, job['rotate'])

    def _convert_image(self, src, out, preset, job):
        from PIL import Image, ImageOps
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        reg = registry()[job['model']]
        screen = reg.get('screen') or {'width': 240, 'height': 320}
        with Image.open(src) as image:
            image = ImageOps.exif_transpose(image)
            if job['rotate']:
                image = image.rotate(-job['rotate'], expand=True)
            image = image.convert('RGB')
            size = (screen['width'], screen['height'])
            if preset['mode'] == 'cover':
                image = ImageOps.fit(image, size, method=Image.LANCZOS)
            else:
                image.thumbnail(size, Image.LANCZOS)
            image.save(out, preset['fmt'], **({'quality': 85, 'optimize': True} if preset['fmt'] == 'JPEG' else {}))

    def _preview(self, src: Path, kind: str, rotate: int) -> str | None:
        try:
            if kind == 'audio':
                return None
            if kind == 'image':
                from PIL import Image
                with Image.open(src) as image:
                    image.thumbnail((160, 160))
                    buf = io.BytesIO()
                    image.convert('RGB').save(buf, 'JPEG', quality=70)
                    return base64.b64encode(buf.getvalue()).decode()
            frame = self.run('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-nostdin', '-protocol_whitelist', 'file', '-i', str(src), '-frames:v', '1',
                                        '-vf', 'scale=160:-2', '-f', 'mjpeg', '-'], 30)
            return base64.b64encode(frame).decode()
        except ValueError:
            return None

    def view(self, key) -> dict:
        job = self.jobs.get(key) if isinstance(key, str) else None
        if not job or job['expires'] < time.monotonic():
            raise ValueError('The job expired or is unknown.')
        out = job.get('output')
        pos = self.queue.index(key) + 1 if key in self.queue else 0
        return {'id': key, 'state': job['state'], 'stage': job['stage'], 'queue_position': pos, 'model': job['model'], 'preset': job['preset'],
                'kind': job['kind'], 'estimate_bytes': job['estimate'], 'error': job.get('error'),
                'output': {k: out[k] for k in ('name', 'size', 'sha256', 'ext')} if out else None, 'preview': job.get('preview'),
                'outcomes': job['outcomes'], **THEORETICAL}

    def export(self, data):
        job = self.jobs.get(data.get('job'))
        self.view(data.get('job'))
        if job['state'] != 'done':
            raise ValueError('The conversion is not finished.')
        raw = Path(job['output']['path']).read_bytes()
        if sha(raw) != job['output']['sha256']:
            raise ValueError('The result changed on disk; convert again.')
        job['outcomes']['exported'] = True
        report = {'schema': 'symport.media-prep/1', 'created': now(), 'model': job['model'], 'preset': job['preset'], 'kind': job['kind'],
                  'source': {k: self.sources.get(job['source'], {}).get(k) for k in ('size', 'sha256')},
                  'output': {k: job['output'][k] for k in ('name', 'size', 'sha256')}, 'hardware': 'not-tested', 'outcomes': job['outcomes'],
                  'statement': 'Exported is not transferred and not played on a device.'}
        return {'name': job['output']['name'], 'content': base64.b64encode(raw).decode(), 'sha256': job['output']['sha256'],
                'report_name': job['output']['name'] + '.report.json',
                'report': base64.b64encode(json.dumps(report, indent=2).encode()).decode()}

    def discard(self, data):
        key = data.get('id')
        with self.lock:
            for table in (self.sources, self.jobs):
                if key in table:
                    if table is self.jobs and table[key]['state'] == 'running':
                        raise ValueError('The job is running.')
                    table.pop(key)
                    shutil.rmtree(self.root / str(key), ignore_errors=True)
                    if key in self.queue:
                        self.queue.remove(key)
                    return {'discarded': key}
        raise ValueError('Unknown item')

    def record(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm that this is what you observed on the phone')
        job = self.jobs.get(data.get('job'))
        self.view(data.get('job'))
        if data.get('result') not in ('pass', 'fail', 'not-tested'):
            raise ValueError('Invalid result')
        job['outcomes']['played-on-device'] = data['result']
        row, facts = self.service._need_device(data)
        saved = self.service._load('observations', facts['key'])
        saved.setdefault('media', {})[job['id'][:12]] = {'preset': job['preset'], 'model': job['model'], 'result': data['result'], 'at': now(), 'source': 'manual'}
        self.service._save('observations', facts['key'], saved)
        return {'job': job['id'], 'outcomes': job['outcomes']}

    # ---- Safety Net scenario --------------------------------------------------------------------------------
    def _gate(self, row, facts, plan):
        from . import checks as C
        ev = C.evaluate(dict(facts, required_free=plan['dry_run']['bytes']), 'network-certs')
        unmet = [{'code': 'gate-' + c, 'text': ev[c]['reason']} for c in ('connection', 'files', 'transfer') if ev[c]['status'] not in ('ready',)]
        free = facts['observed'].get('free')
        if isinstance(free, int) and free < plan['dry_run']['bytes'] + 1024 * 1024:
            unmet.append({'code': 'gate-space', 'text': {'en': 'Not enough free space on the phone for this file.', 'ru': 'На телефоне недостаточно места для этого файла.'}})
        prof = facts['identity']['profile']
        if prof and plan.get('media_model') and prof['id'] != plan['media_model']:
            unmet.append({'code': 'gate-preset-for-other-model', 'text': {'en': 'This file was prepared for another model.', 'ru': 'Файл подготовлен для другой модели.'}})
        return unmet

    def _plan_scenario(self, row, facts, data):
        key = data.get('job')
        job = self.jobs.get(key) if isinstance(key, str) else None
        self.view(key)
        if job['state'] != 'done' or not job.get('output'):
            raise ValueError('The conversion is not finished.')
        raw = Path(job['output']['path']).read_bytes()
        digest = self.service.safety.put_artifact(raw)
        item = {'name': job['output']['name'], 'sha256': digest, 'size': len(raw), 'component': 'media'}
        return self.service.safety.build_plan(
            row, facts, scenario='media', label=f"Media: {job['output']['name']}", folder='SymPort-Media', items=[item],
            risk={'level': 'low', 'blocking': [], 'irreversible': False},
            restore={'kind': 'files-created-by-symport', 'system_restore': 'unsupported', 'note': 'Rollback removes only the copied media file.'},
            phone_actions=[{'component': 'media', 'steps': [{'en': 'Open the file in the phone gallery or music player and check that it plays.', 'ru': 'Откройте файл в галерее или плеере телефона и проверьте, что он воспроизводится.'}],
                            'restore': {'en': 'Delete the copied file.', 'ru': 'Удалите скопированный файл.'}}],
            extra={'media_model': job['model']})
