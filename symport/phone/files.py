"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

import base64
import hashlib
import io
import secrets
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from .contracts import LIMIT


class MountedVolumes:
    def __init__(self, roots: dict[str, str]):
        self.roots = {k: Path(v).absolute() for k, v in roots.items()}

    def devices(self) -> list[dict]:
        result = []
        for key, root in self.roots.items():
            connected = root.is_dir() and not root.is_symlink()
            usage = shutil.disk_usage(root) if connected else None
            result.append({"id": key, "transport": "mounted-volume", "connected": connected,
                           "model": None, "rm": None, "firmware": None, "battery": None,
                           "free": usage.free if usage else None,
                           "total": usage.total if usage else None,
                           "evidence": "Operator-enrolled volume; phone identity unverified",
                           "capabilities": ["files", "transfer"] if connected else []})
        return result

    def _path(self, device: str, value: str) -> Path:
        if device not in self.roots:
            raise ValueError("Unknown device")
        if not isinstance(value, str) or '\\' in value or '\0' in value:
            raise ValueError("Invalid device path")
        parts = PurePosixPath(value).parts
        reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
        if value.startswith('/') or any(p in ('.', '..') or ':' in p or p.endswith((' ', '.'))
                                        or p.split('.')[0].upper() in reserved for p in parts):
            raise ValueError("Path must be relative to the enrolled drive")
        root = self.roots[device]
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Device disconnected")
        # Reject symlinks in *every* ancestor, including the enrolled root.
        for ancestor in (root, *root.parents):
            if ancestor.is_symlink() or (getattr(ancestor, 'is_junction', lambda: False)()):
                raise ValueError("Symlink roots are forbidden")
        path = root
        for part in parts:
            path = path / part
            if path.is_symlink() or (getattr(path, 'is_junction', lambda: False)()):
                raise ValueError("Symlinks are forbidden")
        return path

    def execute(self, data: dict) -> dict:
        action = data.get('action')
        path = self._path(data.get('device'), data.get('path', ''))
        if action == 'contacts-stage':
            from .contacts import vcards
            if data.get('confirm') is not True:
                raise ValueError('Подтвердите передачу vCard на телефон')
            cards = vcards(data['contacts'])
            folder = path / ('Contacts-import-' + secrets.token_hex(5))
            folder.mkdir()
            try:
                for i, card in enumerate(cards, 1):
                    (folder / f'contact-{i:04}.vcf').write_text(card, encoding='utf-8', newline='')
            except OSError:
                for entry in folder.iterdir():
                    entry.unlink()
                folder.rmdir()
                raise
            return {'status': 'vcards-transferred-not-imported', 'count': len(cards),
                    'folder': folder.name, 'instructions': 'Откройте vCard на телефоне и сохраните в Контакты. Запись в книгу ещё не подтверждена.'}
        if action == 'list':
            entries = []
            for p in sorted(path.iterdir(), key=lambda p: p.name.casefold()):
                if p.is_symlink():
                    continue
                entries.append({'name': p.name, 'directory': p.is_dir(),
                                'size': p.stat().st_size if p.is_file() else None})
                if len(entries) > 5000:
                    raise ValueError('Folder exceeds 5000 entries')
            return {'entries': entries}
        if action == 'backup':
            buffer = io.BytesIO()
            total = 0
            with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
                for entry in sorted(path.iterdir()):
                    if entry.is_symlink() or not entry.is_file():
                        continue
                    total += entry.stat().st_size
                    if total > LIMIT - 65536 or len(archive.namelist()) >= 500:
                        raise ValueError('Backup exceeds 8 MiB or 500 files')
                    archive.writestr(entry.name, entry.read_bytes())
            return {'name': 'symport-files.zip',
                    'content': base64.b64encode(buffer.getvalue()).decode(),
                    'scope': 'Regular files in selected directory only; subdirectories excluded'}
        if action in ('restore-preview', 'restore'):
            raw = base64.b64decode(data.get('content', ''), validate=True)
            if len(raw) > LIMIT:
                raise ValueError('Archive exceeds 8 MiB')
            digest = hashlib.sha256(raw).hexdigest()
            files = []
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if len(archive.infolist()) > 500 or sum(x.file_size for x in archive.infolist()) > LIMIT:
                    raise ValueError('Archive contents exceed limits')
                seen = set()
                for entry in archive.infolist():
                    if entry.is_dir() or '/' in entry.filename or '\\' in entry.filename or entry.filename in seen:
                        raise ValueError('Restore accepts unique flat filenames only')
                    seen.add(entry.filename)
                    dest = self._path(data['device'], str(PurePosixPath(data.get('path', '')) / entry.filename))
                    if dest == path:
                        raise ValueError('Invalid archive filename')
                    files.append((dest, archive.read(entry)))
            preview = [{'name': dest.name, 'size': len(content), 'conflict': dest.exists()}
                       for dest, content in files]
            if action == 'restore-preview':
                return {'sha256': digest, 'changes': preview}
            if data.get('confirm') is not True or data.get('preview_sha256') != digest:
                raise ValueError('Restore requires confirmation of this exact archive preview')
            if any(x['conflict'] for x in preview):
                raise ValueError('Restore would overwrite existing files; use an empty directory')
            written = []
            try:
                for dest, content in files:
                    with dest.open('xb') as target:
                        written.append(dest)
                        target.write(content)
            except OSError:
                for dest in written:
                    dest.unlink(missing_ok=True)
                raise
            return {'status': 'restored-files-only', 'count': len(written)}
        if action == 'download':
            if not path.is_file() or path.stat().st_size > LIMIT:
                raise ValueError('Only regular files up to 8 MiB can be downloaded')
            return {'name': path.name, 'content': base64.b64encode(path.read_bytes()).decode()}
        if action in ('delete', 'upload', 'mkdir', 'transfer', 'media-upload', 'software-transfer'):
            if data.get('confirm') is not True:
                raise ValueError('Explicit confirmation required')
            if path == self.roots[data['device']]:
                raise ValueError('Cannot modify drive root')
            if action == 'delete':
                if path.is_dir():
                    path.rmdir()  # only empty directories
                else:
                    path.unlink()
            elif action == 'mkdir':
                path.mkdir()
            else:
                content = base64.b64decode(data.get('content', ''), validate=True)
                if len(content) > (64 * 1024 * 1024 if action == 'media-upload' else LIMIT):
                    raise ValueError('File exceeds transfer limit')
                if action == 'media-upload':
                    allowed = {'audio': {'.mp3', '.aac', '.m4a', '.wav', '.mid', '.midi', '.amr'},
                               'video': {'.mp4', '.3gp'}}
                    if path.suffix.lower() not in allowed.get(data.get('kind'), set()):
                        raise ValueError('Неподдерживаемое расширение медиафайла')
                if action == 'software-transfer' and path.suffix.lower() in ('.jar', '.jad'):
                    if path.suffix.lower() == '.jar':
                        with zipfile.ZipFile(io.BytesIO(content)) as archive:
                            if 'META-INF/MANIFEST.MF' not in archive.namelist():
                                raise ValueError('JAR не содержит манифест MIDlet')
                            entry = archive.getinfo('META-INF/MANIFEST.MF')
                            if entry.file_size > 65536 or b'MIDlet-' not in archive.read(entry):
                                raise ValueError('JAR не содержит манифест MIDlet')
                    elif b'MIDlet-Jar-URL:' not in content or b'MIDlet-Name:' not in content:
                        raise ValueError('Некорректный дескриптор JAD')
                elif action in ('transfer', 'software-transfer'):
                    from symport.sis.reader import inspect
                    info = inspect(content)
                    if path.suffix.lower() not in ('.sis', '.sisx') or not all(
                        info[k] for k in ('controller_crc_ok', 'data_crc_ok', 'uid_checksum_ok')
                    ):
                        raise ValueError('Invalid SIS/SISX package')
                # Exclusive creation prevents accidental replacement of phone data.
                created = False
                try:
                    with path.open('xb') as target:
                        created = True
                        target.write(content)
                except OSError:
                    if created:
                        path.unlink(missing_ok=True)
                    raise
            return {'status': 'transferred-not-installed' if action in ('transfer', 'software-transfer') else 'completed'}
        raise ValueError('Unsupported operation for mounted-volume transport')


