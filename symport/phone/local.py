"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

from .files import MountedVolumes


class LocalTransports:
    """Mounted files plus optional Gammu identification with operator-owned config."""
    def __init__(self):
        self.files = MountedVolumes(json.loads(os.getenv('SYMPORT_DEVICE_ROOTS', '{}')))

    def devices(self) -> list[dict]:
        result = self.files.devices()
        config = os.getenv('SYMPORT_GAMMU_CONFIG')
        if config:
            device = {'id': 'gammu', 'transport': 'gammu', 'connected': False,
                      'model': None, 'rm': None, 'firmware': None, 'battery': None,
                      'capabilities': [], 'evidence': 'Gammu identification not yet successful'}
            try:
                output = subprocess.run(['gammu', '--config', config, 'identify'],
                                        capture_output=True, text=True, timeout=20, check=True).stdout
                values = {}
                for line in output.splitlines():
                    key, sep, value = line.partition(':')
                    if sep:
                        values[key.strip().lower()] = value.strip()
                model = values.get('model')
                if model:
                    rm = re.search(r'RM-\d+', model)
                    device.update(connected=True, model=model, rm=rm.group() if rm else None,
                                  firmware=values.get('firmware'), capabilities=['contacts-read', 'contacts-import'], evidence='Gammu identify response; phonebook support must be checked by reading')
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
            if data['action'] == 'contacts-read':
                return {'contacts': gammu_contacts.read(config)}
            if data['action'] == 'contacts-import':
                return gammu_contacts.import_contacts(config, data['contacts'], data.get('confirm'))
            raise ValueError('Gammu предоставляет контакты; для файлов выберите накопитель')
        return self.files.execute(data)


