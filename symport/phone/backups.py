"""Server-side store of full file backups made through the Workbench.

The browser never supplies filesystem paths: backup directories live under one server-controlled
root and are addressed by generated ids. Deleting only ever removes a directory inside that root
that contains a SymPort manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,80}$")
MAX_LISTED = 200


class BackupStoreError(ValueError):
    pass


def default_root(repo: Path) -> Path:
    env = os.environ.get("SYMPORT_BACKUP_ROOT")
    return Path(env) if env else Path(repo) / "build" / "symport" / "backups"


class BackupStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    # ---- ids and paths
    def new_id(self, device: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", str(device)).strip("-_")[:40] or "volume"
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        bid = f"{stem}-{stamp}"
        n = 1
        while (self.root / bid).exists():
            n += 1
            bid = f"{stem}-{stamp}-{n}"
        return bid

    def path(self, backup_id: object) -> Path:
        if not isinstance(backup_id, str) or not ID_RE.fullmatch(backup_id):
            raise BackupStoreError("Некорректный идентификатор копии")
        return self.root / backup_id

    def existing(self, backup_id: object) -> Path:
        p = self.path(backup_id)
        if p.is_symlink() or not (p / "manifest.json").is_file():
            raise BackupStoreError("Копия не найдена")
        return p

    # ---- progress (counters only: no file names, no paths)
    def progress_path(self, backup_id: str) -> Path:
        return self.root / ".progress" / f"{self.path(backup_id).name}.json"

    def progress(self, backup_id: str) -> dict | None:
        try:
            data = json.loads(self.progress_path(backup_id).read_text(encoding="utf-8"))
        except (OSError, ValueError, BackupStoreError):
            return None
        return {k: data.get(k) for k in ("done", "total", "bytes", "bytes_total")} if isinstance(data, dict) else None

    # ---- listing
    def list(self) -> list[dict]:
        if not self.root.is_dir() or self.root.is_symlink():
            return []
        rows = []
        for d in sorted(self.root.iterdir(), reverse=True)[:MAX_LISTED * 2]:
            if d.name.startswith(".") or d.is_symlink() or not d.is_dir() or not ID_RE.fullmatch(d.name):
                continue
            mp = d / "manifest.json"
            if not mp.is_file():
                rows.append({"id": d.name, "state": "incomplete", "created": None, "label": None,
                             "files": None, "bytes": None, "complete": False, "skipped": None,
                             "manifest_ok": False})
                continue
            try:
                raw = mp.read_bytes()
                m = json.loads(raw)
                sp = d / "manifest.sha256"
                ok = sp.is_file() and sp.read_text(encoding="ascii", errors="replace").split()[0] \
                    == hashlib.sha256(raw).hexdigest()
                rows.append({"id": d.name, "state": "ready", "created": m.get("created"),
                             "label": m.get("source_label"), "files": m.get("totals", {}).get("files"),
                             "bytes": m.get("totals", {}).get("bytes"), "complete": bool(m.get("complete")),
                             "skipped": len(m.get("skipped", [])), "manifest_ok": ok})
            except (OSError, ValueError, IndexError):
                rows.append({"id": d.name, "state": "unreadable", "created": None, "label": None,
                             "files": None, "bytes": None, "complete": False, "skipped": None,
                             "manifest_ok": False})
        rows.sort(key=lambda r: (r["created"] or "", r["id"]), reverse=True)
        return rows[:MAX_LISTED]

    # ---- deletion
    def delete(self, backup_id: object, confirm: object) -> dict:
        if confirm is not True:
            raise BackupStoreError("Подтвердите удаление копии")
        d = self.path(backup_id)
        if d.is_symlink() or not d.is_dir():
            raise BackupStoreError("Копия не найдена")
        # Only SymPort backups (manifest present) or abandoned partial copies (no manifest, ours by id).
        shutil.rmtree(d)
        self.progress_path(d.name).unlink(missing_ok=True)
        return {"deleted": d.name}


def write_progress(path: Path, done: int, total: int, nbytes: int, bytes_total: int) -> None:
    """Atomically replace a small JSON progress file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".p-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"done": done, "total": total, "bytes": nbytes, "bytes_total": bytes_total}, f)
    os.replace(tmp, path)
