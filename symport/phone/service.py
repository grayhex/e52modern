"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

import json
import os
import threading
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .bridge import PCBridge
from .contracts import Transport
from .local import LocalTransports


class DeviceManager:
    def __init__(self, repo: Path, transport: Transport | None = None):
        self.transport = transport or (
            PCBridge(os.environ['SYMPORT_BRIDGE_URL'], os.getenv('SYMPORT_BRIDGE_KEY', ''))
            if os.getenv('SYMPORT_BRIDGE_URL') else
            LocalTransports(repo)
        )
        self.lock = threading.Lock()
        self.journal = repo / 'build' / 'symport' / 'device-manager' / 'operations.jsonl'

    def execute(self, data: dict) -> dict:
        allowed = {'discover', 'history', 'list', 'download', 'upload', 'transfer',
                   'mkdir', 'delete', 'backup', 'restore-preview', 'restore', 'contacts-stage',
                   'contacts-read', 'contacts-import', 'media-upload', 'software-transfer',
                   'apps-inventory', 'calendar-read', 'media-list', 'media-info', 'media-chunk', 'media-thumbnail',
                   'device-details', 'device-imei', 'personal-read', 'personal-preview', 'personal-apply',
                   'personal-calendar-import', 'personal-export', 'personal-backup', 'personal-backup-download', 'sms-send'}
        if not isinstance(data.get('action'), str) or data['action'] not in allowed:
            raise ValueError('Unknown device operation')
        if data['action'] not in ('discover', 'history'):
            if not isinstance(data.get('device'), str) or not isinstance(data.get('path', ''), str):
                raise ValueError('Device and path must be strings')
            if len(data.get('path', '')) > 1024 or not isinstance(data.get('content', ''), str):
                raise ValueError('Invalid path or content')
        if data['action'] == 'media-upload' and data.get('kind') not in ('audio', 'video'):
            raise ValueError('Выберите тип медиа: аудио или видео')
        if data['action'] in ('contacts-stage', 'contacts-import'):
            from .contacts import normalize
            data = dict(data, contacts=normalize(data.get('contacts')))
        with self.lock:
            if data.get('action') == 'discover':
                return {'devices': self.transport.devices(), 'limitations': {
                    'contacts': 'Импорт Google CSV / Apple vCard, передача vCard на карту или запись через Gammu с чтением для проверки',
                    'sms': 'Requires a tested Gammu or native Agent adapter',
                    'applications': 'Mounted volumes do not expose the installed application registry; apps-inventory lists SIS package files only',
                    'calendar': 'Calendar and tasks require Gammu storage access; use Nokia Suite iCalendar export if the selected driver cannot read them',
                    'backup': 'File backup covers only the selected folder, not contacts, SMS, applications or firmware',
                    'bluetooth': 'OBEX pairing and service discovery must run on the PC connected to the phone',
                }}
            if data.get('action') == 'history':
                if not self.journal.exists():
                    return {'operations': []}
                return {'operations': [json.loads(x) for x in self.journal.read_text().splitlines()[-100:]]}
            status = 'failed'
            try:
                try:
                    result = self.transport.execute(data)
                except zipfile.BadZipFile as exc:
                    raise ValueError('Invalid ZIP archive') from exc
                status = 'unverified' if result.get('status') in ('partial-or-unverified', 'submitted-to-network') else 'success'
                return result
            finally:
                self.journal.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                # Never retain payloads, phone paths, contacts, SMS or exception text.
                record = {'time': datetime.now(UTC).isoformat(),
                          'action': str(data.get('action', ''))[:40], 'status': status}
                if self.journal.exists() and self.journal.stat().st_size > 1024 * 1024:
                    self.journal.unlink()
                with self.journal.open('a', encoding='utf-8') as log:
                    os.chmod(self.journal, 0o600)
                    log.write(json.dumps(record) + '\n')
