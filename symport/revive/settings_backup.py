"""Settings and databases backup (#36 addendum): capability-aware export, versioned manifest, preview restore.

Only stores whose read capability is *verified on this connection* can be exported, only with the
owner's consent, and the result says how complete it is. The manifest (shareable) holds hashes,
counts and metadata; the private payloads live in a separate 0600 area and never in a report.
Restore is a preview with conflicts, then one component at a time through the existing
read-back-verified personal-data writer. Nothing here copies into protected system paths, restores a
system database or promises a full-device backup or a rollback after a CFW.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import secrets
import shutil
import zipfile
from pathlib import Path

from symport.catalog.service import now

SCHEMA = 'symport.settings-backup/1'
ID = re.compile(r'^[0-9a-f]{16}$')
MAX_ARCHIVE = 16 * 1024 * 1024
LEVELS = ('exported', 'restored-with-readback', 'manual-only', 'unavailable')
CATEGORIES = [
    {'id': 'contacts', 'op': 'contacts.read', 'domain': 'contacts', 'restore': True, 'sensitive': False, 'schema': 'symport.personal.contacts/1'},
    {'id': 'calendar', 'op': 'calendar.read', 'domain': 'calendar', 'restore': True, 'sensitive': False, 'schema': 'symport.personal.calendar/1'},
    {'id': 'tasks', 'op': 'tasks.read', 'domain': 'tasks', 'restore': True, 'sensitive': False, 'schema': 'symport.personal.tasks/1'},
    {'id': 'sms', 'op': 'sms.read', 'domain': 'sms', 'restore': False, 'sensitive': True, 'schema': 'symport.personal.sms/1'},
    {'id': 'notes', 'level': 'unavailable', 'reason': {'en': 'No read API through this transport; needs the Device Agent (#38), which is not implemented.', 'ru': 'Нет API чтения через этот транспорт; нужен Device Agent (#38), он не реализован.'}},
    {'id': 'profiles', 'level': 'manual-only', 'reason': {'en': 'Profile settings are not readable here: write them down on the phone (Profiles) and re-enter them after a restore.', 'ru': 'Настройки профилей отсюда не читаются: запишите их на телефоне («Профили») и введите заново после восстановления.'}},
    {'id': 'app-settings', 'level': 'unavailable', 'reason': {'en': 'Application settings live in protected stores with no permitted read API.', 'ru': 'Настройки приложений лежат в защищённых хранилищах без разрешённого API чтения.'}},
    {'id': 'system-databases', 'level': 'unavailable', 'reason': {'en': 'System databases are never copied blindly into or out of protected paths.', 'ru': 'Системные базы никогда не копируются вслепую в защищённые пути и из них.'}},
]
STATEMENT = ('Not a backup of the phone: only the stores listed as exported, as read through the driver (completeness is not verified). '
             'It cannot restore firmware, applications or system databases and promises nothing after a CFW installation.')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class SettingsBackup:
    def __init__(self, service):
        self.service = service
        self.root = service.root / 'settings-backups'

    def _dir(self, backup_id) -> Path:
        if not isinstance(backup_id, str) or not ID.fullmatch(backup_id):
            raise ValueError('Invalid backup id')
        return self.root / backup_id

    def _manifest(self, backup_id) -> dict:
        try:
            manifest = json.loads((self._dir(backup_id) / 'manifest.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ValueError('Unknown backup') from exc
        if manifest.get('schema') != SCHEMA:
            raise ValueError('Unsupported backup schema')
        return manifest

    def _payload(self, backup_id, category) -> bytes:
        manifest = self._manifest(backup_id)
        entry = manifest['categories'].get(category)
        if not entry:
            raise ValueError('The backup does not contain this category')
        path = self._dir(backup_id) / 'payload' / (category + '.json')
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ValueError('The payload is missing; the backup is damaged') from exc
        if sha(raw) != entry['sha256']:
            raise ValueError('The payload hash differs from the manifest; the backup is damaged and was not used')
        return raw

    # ---- state -----------------------------------------------------------------------------------------
    def levels(self, row) -> list[dict]:
        caps = (row or {}).get('capability_matrix') or {}
        out = []
        for c in CATEGORIES:
            if 'level' in c:
                out.append({'id': c['id'], 'level': c['level'], 'reason': c['reason'], 'sensitive': False, 'restore': False})
                continue
            status = (caps.get(c['op']) or {}).get('status', 'not-tested')
            level = 'exportable' if status == 'available' else 'unverified' if status == 'not-tested' else 'unavailable'
            reason = {'exportable': {'en': 'The read capability is verified on this connection.', 'ru': 'Возможность чтения проверена на этом подключении.'},
                      'unverified': {'en': 'The read capability has not been verified; run the capability recheck first.', 'ru': 'Возможность чтения не проверена; сначала выполните перепроверку возможностей.'},
                      'unavailable': {'en': 'This transport cannot read it.', 'ru': 'Этот транспорт не умеет это читать.'}}[level]
            out.append({'id': c['id'], 'level': level, 'reason': reason, 'sensitive': c['sensitive'], 'restore': c['restore']})
        return out

    def state(self, data):
        row, rows, facts = self.service._context(data)
        backups = []
        for path in sorted(self.root.glob('*/manifest.json'), reverse=True)[:30] if self.root.is_dir() else []:
            try:
                m = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            backups.append({'id': m['id'], 'created': m['created'], 'device': m['device'],
                            'categories': {k: {kk: v[kk] for kk in ('status', 'count', 'sensitive')} for k, v in m['categories'].items()}})
        return {'device': (row or {}).get('id'), 'reason': None if row else ('no-connection' if not rows else 'device-not-selected'),
                'categories': self.levels(row), 'backups': backups, 'levels': list(LEVELS), 'statement': STATEMENT}

    # ---- export ----------------------------------------------------------------------------------------
    def export(self, data):
        if data.get('confirm') is not True or data.get('owner_consent') is not True:
            raise ValueError('Confirm that you own this phone and consent to exporting the selected stores')
        wanted = data.get('categories')
        if not isinstance(wanted, list) or not wanted or len(wanted) > 4 or len(set(wanted)) != len(wanted):
            raise ValueError('Choose up to four stores')
        row, facts = self.service._need_device(data)
        known = {c['id']: c for c in CATEGORIES if 'op' in c}
        levels = {x['id']: x for x in self.levels(row)}
        for cid in wanted:
            if cid not in known:
                raise ValueError(f'{cid} cannot be exported')
            if levels[cid]['level'] != 'exportable':
                raise ValueError(f'{cid}: the read capability is not verified on this connection')
        backup_id = secrets.token_hex(8)
        directory = self._dir(backup_id)
        (directory / 'payload').mkdir(parents=True, mode=0o700)
        categories = {}
        try:
            for cid in wanted:
                c = known[cid]
                snap = self.service.devices.execute({'action': 'personal-read', 'device': row['id'], 'domain': c['domain']})
                exported = self.service.devices.execute({'action': 'personal-export', 'device': row['id'], 'snapshot': snap['snapshot'], 'format': 'json'})
                raw = base64.b64decode(exported['content'], validate=True)
                body = json.loads(raw)
                target = directory / 'payload' / (cid + '.json')
                target.write_bytes(raw)
                target.chmod(0o600)
                categories[cid] = {'status': 'exported', 'count': len(body.get('rows', [])), 'sha256': sha(raw), 'bytes': len(raw),
                                   'sensitive': c['sensitive'], 'completeness': 'as-read-by-driver (not verified complete)', 'import_schema': c['schema']}
        except (ValueError, OSError, KeyError):
            shutil.rmtree(directory, ignore_errors=True)
            raise
        manifest = {'schema': SCHEMA, 'id': backup_id, 'created': now(),
                    'device': {k: row.get(k) for k in ('model', 'rm', 'firmware', 'transport', 'connection_kind')} | {'fingerprint': row.get('capability_fingerprint')},
                    'categories': categories, 'secrets': 'none-collected', 'statement': STATEMENT}
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'backup': backup_id, 'manifest': manifest}

    def download(self, data):
        manifest = self._manifest(data.get('backup'))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            for cid in manifest['categories']:
                z.writestr(f'payload/{cid}.json', self._payload(manifest['id'], cid))
        return {'name': f"symport-settings-{manifest['id']}.zip", 'mime': 'application/zip',
                'content': base64.b64encode(buffer.getvalue()).decode(), 'contains_private_data': True,
                'warning': 'This archive contains private data (contacts, messages). Keep it protected.'}

    def import_archive(self, data):
        try:
            raw = base64.b64decode(data.get('content', ''), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('Damaged archive: not valid base64') from exc
        if not raw or len(raw) > MAX_ARCHIVE:
            raise ValueError('Damaged archive: empty or larger than 16 MiB')
        try:
            z = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise ValueError('Damaged archive: not a ZIP file') from exc
        with z:
            names = z.namelist()
            if len(names) > 12 or len(set(names)) != len(names) or any(n.startswith('/') or '..' in n.split('/') or '\\' in n for n in names):
                raise ValueError('Damaged archive: unsafe or duplicate entries')
            if sum(i.file_size for i in z.infolist()) > MAX_ARCHIVE or z.testzip() is not None:
                raise ValueError('Damaged archive: limits or checksum failure')
            try:
                manifest = json.loads(z.read('manifest.json'))
            except (KeyError, ValueError) as exc:
                raise ValueError('Damaged archive: no readable manifest') from exc
            if manifest.get('schema') != SCHEMA:
                raise ValueError('Unsupported backup schema')
            if not ID.fullmatch(str(manifest.get('id', ''))) or self._dir(manifest['id']).exists():
                raise ValueError('Invalid or already imported backup id')
            payloads = {}
            for cid, entry in manifest.get('categories', {}).items():
                if cid not in {c['id'] for c in CATEGORIES if 'op' in c}:
                    raise ValueError(f'Unsupported category in the archive: {cid}')
                try:
                    body = z.read(f'payload/{cid}.json')
                except KeyError as exc:
                    raise ValueError(f'Damaged archive: payload for {cid} is missing') from exc
                if sha(body) != entry.get('sha256'):
                    raise ValueError(f'Damaged archive: the {cid} payload hash differs from the manifest')
                payloads[cid] = body
        directory = self._dir(manifest['id'])
        (directory / 'payload').mkdir(parents=True, mode=0o700)
        for cid, body in payloads.items():
            target = directory / 'payload' / (cid + '.json')
            target.write_bytes(body)
            target.chmod(0o600)
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'backup': manifest['id'], 'categories': sorted(payloads)}

    def delete(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm deleting this settings backup')
        directory = self._dir(data.get('backup'))
        if not (directory / 'manifest.json').is_file() or directory.is_symlink():
            raise ValueError('Unknown backup')
        shutil.rmtree(directory)
        return {'deleted': directory.name}

    # ---- restore: preview, then one component with read-back ------------------------------------------------
    def _restore_context(self, data):
        manifest = self._manifest(data.get('backup'))
        cid = data.get('category')
        spec = next((c for c in CATEGORIES if c['id'] == cid and 'op' in c), None)
        if spec is None or cid not in manifest['categories']:
            raise ValueError('Choose a category contained in the backup')
        if not spec['restore']:
            raise ValueError(f'{cid} is manual-only: SymPort cannot write it back')
        row, facts = self.service._need_device(data)
        other = (row.get('model'), row.get('rm')) != (manifest['device'].get('model'), manifest['device'].get('rm'))
        return manifest, spec, row, other

    def restore_preview(self, data):
        manifest, spec, row, other = self._restore_context(data)
        raw = self._payload(manifest['id'], spec['id'])
        rows = json.loads(raw).get('rows', [])
        snap = self.service.devices.execute({'action': 'personal-read', 'device': row['id'], 'domain': spec['domain']})
        preview = self.service.devices.execute({'action': 'personal-preview', 'device': row['id'], 'snapshot': snap['snapshot'], 'rows': rows})
        return {'backup': manifest['id'], 'category': spec['id'], 'other_phone': other, 'snapshot': snap['snapshot'], 'plan': preview.get('plan'),
                'changes': preview.get('changes', []), 'conflicts': preview.get('conflicts', []), 'skipped': preview.get('skipped'),
                'deletions': preview.get('deletions', 0), 'dry_run': True,
                'blocked': bool(preview.get('conflicts')) or other,
                'blocking': (['conflicts'] if preview.get('conflicts') else []) + (['other-phone'] if other else []),
                'statement': 'Preview only: nothing was written. A restore writes one store at a time and is verified by reading it back.'}

    def restore_apply(self, data):
        if data.get('confirm') is not True:
            raise ValueError('Confirm the restore preview')
        manifest, spec, row, other = self._restore_context(data)
        if other and data.get('acknowledge_other_phone') is not True:
            raise ValueError('This backup was taken from another phone; acknowledge to restore it here')
        result = self.service.devices.execute({'action': 'personal-apply', 'device': row['id'], 'snapshot': data.get('snapshot'),
                                               'plan': data.get('plan'), 'confirm': True})
        verified = result.get('status') == 'verified-by-readback'
        return {'backup': manifest['id'], 'category': spec['id'], 'level': 'restored-with-readback' if verified else 'unverified',
                'status': result.get('status'), 'verified': result.get('verified'), 'requested': result.get('requested'),
                'checkpoint': result.get('backup'),
                'statement': 'Restored and read back.' if verified else 'The write could not be verified by reading back; read the phone again before another attempt.'}
