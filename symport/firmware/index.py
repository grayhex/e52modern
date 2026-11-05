"""Build a searchable index of a firmware ZIP or core ROM image without extracting anything to disk."""
from __future__ import annotations

import hashlib
import mmap
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from symport.analysis import e32

from . import formats
from .rom import RomError, RomImage
from .rpkg import RpkgError, is_rpkg, read_entries

SCHEMA = "symport.firmware/1"
MAX_ENTRIES = 200_000
MAX_TOTAL = 8 * 1024**3
MAX_DEEP = 32 * 1024 * 1024
MAX_HASH = 64 * 1024 * 1024
CHUNK = 1 << 20


class FirmwareError(ValueError):
    pass


def detect(path: Path) -> str:
    """``zip``, ``rpkg`` or ``rom``; anything else is rejected with the reason (never guessed)."""
    with open(path, "rb") as f:
        head = f.read(16)
        if head[:4] == b"PK\x03\x04":
            return "zip"
        if not head:
            raise FirmwareError("Empty file")
        if is_rpkg(head):
            return "rpkg"
        size = path.stat().st_size
        with mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ) as view:
            try:
                RomImage(view)
            except RomError as exc:
                raise FirmwareError("Unsupported firmware file: " + str(exc) + ". Supported: a ZIP of an unpacked Z: tree, an EKA2L1 RPKG v1 "
                                    "or a raw core ROM image. Nokia FPSX/VPL containers and ROFS images are not decoded (no verified "
                                    "specification or sample): unpack them with a dedicated tool first. A file is never assumed "
                                    "compatible because of its extension.") from exc
    return "rom"


def _clean(name: str) -> str | None:
    name = name.replace("\\", "/").lstrip("/")
    if re.match(r"^[A-Za-z]:", name):
        name = name[2:].lstrip("/")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." or "\0" in p for p in parts):
        return None
    return "/".join(parts)


def _root_prefix(names: list[str]) -> str:
    """Directory that holds ``sys/`` (the Z: root) when the archive nests it under extra folders."""
    depth, prefix = None, ""
    for name in names:
        parts = name.split("/")
        for i, part in enumerate(parts[:-1]):
            if part.lower() == "sys" and parts[i + 1].lower() in ("bin", "hash"):
                if depth is None or i < depth:
                    depth, prefix = i, "/".join(parts[:i])
                break
    return prefix


def _entry(path: str, size: int, head: bytes, reader) -> dict:
    kind, basis = formats.classify(path.rsplit("/", 1)[-1], head)
    entry = {"path": "Z:/" + path, "name": path.rsplit("/", 1)[-1], "dir": "Z:/" + path.rsplit("/", 1)[0] if "/" in path else "Z:",
             "size": size, "kind": kind, "basis": basis, "sha256": None}
    uid = formats.uid_header(head)
    if uid:
        entry["uids"] = uid["uids"]
    if size <= MAX_HASH:
        data = reader()
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        if size <= MAX_DEEP:
            try:
                if kind in ("e32-exe", "e32-dll"):
                    entry["e32"] = formats.e32_summary(data)
                elif kind == "mbm":
                    entry["mbm"] = formats.mbm_info(data)
                elif kind == "mif":
                    entry["mif"] = formats.mif_info(data)
            except (ValueError, e32.E32Error) as exc:
                entry["parse_error"] = str(exc)[:160]
    return entry


