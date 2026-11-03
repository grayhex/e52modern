"""Bounded, private media streaming and bulk exports; no phone paths in logs."""

from __future__ import annotations

import base64
import os
import re
import secrets
import time
import zipfile
from pathlib import Path

from .media import CHUNK


def byte_range(value: str | None, size: int) -> tuple[int, int, int]:
    if not value:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or not any(match.groups()) or size == 0:
        raise ValueError("Unsatisfiable range")
    first, last = match.groups()
    if not first:
        start, end = max(0, size - int(last)), size - 1
    else:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise ValueError("Unsatisfiable range")
    return start, end, 206


class MediaDownloads:
    def __init__(self, repo: Path, devices):
        self.root = repo / "build/symport/media-exports"
        self.devices = devices

    def chunks(self, item: dict, start: int, end: int):
        offset = start
        while offset <= end:
            result = self.devices.execute(
                dict(item, action="media-chunk", offset=offset, limit=min(CHUNK, end - offset + 1))
            )
            raw = base64.b64decode(result["content"], validate=True)
            if not raw or len(raw) > min(CHUNK, end - offset + 1):
                raise ValueError("Incomplete media read; refresh the gallery")
            yield raw
            offset += len(raw)

    def export(self, data: dict) -> dict:
        items = data.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 200:
            raise ValueError("Select between 1 and 200 media files")
        checked, seen, total = [], set(), 0
        for item in items:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("path"), str)
                or item["path"] in seen
            ):
                raise ValueError("Choose unique media files")
            seen.add(item["path"])
            request = {k: item.get(k) for k in ("path", "revision")}
            request["device"] = data.get("device")
            meta = self.devices.execute(dict(request, action="media-info"))
            total += meta["size"]
            if total > 1024**3:
                raise ValueError("A bulk download is limited to 1 GiB")
            checked.append((request, meta))
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for old in self.root.glob("*.zip"):
            if old.is_file() and not old.is_symlink() and time.time() - old.stat().st_mtime > 3600:
                old.unlink()
        key = secrets.token_hex(16)
        target = self.root / f"{key}.zip"
        try:
            with target.open("xb") as output:
                os.chmod(target, 0o600)
                with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
                    for request, meta in checked:
                        # MountedVolumes path validation has already rejected traversal.
                        if (
                            meta["path"].startswith("/")
                            or ".." in Path(meta["path"]).parts
                            or "\\" in meta["path"]
                        ):
                            raise ValueError("Invalid media export path")
                        with archive.open(meta["path"], "w", force_zip64=True) as entry:
                            for raw in self.chunks(request, 0, meta["size"] - 1):
                                entry.write(raw)
            self.devices.record("media-export", "success")
            return {"url": f"/api/media/export/{key}", "count": len(items), "size": total}
        except Exception:
            target.unlink(missing_ok=True)
            self.devices.record("media-export", "failed")
            raise

    def archive(self, key: str) -> Path:
        if not re.fullmatch("[a-f0-9]{32}", key):
            raise ValueError("Invalid download")
        file = self.root / f"{key}.zip"
        if not file.is_file() or file.is_symlink() or time.time() - file.stat().st_mtime > 3600:
            raise ValueError("Download expired; select the files again")
        return file
