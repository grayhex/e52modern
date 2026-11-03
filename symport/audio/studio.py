"""FFmpeg-backed ringtone workspace with bounded private input/output lifetime."""

from __future__ import annotations

import base64
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

MAX_INPUT = 64 * 1024**2
MAX_DURATION = 600
TTL = 3600
FORMATS = "mp3,wav,aac,mov,mp4,m4a,3gp,3g2,mj2,flac,ogg,matroska,webm,asf,aiff"


class RingtoneStudio:
    def __init__(self, repo, devices, media):
        self.root = Path(repo) / "build/symport/ringtone-temp"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.devices, self.media = devices, media
        self.lock, self.slots = threading.RLock(), threading.BoundedSemaphore(2)
        self.items = {}
        self.closed = threading.Event()
        self.cleanup()
        threading.Thread(target=self._janitor, daemon=True, name="ringtone-cleanup").start()

    def _janitor(self):
        while not self.closed.wait(60):
            try:
                self.cleanup()
            except FileNotFoundError:
                return

    def cleanup(self):
        with self.lock:
            for path in self.root.iterdir():
                if not path.is_dir() or path.is_symlink():
                    continue
                item = self.items.get(path.name)
                if not item or (not item.get("busy") and time.monotonic() > item["expires"]):
                    shutil.rmtree(path)
                    self.items.pop(path.name, None)

    def run(self, tool, args, timeout=80):
        executable = shutil.which(tool)
        if not executable:
            raise ValueError("FFmpeg is unavailable. Install the current Docker image.")
        if sys.platform != "linux":
            raise ValueError("Ringtone processing requires the Linux Docker backend.")
        command = [sys.executable, "-m", "symport.audio.worker", executable, *args]
        try:
            with tempfile.TemporaryFile() as log, tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=log,
                    timeout=timeout,
                    check=False,
                    env={
                        **os.environ,
                        "LC_ALL": "C",
                        "OPENBLAS_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "2",
                    },
                )
                log.seek(0, 2)
                if log.tell() > 1024**2:
                    raise ValueError("Audio processing produced excessive diagnostics.")
                log.seek(0)
                diagnostic = log.read().decode("utf-8", errors="replace")
                output.seek(0, 2)
                if result.returncode or output.tell() > 1024**2:
                    raise ValueError(
                        "Audio could not be decoded or processed. Choose a supported audio/video file."
                    )
                output.seek(0)
                return output.read(), diagnostic
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "Audio processing timed out. Choose a shorter file or selection."
            ) from exc

    def probe(self, path):
        raw, _ = self.run(
            "ffprobe",
            [
                "-v",
                "error",
                "-max_alloc",
                "67108864",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                FORMATS,
                "-show_entries",
                "format=duration:stream=codec_type,sample_rate,channels",
                "-of",
                "json",
                str(path),
            ],
            20,
        )
        metadata = json.loads(raw)
        duration = float(metadata.get("format", {}).get("duration", "nan"))
        audio = next(
            (s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"), None
        )
        if not audio or not math.isfinite(duration) or not 0 < duration <= MAX_DURATION:
            raise ValueError("Choose a file with an audio track lasting at most 10 minutes.")
        return {
            "duration": duration,
            "channels": int(audio.get("channels", 0)),
            "sample_rate": int(audio.get("sample_rate", 0)),
        }

    def ffmpeg(self, source, output, filters="", start=0, duration=MAX_DURATION, extra=()):
        args = [
            "-hide_banner",
            "-loglevel",
            "info",
            "-nostdin",
            "-n",
            "-max_alloc",
            "67108864",
            "-threads",
            "2",
            "-filter_threads",
            "1",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            FORMATS,
            "-i",
            str(source),
            "-ss",
            str(start),
            "-t",
            str(duration),
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-map_metadata",
            "-1",
        ]
        if filters:
            args += ["-af", filters]
        args += [*extra, str(output)]
        return self.run("ffmpeg", args)

    def create(self, stream=None, length=0, gallery=None):
        if not self.slots.acquire(blocking=False):
            raise ValueError("Ringtone Studio is busy. Try again shortly.")
        identifier = secrets.token_hex(16)
        folder = self.root / identifier
        try:
            self.cleanup()
            with self.lock:
                if len(self.items) >= 3:
                    raise ValueError("Close an existing audio source before uploading another.")
                folder.mkdir(mode=0o700)
                self.items[identifier] = {
                    "busy": True,
                    "expires": time.monotonic() + TTL,
                    "output": None,
                }
            source = folder / "input.bin"
            if gallery is not None:
                meta = self.devices.execute(dict(gallery, action="media-info"))
                length = meta["size"]
                if meta.get("kind") not in ("audio", "video") and not str(
                    meta.get("mime", "")
                ).startswith(("audio/", "video/")):
                    raise ValueError("Select an audio or video file.")
            if type(length) is not int or not 0 < length <= MAX_INPUT:
                raise ValueError("Audio input must be between 1 byte and 64 MiB.")
            with source.open("xb") as target:
                os.chmod(source, 0o600)
                if gallery is not None:
                    for chunk in self.media.chunks(gallery, 0, length - 1):
                        target.write(chunk)
                else:
                    remaining = length
                    while remaining:
                        chunk = stream.read(min(256 * 1024, remaining))
                        if not chunk:
                            raise ValueError("Audio upload was interrupted.")
                        target.write(chunk)
                        remaining -= len(chunk)
            if source.stat().st_size != length:
                raise ValueError("Incomplete audio input.")
            meta = self.probe(source)
            preview = folder / "preview.wav"
            self.ffmpeg(source, preview, extra=("-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"))
            os.chmod(preview, 0o600)
            with self.lock:
                self.items[identifier].update(meta, busy=False)
            return {
                "id": identifier,
                **meta,
                "preview": f"/api/audio/{identifier}/preview",
                "expires_in": TTL,
            }
        except Exception:
            with self.lock:
                self.items.pop(identifier, None)
                if folder.exists():
                    shutil.rmtree(folder)
            raise
        finally:
            self.slots.release()

    def item(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch("[a-f0-9]{32}", identifier):
            raise ValueError("Invalid audio source.")
        item = self.items.get(identifier)
        if not item or (not item.get("busy") and item["expires"] < time.monotonic()):
            raise ValueError("Audio source expired. Upload it again.")
        return item

    @staticmethod
    def options(data, source_duration):
        def number(key, default, low, high):
            value = data.get(key, default)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError("Invalid audio parameter: " + key)
            return value

        start, end = (
            number("start", 0, 0, source_duration),
            number("end", min(30, source_duration), 0, source_duration),
        )
        if not 0.1 <= end - start <= 180:
            raise ValueError("Select a fragment between 0.1 and 180 seconds.")
        opts = {
            "start": start,
            "end": end,
            "fade_in": number("fade_in", 0.1, 0, min(10, (end - start) / 2)),
            "fade_out": number("fade_out", 0.3, 0, min(10, (end - start) / 2)),
            "lufs": number("lufs", -16, -30, -9),
        }
        for key, default, allowed in [
            ("bitrate", 128, {32, 48, 64, 96, 128, 160, 192, 256, 320}),
            ("sample_rate", 44100, {8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000}),
        ]:
            value = data.get(key, default)
            if type(value) is not int or value not in allowed:
                raise ValueError("Unsupported " + key)
            opts[key] = value
        for key in ("mono", "normalize"):
            value = data.get(key, True)
            if type(value) is not bool:
                raise ValueError("Invalid " + key)
            opts[key] = value
        return opts

    def export(self, identifier, data):
        if not self.slots.acquire(blocking=False):
            raise ValueError("Ringtone Studio is busy. Try again shortly.")
        item = None
        acquired = False
        candidate = None
        succeeded = False
        try:
            with self.lock:
                item = self.item(identifier)
                if item["busy"]:
                    raise ValueError("This audio source is busy.")
                opts = self.options(data, item["duration"])
                item["busy"] = True
                acquired = True
            folder = self.root / identifier
            duration = opts["end"] - opts["start"]
            filters = []
            if opts["mono"]:
                filters.append("aformat=channel_layouts=mono")
            if opts["normalize"]:
                target = f"loudnorm=I={opts['lufs']}:TP=-1.5:LRA=11"
                _, log = self.ffmpeg(
                    folder / "input.bin",
                    "-",
                    ",".join([*filters, target + ":print_format=json"]),
                    opts["start"],
                    duration,
                    ("-f", "null"),
                )
                match = re.search(r'\{\s*"input_i".*?\}', log, re.S)
                measured = json.loads(match[0]) if match else {}
                values = [
                    measured.get(k)
                    for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
                ]
                if len(values) == 5 and all(
                    v is not None and math.isfinite(float(v)) for v in values
                ):
                    target += ":measured_I={}:measured_TP={}:measured_LRA={}:measured_thresh={}:offset={}:linear=true".format(
                        *[float(v) for v in values]
                    )
                filters.append(target)
            if opts["fade_in"]:
                filters.append(f"afade=t=in:st=0:d={opts['fade_in']}")
            if opts["fade_out"]:
                filters.append(f"afade=t=out:st={duration - opts['fade_out']}:d={opts['fade_out']}")
            version = secrets.token_hex(8)
            output = folder / (version + ".mp3")
            candidate = output
            self.ffmpeg(
                folder / "input.bin",
                output,
                ",".join(filters),
                opts["start"],
                duration,
                (
                    "-c:a",
                    "libmp3lame",
                    "-b:a",
                    str(opts["bitrate"]) + "k",
                    "-ar",
                    str(opts["sample_rate"]),
                    "-ac",
                    "1" if opts["mono"] else "2",
                ),
            )
            os.chmod(output, 0o600)
            meta = self.probe(output)
            with self.lock:
                previous = item["output"]
                item.update(output=version, expires=time.monotonic() + TTL)
                if previous:
                    (folder / (previous + ".mp3")).unlink(missing_ok=True)
            succeeded = True
            return {
                "id": identifier,
                "version": version,
                "size": output.stat().st_size,
                **meta,
                "options": opts,
                "url": f"/api/audio/{identifier}/{version}",
            }
        finally:
            if candidate and not succeeded:
                candidate.unlink(missing_ok=True)
            if acquired:
                with self.lock:
                    item["busy"] = False
            self.slots.release()

    def read(self, identifier, version):
        with self.lock:
            item = self.item(identifier)
            if version == "preview":
                path, mime = self.root / identifier / "preview.wav", "audio/wav"
            elif version == item["output"] and re.fullmatch("[a-f0-9]{16}", str(version)):
                path, mime = self.root / identifier / (version + ".mp3"), "audio/mpeg"
            else:
                raise ValueError("Export the ringtone again.")
            return path.read_bytes(), mime

    def execute(self, data):
        action = data.get("action")
        if action == "gallery":
            context = {k: data.get(k) for k in ("device", "path", "revision")}
            return self.create(gallery=context)
        if action == "export":
            return self.export(data.get("id"), data)
        if action == "delete":
            with self.lock:
                item = self.item(data.get("id"))
                if item["busy"]:
                    raise ValueError("Audio processing is in progress.")
                shutil.rmtree(self.root / data["id"])
                del self.items[data["id"]]
            return {"deleted": True}
        if action == "transfer":
            if data.get("confirm") is not True:
                raise ValueError("Confirm the ringtone transfer.")
            raw, _ = self.read(data.get("id"), data.get("version"))
            device = next(
                (
                    d
                    for d in self.devices.execute({"action": "discover"})["devices"]
                    if d["id"] == data.get("device")
                ),
                None,
            )
            if not device or "transfer" not in device.get("capabilities", []):
                raise ValueError("The selected connection cannot transfer files.")
            path = data.get("path", "")
            if not isinstance(path, str) or len(path) > 900:
                raise ValueError("Choose a phone folder.")
            if "opp-push" in device["capabilities"]:
                path = ""
            name = "SymPort-ringtone-" + data["version"] + ".mp3"
            return self.devices.execute(
                {
                    "action": "media-upload",
                    "kind": "audio",
                    "device": device["id"],
                    "path": "/".join(filter(None, (path.rstrip("/"), name))),
                    "content": base64.b64encode(raw).decode(),
                    "confirm": True,
                }
            )
        raise ValueError("Unknown Ringtone Studio operation.")