def build_index(path: Path, kind: str, name: str, progress=None) -> dict:
    entries, skipped = [], []
    if kind == "zip":
        try:
            archive = zipfile.ZipFile(path)
        except zipfile.BadZipFile as exc:
            raise FirmwareError("Not a valid ZIP archive") from exc
        with archive:
            infos = [i for i in archive.infolist() if not i.is_dir()]
            if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_TOTAL:
                raise FirmwareError("Archive exceeds 200000 files or 8 GiB uncompressed")
            names = {}
            for info in infos:
                clean = _clean(info.filename)
                if clean is None:
                    skipped.append({"path": info.filename[:200], "reason": "unsafe path"})
                elif info.flag_bits & 0x1:
                    skipped.append({"path": info.filename[:200], "reason": "encrypted entry"})
                else:
                    names[clean] = info
            prefix = _root_prefix(list(names))
            for i, (clean, info) in enumerate(sorted(names.items()), 1):
                rel = clean[len(prefix) + 1:] if prefix and clean.startswith(prefix + "/") else clean
                if not rel:
                    continue

                def read(info=info):
                    with archive.open(info) as f:
                        data = f.read(info.file_size + 1)
                    if len(data) != info.file_size:
                        raise FirmwareError("ZIP member size differs from its directory entry")
                    return data

                try:
                    head = b""
                    if info.file_size:
                        with archive.open(info) as f:
                            head = f.read(64)
                    entries.append(_entry(rel, info.file_size, head, read))
                except (zipfile.BadZipFile, NotImplementedError, RuntimeError, FirmwareError, OSError) as exc:
                    skipped.append({"path": clean[:200], "reason": "unreadable: " + str(exc)[:80]})
                if progress and i % 200 == 0:
                    progress(i, len(names))
            if progress:
                progress(len(names), len(names))
    elif kind == "rpkg":
        with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as view:
            try:
                header, found = read_entries(view)
            except RpkgError as exc:
                raise FirmwareError("RPKG file rejected: " + str(exc)) from exc
            for i, (rpath, offset, size) in enumerate(sorted(found), 1):
                clean = _clean(rpath)
                if clean is None:
                    skipped.append({"path": rpath[:200], "reason": "unsafe path"})
                    continue
                entries.append(_entry(clean, size, bytes(view[offset:offset + min(size, 64)]), lambda o=offset, s=size: bytes(view[o:o + s])))
                if progress and i % 200 == 0:
                    progress(i, len(found))
            rom_info = {"version": f"{header['major']}.{header['minor']}.{header['build']}", "base": "n/a", "size": path.stat().st_size}
    else:
        with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as view:
            rom = RomImage(view)
            found = list(rom.entries())
            for i, (rel, address, size) in enumerate(sorted(found), 1):
                try:
                    head = rom.read(address, min(size, 64))
                    entries.append(_entry(rel, size, head, lambda a=address, s=size: rom.read(a, s)))
                except RomError as exc:
                    skipped.append({"path": rel[:200], "reason": str(exc)[:80]})
                if progress and i % 200 == 0:
                    progress(i, len(found))
            rom_info = {"version": ".".join(str(x) for x in rom.version), "base": f"{rom.base:#010x}", "size": rom.size}
    by_kind: dict[str, int] = {}
    for e in entries:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    index = {"schema": SCHEMA, "created": datetime.now(UTC).isoformat(timespec="seconds"),
             "source": {"name": name, "kind": kind, "sha256": _sha256_file(path), "size": path.stat().st_size},
             "counts": {"files": len(entries), "bytes": sum(e["size"] for e in entries), "by_kind": by_kind,
                        "e32": sum(1 for e in entries if "e32" in e)},
             "skipped": skipped[:200], "skipped_count": len(skipped), "entries": entries,
             "levels": {"static": "indexed", "boot": "not-tested", "physical_device": "not-tested"},
             "limitations": ["Compressed E32 images show headers only; their imports are unknown.",
                             "A file's presence in this firmware says nothing about what is installed on a phone.",
                             "Indexes are static: nothing was executed, flashed or installed."]}
    if kind == "rom":
        index["rom"] = rom_info
        index["limitations"].append("Core ROM reader is experimental and was verified only on synthetic images.")
    if kind == "rpkg":
        index["rpkg"] = rom_info
        index["limitations"].append("RPKG is read as a container only: contents are indexed, nothing is booted or accepted by an emulator.")
    return index


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def read_member(path: Path, kind: str, entry: dict) -> bytes:
    """Bytes of one indexed file (bounded)."""
    if entry["size"] > MAX_DEEP * 2:
        raise FirmwareError("File is too large to read here")
    rel = entry["path"][3:]
    if kind == "zip":
        with zipfile.ZipFile(path) as archive:
            names = {}
            for info in archive.infolist():
                clean = _clean(info.filename)
                if clean:
                    names[clean] = info
            prefix = _root_prefix(list(names))
            for clean, info in names.items():
                r = clean[len(prefix) + 1:] if prefix and clean.startswith(prefix + "/") else clean
                if r == rel:
                    with archive.open(info) as f:
                        return f.read(info.file_size + 1)[:info.file_size]
        raise FirmwareError("File not found in archive")
    if kind == "rpkg":
        with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as view:
            _header, found = read_entries(view)
            for rpath, offset, size in found:
                if _clean(rpath) == rel:
                    return bytes(view[offset:offset + size])
        raise FirmwareError("File not found in RPKG")
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as view:
        rom = RomImage(view)
        for r, address, size in rom.entries():
            if r == rel:
                return rom.read(address, size)
    raise FirmwareError("File not found in ROM")
