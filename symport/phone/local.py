"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from .files import MountedVolumes


class LocalTransports:
    """Mounted files plus optional Gammu identification with operator-owned config."""
    def __init__(self, repo: Path | None = None):
        from .personal import PersonalWorkspace
        self.personal = PersonalWorkspace(repo or Path.cwd())
        self.files = MountedVolumes(json.loads(os.getenv('SYMPORT_DEVICE_ROOTS', '{}')))

    def devices(self) -> list[dict]:
        from . import gammu_native
        result = self.files.devices()
        config = os.getenv('SYMPORT_GAMMU_CONFIG')
        if config:
            device = {'id': 'gammu', 'transport': 'gammu', 'connected': False,
                      'model': None, 'rm': None, 'firmware': None, 'battery': None,
                      'capabilities': [], 'evidence': 'Gammu identification not yet successful'}
            if gammu_native.available():
                try:
                    details = self.personal.execute(config, {'action': 'device-details'})
                    device.update(details, connected=True, evidence='Gammu service responses')
                    device['capabilities'] = ['device-details', 'personal-data']
                    device['capabilities'] += [name + '-read' for name, status in details['capability_status'].items() if status['status'] == 'available']
                except ValueError:
                    device['evidence'] = 'Gammu connection failed; check the configured driver and phone mode'
            if not device['connected']:
                try:
                    output = subprocess.run(['gammu', '--config', config, 'identify'],
                                            capture_output=True, text=True, timeout=20, check=True,
                                            env={**os.environ, 'LC_ALL': 'C'}).stdout
                    values = {}
                    for line in output.splitlines():
                        key, sep, value = line.partition(':')
                        if sep:
                            values[key.strip().lower()] = value.strip()
                    model = values.get('model')
                    if model:
                        rm = re.search(r'RM-\d+', model)
                        device.update(connected=True, model=model, rm=rm.group() if rm else None,
                                      firmware=values.get('firmware'), capabilities=['contacts-read', 'calendar-read'],
                                      evidence='Gammu CLI identity response; read the selected store to check access')
                except (OSError, subprocess.SubprocessError):
                    device['evidence'] = 'Gammu unavailable, configuration invalid or phone unreachable'
            result.append(device)
        return result

    def execute(self, data: dict) -> dict:
        if data.get('device') == 'gammu':
            from . import gammu_contacts
            config = os.getenv('SYMPORT_GAMMU_CONFIG')
            if not config:
                raise ValueError('Настройте Gammu на ПК с телефоном')
            if data['action'].startswith('personal-') or data['action'] in ('device-details', 'device-imei', 'sms-send'):
                return self.personal.execute(config, data)
            if data['action'] == 'contacts-read':
                return {'contacts': gammu_contacts.read(config)}
            if data['action'] == 'contacts-import':
                raise ValueError('Use the phone sync preview with python-gammu for direct writes, or transfer vCard files and import them on the phone')
            if data['action'] == 'calendar-read':
                from . import gammu_calendar
                return gammu_calendar.read(config, include_raw=True)
            raise ValueError('Gammu предоставляет контакты; для файлов выберите накопитель')
        if data.get('action') in ('media-list', 'media-info', 'media-chunk', 'media-thumbnail'):
            from . import media
            return media.execute(self.files, data)
        if data.get('action') == 'apps-inventory':
            root = self.files.roots.get(data.get('device'))
            if root is None or not root.is_dir() or root.is_symlink():
                raise ValueError('Unknown or disconnected device')
            from . import inventory
            return inventory.scan(root)
        return self.files.execute(data)


