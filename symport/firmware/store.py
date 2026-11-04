"""Server-side store of user-uploaded firmware images (never redistributed, never executed)."""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path

from .index import FirmwareError, build_index, detect

ID_RE = re.compile(r"^[a-f0-9]{16}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()+-]{0,119}$")
MAX_IMAGES = 6
CHUNK = 1 << 20


def max_upload() -> int:
    try:
        return max(1, int(os.getenv("SYMPORT_FIRMWARE_MAX_MB", "1024"))) * 1024 * 1024
    except ValueError:
        return 1024 * 1024 * 1024


class FirmwareStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.lock = threading.RLock()
        self._cache: dict[str, dict] = {}

    # ---- helpers ------------------------------------------------------------------------------
    def _dir(self, key) -> Path:
        if not isinstance(key, str) or not ID_RE.fullmatch(key):
            raise FirmwareError("Invalid firmware ID")
        path = self.root / key
        if not path.is_dir():
            raise FirmwareError("Firmware image not found")
        return path

    def _meta(self, key) -> dict:
        return json.loads((self._dir(key) / "meta.json").read_text(encoding="utf-8"))

    def _write_meta(self, key, meta) -> None:
        directory = self.root / key
        temporary = directory / "meta.json.tmp"
        temporary.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, directory / "meta.json")

    def source_path(self, key) -> Path:
        return self._dir(key) / "source.bin"

    # ---- operations ---------------------------------------------------------------------------
    def list(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        result = []
        for path in sorted(self.root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.is_dir() and ID_RE.fullmatch(path.name):
                try:
                    result.append(self._meta(path.name))
                except (OSError, ValueError):
                    continue
        return result

    def create(self, stream, length: int, name: str, label: str | None = None) -> dict:
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise FirmwareError("File name must be 1–120 safe characters")
        if not 0 < length <= max_upload():
            raise FirmwareError(f"Upload between 1 byte and {max_upload() // 1024 // 1024} MiB")
        with self.lock:
            if len(self.list()) >= MAX_IMAGES:
                raise FirmwareError(f"At most {MAX_IMAGES} firmware images are stored; delete one first")
            key = secrets.token_hex(8)
            directory = self.root / key
            directory.mkdir(parents=True, mode=0o700)
        target = directory / "source.bin"
        try:
            received = 0
            with open(target, "wb") as out:
                while received < length:
                    chunk = stream.read(min(CHUNK, length - received))
                    if not chunk:
                        raise FirmwareError("Upload ended early")
                    out.write(chunk)
                    received += len(chunk)
            kind = detect(target)
        except (FirmwareError, OSError):
            shutil.rmtree(directory, ignore_errors=True)
            raise
        meta = {"id": key, "name": name, "label": (label or "")[:80], "size": length, "kind": kind,
                "created": datetime.now(UTC).isoformat(timespec="seconds"), "status": "indexing",
                "progress": {"done": 0, "total": 0}, "error": None, "files": None}
        self._write_meta(key, meta)
        threading.Thread(target=self._index, args=(key,), daemon=True).start()
        return meta

    def _index(self, key: str) -> None:
        meta = self._meta(key)

        def progress(done, total):
            meta["progress"] = {"done": done, "total": total}
            self._write_meta(key, meta)

        try:
            index = build_index(self.source_path(key), meta["kind"], meta["name"], progress)
            (self.root / key / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            meta.update(status="ready", files=index["counts"]["files"], error=None)
        except (FirmwareError, OSError, ValueError, MemoryError) as exc:
            meta.update(status="failed", error=str(exc)[:300])
        self._write_meta(key, meta)
        self._cache.pop(key, None)

    def index(self, key) -> dict:
        meta = self._meta(key)
        if meta["status"] != "ready":
            raise FirmwareError("Firmware index is " + meta["status"] + (": " + meta["error"] if meta.get("error") else ""))
        cached = self._cache.get(key)
        if cached is None:
            cached = json.loads((self._dir(key) / "index.json").read_text(encoding="utf-8"))
            cached["_lookup"] = {e["path"].lower(): e for e in cached["entries"]}
            if len(self._cache) >= 3:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = cached
        return cached

    def delete(self, key, confirm) -> dict:
        if confirm is not True:
            raise FirmwareError("Explicit confirmation required")
        directory = self._dir(key)
        shutil.rmtree(directory)
        self._cache.pop(key, None)
        return {"deleted": key}
