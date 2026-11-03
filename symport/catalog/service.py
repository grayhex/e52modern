"""Durable application sets, batch queue and honest per-application outcomes."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path

from .download import Downloader
from .model import Catalog
from .packages import validate_package


def now():
    return datetime.now(UTC).isoformat()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(4) + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


class AppCatalog:
    def __init__(self, repo: Path, devices):
        self.catalog = Catalog(repo / 'catalog' if (repo / 'catalog').is_dir() else Path(__file__).resolve().parents[2] / 'catalog')
        self.root = repo / 'build' / 'symport' / 'app-catalog'
        self.devices = devices
        self.downloader = Downloader(self.root / 'cache')
        self.lock = threading.RLock()
        self.active = None
        # A restored process cannot resume in-flight network/device operations safely.
        for path in (self.root / 'jobs').glob('*.json'):
            job = json.loads(path.read_text())
            if job['state'] == 'running':
                job['state'] = 'interrupted'
                for item in job['items']:
                    if item['stage'] not in ('validated', 'awaiting-installation', 'user-confirmed-installed', 'failed'):
                        item.update(stage='interrupted', error='Process restarted; inspect phone before retry')
                save(path, job)

    def state(self, filters=None) -> dict:
        with self.lock:
            sets = json.loads((self.root / 'sets.json').read_text()) if (self.root / 'sets.json').exists() else {}
            jobs = sorted([json.loads(p.read_text()) for p in (self.root / 'jobs').glob('*.json')], key=lambda j: j['created'], reverse=True)[:30]
            apps = [dict(entry, distribution=self.catalog.sources.get(entry['source_id'], {}).get('artifacts', [])) for entry in self.catalog.list(filters)]
            return {'apps': apps, 'sets': sets, 'jobs': jobs,
                    'research': self.catalog.research, 'profile': 'nokia-e52'}

    def execute(self, data: dict) -> dict:
        action = data.get('action')
        if action == 'list':
            return self.state(data.get('filters'))
        if action == 'plan':
            return self.catalog.plan(data.get('ids'), data.get('profile', 'nokia-e52'))
        if action == 'save-set':
            name = data.get('name')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60 or any(ord(c) < 32 for c in name):
                raise ValueError('Set name must be 1–60 characters')
            plan = self.catalog.plan(data.get('ids'))
            if plan['problems']:
                raise ValueError('; '.join(plan['problems']))
            with self.lock:
                state = self.state()['sets']
                if len(state) >= 30 and name.strip() not in state:
                    raise ValueError('Maximum 30 saved sets')
                state[name.strip()] = data['ids']
                save(self.root / 'sets.json', state)
            return {'saved': name.strip()}
        if action == 'confirm-installed':
            if data.get('confirm') is not True:
                raise ValueError('Explicit user confirmation required')
            with self.lock:
                job = self.job(data.get('job'))
                item = next((i for i in job['items'] if i['id'] == data.get('app')), None)
                if not item or item['stage'] != 'awaiting-installation':
                    raise ValueError('Only transferred apps can be user-confirmed')
                item.update(stage='user-confirmed-installed', confirmed_at=now(), evidence='manual user observation')
                save(self.root / 'jobs' / (job['id'] + '.json'), job)
            return job
        if action in ('download', 'transfer'):
            plan = self.catalog.plan(data.get('ids'), data.get('profile', 'nokia-e52'))
            if plan['problems']:
                raise ValueError('; '.join(plan['problems']))
            if action == 'transfer' and (data.get('confirm') is not True or not isinstance(data.get('device'), str)
                                         or not isinstance(data.get('path', ''), str) or len(data.get('path', '')) > 1024):
                raise ValueError('Choose a phone and confirm transfer, not installation')
            if plan['bytes'] > 128 * 1024 * 1024:
                raise ValueError('Batch exceeds 128 MiB')
            with self.lock:
                if self.active:
                    raise ValueError('Another catalog batch is still running')
                key = secrets.token_hex(12)
                job = {'id': key, 'action': action, 'state': 'running', 'created': now(),
                       'items': [{'id': i, 'stage': 'queued', 'events': []} for i in plan['ids']],
                       'target': data.get('device') if action == 'transfer' else None}
                self.active = key
                save(self.root / 'jobs' / (key + '.json'), job)
                threading.Thread(target=self._run, args=(job, data), daemon=True).start()
            return job
        raise ValueError('Unknown catalog action')

    def job(self, key: str) -> dict:
        if not isinstance(key, str) or len(key) != 24 or any(c not in 'abcdef0123456789' for c in key):
            raise ValueError('Invalid job ID')
        return json.loads((self.root / 'jobs' / (key + '.json')).read_text())

    def _run(self, job: dict, request: dict):
        path = self.root / 'jobs' / (job['id'] + '.json')
        def update(item, stage, **details):
            with self.lock:
                item.update(stage=stage, **details)
                item['events'].append({'stage': stage, 'at': now()})
                save(path, job)
        try:
            if job['action'] == 'transfer':
                device = next((d for d in self.devices.transport.devices() if d['id'] == request['device']), None)
                required = self.catalog.plan([i['id'] for i in job['items']])['bytes']
                if not device or not (device['connected'] or (device.get('configured') and 'opp-push' in device['capabilities'])) or not any(c in device['capabilities'] for c in ('files', 'transfer')):
                    raise ValueError('Connected file-capable phone required')
                if device.get('free') is not None and device['free'] < required:
                    raise ValueError('Insufficient or unknown free space on phone')
            for item in job['items']:
                try:
                    failed_dependencies = [key for key in self.catalog.entries[item['id']]['dependencies'] if any(i['id'] == key and i['stage'] == 'failed' for i in job['items'])]
                    if failed_dependencies:
                        raise ValueError('Dependency failed: ' + ', '.join(failed_dependencies))
                    update(item, 'downloading')
                    entry = self.catalog.entries[item['id']]
                    source = self.catalog.sources[entry['source_id']]
                    artifacts = []
                    for artifact in source['artifacts']:
                        cached, evidence = self.downloader.fetch(source, artifact)
                        artifacts.append((cached, evidence))
                    update(item, 'downloaded', artifacts=[e for _, e in artifacts])
                    jar = next(((p.name, p.read_bytes()) for p, _ in artifacts if p.suffix.lower() == '.jar'), None)
                    if entry['format'] == 'jar+jad' and not any(p.suffix.lower() == '.jad' for p, _ in artifacts):
                        raise ValueError('Curated JAR/JAD pair is incomplete')
                    for cached, evidence in artifacts:
                        evidence['validation'] = validate_package(cached.name, cached.read_bytes(), jar=jar)
                        if cached.suffix.lower() == '.jad' and '://' in evidence['validation']['descriptor']['MIDlet-Jar-URL']:
                            raise ValueError('Remote JAD URL is not suitable for offline local transfer; use the curated JAR-only variant')
                        if cached.suffix.lower() == '.jar':
                            validation = evidence['validation']
                            if validation['midp'] not in ('MIDP-1.0', 'MIDP-2.0', 'MIDP-2.1') or validation['cldc'] not in ('CLDC-1.0', 'CLDC-1.1'):
                                raise ValueError('JAR MIDP/CLDC profile is not supported by the E52 profile')
                    update(item, 'validated')
                    if job['action'] == 'transfer' and any(c in device['capabilities'] for c in ('files-stage', 'opp-push')):
                        if entry['format'] == 'jar+jad':
                            raise ValueError('This OBEX adapter cannot preserve a JAR/JAD pair in one folder. Choose a JAR-only package or a mounted memory card.')
                        receipts = []
                        for cached, evidence in artifacts:
                            folder = '' if 'opp-push' in device['capabilities'] else request.get('path', '').rstrip('/')
                            receipt = self.devices.execute({'action': 'software-transfer', 'device': request['device'],
                                'path': '/'.join(filter(None, (folder, cached.name))), 'confirm': True,
                                'content': base64.b64encode(cached.read_bytes()).decode()})
                            receipts.append(receipt)
                        update(item, 'transferred', integrity='receiver-acknowledgement-only' if 'opp-push' in device['capabilities'] else 'sha256-read-back', receipts=receipts)
                        update(item, 'awaiting-installation', instructions='Откройте переданный пакет на Nokia и подтвердите установку.')
                    elif job['action'] == 'transfer':
                        directory = self.devices.execute({'action': 'list', 'device': request['device'], 'path': request.get('path', '')})
                        existing = {e['name'] for e in directory['entries']}
                        for cached, evidence in artifacts:
                            name = cached.name
                            folder = request.get('path', '').rstrip('/')
                            destination = '/'.join(filter(None, (folder, name)))
                            content = cached.read_bytes()
                            if name not in existing:
                                self.devices.execute({'action': 'software-transfer', 'device': request['device'],
                                                      'path': destination, 'confirm': True,
                                                      'content': base64.b64encode(content).decode()})
                            # Read-back is mandatory for transports advertising files; failure remains visible.
                            copied = self.devices.execute({'action': 'download', 'device': request['device'], 'path': destination})
                            if hashlib.sha256(base64.b64decode(copied['content'])).hexdigest() != evidence['sha256']:
                                raise ValueError('Phone read-back SHA-256 mismatch')
                        update(item, 'transferred', integrity='sha256-read-back')
                        update(item, 'awaiting-installation', instructions='Откройте пакет на Nokia и подтвердите установку на её экране.')
                except (ValueError, OSError, RuntimeError) as exc:
                    update(item, 'failed', error=str(exc)[:500], warning='A partial transfer may exist; inspect destination before retry')
            with self.lock:
                job['state'] = 'completed-with-errors' if any(i['stage'] == 'failed' for i in job['items']) else 'completed'
        except Exception as exc:
            # Never strand the durable queue as running after an unexpected parser/transport failure.
            message = str(exc)[:500] if isinstance(exc, (ValueError, OSError, RuntimeError)) else 'Unexpected catalog failure: ' + type(exc).__name__
            with self.lock:
                job.update(state='failed', error=message)
                for item in job['items']:
                    if item['stage'] in ('queued', 'downloading', 'downloaded'):
                        item.update(stage='failed', error=message)
        finally:
            with self.lock:
                job['finished'] = now()
                save(path, job)
                self.active = None

    def archive(self, key: str) -> bytes:
        import io
        import zipfile
        with self.lock:
            job = self.job(key)
            if job['state'] != 'completed' or any(i['stage'] not in ('validated', 'awaiting-installation', 'user-confirmed-installed') for i in job['items']):
                raise ValueError('All selected packages must be validated before exporting the batch')
            buffer = io.BytesIO()
            manifests = []
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
                for item in job['items']:
                    entry = self.catalog.entries[item['id']]
                    for artifact in item['artifacts']:
                        path = self.root / 'cache' / artifact['sha256'] / artifact['name']
                        content = path.read_bytes()
                        if hashlib.sha256(content).hexdigest() != artifact['sha256']:
                            raise ValueError('Cached package integrity changed')
                        archive.writestr(item['id'] + '/' + artifact['name'], content)
                    manifests.append({'app': entry, 'artifacts': item['artifacts']})
                archive.writestr('catalog-manifest.json', json.dumps(manifests, ensure_ascii=False, indent=2))
            return buffer.getvalue()
