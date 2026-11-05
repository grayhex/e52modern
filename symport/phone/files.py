"""Capability-based device access. Mounted volumes are never inferred to be phones.

Roots are explicitly enrolled by the operator, not accepted from HTTP clients.
No symlinks, recursive deletion, shell execution or implicit installation.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import secrets
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from . import capabilities
from .contracts import LIMIT


class MountedVolumes:
    def __init__(self, roots: dict[str, str], *, identities: dict[str, str] | None = None):
        self.roots = {k: Path(v).absolute() for k, v in roots.items()}
        self.identities = dict(identities or {})

    def devices(self) -> list[dict]:
        result = []
        for key, root in self.roots.items():
            connected = root.is_dir() and not root.is_symlink()
            usage = shutil.disk_usage(root) if connected else None
            stat = root.stat() if connected else None
            root_identity = hashlib.sha256(str((str(root), stat.st_dev if stat else None, stat.st_ino if stat else None, self.identities.get(key))).encode()).hexdigest()
            row = {"connection_identity": root_identity, "id": key, "transport": "mounted-volume", "connected": connected,
                   "model": None, "rm": None, "firmware": None, "battery": None,
                   "free": usage.free if usage else None,
                   "total": usage.total if usage else None,
                   "storage_scope": "enrolled-filesystem", "signal": None, "usb_mode": None,
                   "imei": None, "evidence": "Operator-enrolled volume; phone identity unavailable"}
            result.append(capabilities.apply(row, self.matrix(root, connected)))
        return result

    @staticmethod
    def matrix(root: Path, connected: bool) -> capabilities.Matrix:
        """Mass Storage proves a readable filesystem and nothing about the phone behind it."""
        m = capabilities.Matrix()
        if not connected:
            return m.rest("error", "volume-probe", "The enrolled drive is not mounted or is a symlink")
        src = "mounted-volume"
        mass = "Mass Storage exposes only the enrolled filesystem (internal mass memory or card)"
        try:
            names = sorted(os.listdir(root))
        except OSError:
            return m.rest("error", src, "The enrolled drive cannot be listed")
        m.available("files.list", src + ":listdir", "Listed the enrolled drive root")
        m.available("storage.read", src + ":disk_usage", "Filesystem usage was read")
        sample = next(
            (n for n in names if (root / n).is_file() and not (root / n).is_symlink()), None
        )
        probed = False
        if sample:
            try:
                with open(root / sample, "rb") as handle:
                    handle.read(1)
                probed = True
            except OSError:
                probed = False
        for op in ("files.download", "media.read"):
            if probed:
                m.available(op, src + ":read", "Read one byte of an existing file")
            else:
                m.untested(op, src, "No readable file on the drive root to probe; first use verifies")
        writable = os.access(root, os.W_OK | os.X_OK)
        for op in ("files.upload", "files.mkdir", "files.delete", "packages.transfer",
                   "contacts.stage"):
            if writable:
                m.untested(op, src + ":os.access",
                           "Writable per OS flags; writes are never probed and need confirmation")
            else:
                m.unsupported(op, src + ":os.access", "The drive is read-only for SymPort")
        for op in ("identity.read", "telemetry.read", "contacts.read", "contacts.write",
                   "calendar.read", "tasks.read", "sms.read", "sms.send"):
            m.unsupported(op, src, mass + "; no phone identity, battery or personal data")
        m.unsupported("packages.opp-push", src, mass)
        m.unsupported("files.stage", src, "Direct writes use files.upload; staging is an OBEX concept")
        return m

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
            if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
                raise ValueError('Only regular files up to 64 MiB can be downloaded')
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
                if len(content) > (64 * 1024 * 1024 if action == 'media-upload' else 32 * 1024 * 1024 if action in ('transfer', 'software-transfer') else LIMIT):
                    raise ValueError('File exceeds transfer limit')
                if action == 'media-upload':
                    allowed = {'audio': {'.mp3', '.aac', '.m4a', '.wav', '.mid', '.midi', '.amr'},
                               'video': {'.mp4', '.3gp'}}
                    if path.suffix.lower() not in allowed.get(data.get('kind'), set()):
                        raise ValueError('Неподдерживаемое расширение медиафайла')
                if action in ('transfer', 'software-transfer'):
                    from symport.catalog.packages import validate_package
                    validate_package(path.name, content)
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


