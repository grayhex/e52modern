"""Local published theme library; importing a package does not publish it."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

from symport.phone.contracts import LIMIT
from symport.sis.reader import inspect


class ThemeLibrary:
    def __init__(self, repo: Path):
        self.root = repo / 'build' / 'symport' / 'library'

    def _metadata(self, key: str) -> Path:
        if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{24}', key):
            raise ValueError('Invalid library ID')
        return self.root / (key + '.json')

    def list(self) -> list[dict]:
        result = []
        if self.root.exists():
            for path in sorted(self.root.glob('*.json')):
                entry = json.loads(path.read_text())
                if entry['published']:
                    result.append(entry)
        return result

    def import_package(self, name: str, content: str) -> dict:
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}\.sisx?', name, re.I):
            raise ValueError('Choose a SIS/SISX filename')
        if not isinstance(content, str):
            raise ValueError('Package content must be base64 text')
        raw = base64.b64decode(content, validate=True)
        if len(raw) > LIMIT:
            raise ValueError('Package exceeds 8 MiB')
        info = inspect(raw)
        if not all(info[k] for k in ('controller_crc_ok', 'data_crc_ok', 'uid_checksum_ok')):
            raise ValueError('Package checksum validation failed')
        key = secrets.token_hex(12)
        entry = {'id': key, 'name': name, 'size': len(raw),
                 'sha256': hashlib.sha256(raw).hexdigest(), 'published': False,
                 'imported': datetime.now(UTC).isoformat(), 'device_verification': 'not-tested',
                 'warning': 'SIS structure checked; theme content and handset compatibility unverified'}
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = self.root / (key + '.sis')
        payload.write_bytes(raw)
        os.chmod(payload, 0o600)
        self._metadata(key).write_text(json.dumps(entry, ensure_ascii=False))
        return entry

    def publish(self, key: str, confirm: bool) -> dict:
        if confirm is not True:
            raise ValueError('Explicit publication confirmation required')
        path = self._metadata(key)
        entry = json.loads(path.read_text())
        entry['published'] = True
        path.write_text(json.dumps(entry, ensure_ascii=False))
        return entry

    def download(self, key: str) -> tuple[str, bytes]:
        entry = json.loads(self._metadata(key).read_text())
        if not entry['published']:
            raise ValueError('Package has not been published')
        raw = (self.root / (key + '.sis')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Library package integrity check failed')
        return entry['name'], raw
