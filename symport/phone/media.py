"""Read-only media access over the existing mounted-volume/PC Bridge contract."""

from __future__ import annotations

import base64
import io
import os
import stat
from pathlib import Path

KINDS = {
    "photo": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
    "video": {".mp4", ".3gp", ".mov", ".avi", ".m4v"},
    "audio": {".mp3", ".aac", ".m4a", ".wav", ".mid", ".midi", ".amr", ".wma"},
}
MIMES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".mp4": "video/mp4",
    ".3gp": "video/3gpp",
    ".mov": "video/quicktime",
    ".m4v": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".aac": "audio/aac",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    ".amr": "audio/amr",
    ".wma": "audio/x-ms-wma",
}
CHUNK = 256 * 1024


def kind(path: Path) -> str | None:
    return next((k for k, extensions in KINDS.items() if path.suffix.lower() in extensions), None)


def describe(path: Path, relative: str) -> dict:
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not kind(path):
        raise ValueError("Choose a regular photo, video or audio file")
    return {
        "path": relative,
        "name": path.name,
        "kind": kind(path),
        "size": info.st_size,
        "modified": info.st_mtime,
        "revision": f"{info.st_size}-{info.st_mtime_ns}",
        "mime": MIMES[path.suffix.lower()],
    }


def execute(volumes, data: dict) -> dict:
    path = volumes._path(data["device"], data.get("path", ""))
    action = data["action"]
    if action == "media-list":
        if not path.is_dir():
            raise ValueError("Choose a media folder")
        entries, pending, examined, skipped = [], [(path, 0)], 0, 0
        truncated = False
        while pending and not truncated:
            folder, depth = pending.pop()
            try:
                with os.scandir(folder) as children:
                    for entry in children:
                        examined += 1
                        if examined > 25000 or len(entries) >= 5000:
                            truncated = True
                            break
                        relative = (
                            Path(entry.path).relative_to(volumes.roots[data["device"]]).as_posix()
                        )
                        try:
                            child = volumes._path(data["device"], relative)
                            if child.is_dir():
                                if depth < 12:
                                    pending.append((child, depth + 1))
                                else:
                                    skipped += 1
                            elif kind(child) and child.is_file():
                                entries.append(describe(child, relative))
                        except (OSError, ValueError):
                            skipped += 1
            except OSError:
                skipped += 1
        return {
            "items": entries,
            "truncated": truncated,
            "skipped": skipped,
            "scope": "Files in the selected enrolled volume; protected phone storage is excluded",
        }
    meta = describe(path, data["path"])
    if data.get("revision") != meta["revision"]:
        raise ValueError("The file changed. Refresh the gallery before downloading it")
    if action == "media-info":
        return meta
    if action == "media-chunk":
        offset, limit = data.get("offset"), data.get("limit", CHUNK)
        if (
            type(offset) is not int
            or type(limit) is not int
            or offset < 0
            or not 1 <= limit <= CHUNK
        ):
            raise ValueError("Invalid media range")
        with path.open("rb") as source:
            info = os.fstat(source.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or f"{info.st_size}-{info.st_mtime_ns}" != meta["revision"]
            ):
                raise ValueError("The file changed. Refresh the gallery")
            source.seek(offset)
            content = source.read(limit)
        if describe(path, data["path"])["revision"] != meta["revision"]:
            raise ValueError("The file changed while reading")
        return {"content": base64.b64encode(content).decode(), "size": meta["size"]}
    if action == "media-thumbnail":
        if meta["kind"] != "photo":
            return {
                "status": "unsupported",
                "reason": "Video/audio artwork is unavailable; open the media preview",
            }
        if meta["size"] > 16 * 1024 * 1024:
            return {"status": "unsupported", "reason": "Photo exceeds the 16 MiB thumbnail limit"}
        try:
            from PIL import Image, ImageOps

            with path.open("rb") as source, Image.open(source) as image:
                if image.width * image.height > 24_000_000:
                    raise ValueError("Photo dimensions exceed the thumbnail limit")
                width, height = image.size
                image = ImageOps.exif_transpose(image)
                image.thumbnail((320, 240))
                image = image.convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, "JPEG", quality=78)  # no EXIF, GPS or original metadata
            if describe(path, data["path"])["revision"] != meta["revision"]:
                raise ValueError("The photo changed while generating the thumbnail")
            return {
                "status": "available",
                "content": base64.b64encode(buffer.getvalue()).decode(),
                "width": width,
                "height": height,
                "mime": "image/jpeg",
            }
        except ImportError:
            return {
                "status": "unsupported",
                "reason": "Install the media extra on the PC Bridge to generate thumbnails",
            }
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError("Cannot decode this photo; download the original file") from exc
    raise ValueError("Unsupported media operation")
