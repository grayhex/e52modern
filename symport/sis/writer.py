"""Experimental deterministic SIS 9.x writer for arbitrary installed files.

Profile (matches the reference implementation's canonical package, minus the E32-only rules):
unsigned, English only, stored (uncompressed) data, SHA-1 file hashes, install type SA, no
dependency/prerequisite elements, no conditional blocks, no embedded SIS, creation date fixed
for reproducibility.

NOT validated by MakeSIS/SignSIS or on a phone. Dependencies declared in a .pkg are NOT encoded.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from . import fields as f

MAX_PAYLOAD = 16 * 1024 * 1024
MAX_FILES = 200


@dataclass
class SisFile:
    target: str          # e.g. "!:\\resource\\skins\\e0e52c01\\x.mbm"
    data: bytes


@dataclass
class SisPackage:
    uid: int
    name: str
    vendor: str
    version: tuple[int, int, int] = (1, 0, 0)
    files: list[SisFile] = field(default_factory=list)


def validate(pkg: SisPackage) -> list[str]:
    problems = []
    if not (0 <= pkg.uid <= 0xFFFFFFFF):
        problems.append("package UID out of range")
    for label, text in (("name", pkg.name), ("vendor", pkg.vendor)):
        if not text or len(text) > 128 or any(ord(c) < 32 or ord(c) > 126 for c in text):
            problems.append(f"{label} must be 1..128 printable ASCII characters")
    if any(not (0 <= v <= 32767) for v in pkg.version):
        problems.append("version components must be 0..32767")
    if not pkg.files:
        problems.append("package has no files")
    if len(pkg.files) > MAX_FILES:
        problems.append(f"more than {MAX_FILES} files")
    total = 0
    seen = set()
    for sf in pkg.files:
        t = sf.target
        if not t.startswith(("!:\\", "c:\\", "e:\\", "C:\\", "E:\\")) or "/" in t or ".." in t.split("\\"):
            problems.append(f"invalid install target: {t!r}")
        if any(ord(c) < 32 or ord(c) > 126 for c in t):
            problems.append(f"non-printable-ASCII install target: {t!r}")
        if t.lower() in seen:
            problems.append(f"duplicate install target: {t!r}")
        seen.add(t.lower())
        total += len(sf.data)
    if total > MAX_PAYLOAD:
        problems.append("payload exceeds 16 MiB")
    return problems


def build(pkg: SisPackage) -> bytes:
    problems = validate(pkg)
    if problems:
        raise f.SisFormatError("; ".join(problems))
    version = b"".join(f.u32(v) for v in pkg.version)
    date = f.u16(2004) + b"\0\1"
    datetime = f.field(f.T_DATETIME, f.field(f.T_DATE, date) + f.field(f.T_TIME, b"\0\0\0"))
    info = f.field(
        f.T_INFO,
        f.field(f.T_UID, f.u32(pkg.uid)) + f.string(pkg.vendor) + f.strings(pkg.name)
        + f.strings(pkg.vendor) + f.field(f.T_VERSION, version) + datetime + b"\0\0")

    descriptions = b""
    payloads = b""
    for index, sf in enumerate(pkg.files):
        digest = hashlib.sha1(sf.data).digest()
        desc = (f.string(sf.target) + f.string("")
                + f.field(f.T_HASH, f.u32(1) + f.field(f.T_BLOB, digest))
                + f.u32(1) + f.u32(0) + f.u64(len(sf.data)) + f.u64(len(sf.data)) + f.u32(index))
        descriptions += f.field(f.T_FILE_DESCRIPTION, desc, in_array=True)
        payloads += f.field(f.T_FILE_DATA, f.compressed_raw(sf.data), in_array=True)

    block = f.field(f.T_INSTALL_BLOCK,
                    f.array(f.T_FILE_DESCRIPTION, descriptions) + f.array(f.T_CONTROLLER)
                    + f.array(f.T_IF))
    controller = f.field(
        f.T_CONTROLLER,
        info + f.field(f.T_SUPPORTED_OPTIONS, f.array(f.T_SUPPORTED_OPTION))
        + f.field(f.T_SUPPORTED_LANGUAGES,
                  f.array(f.T_LANGUAGE, f.field(f.T_LANGUAGE, f.u32(1), True)))
        + f.field(f.T_PREREQUISITES, f.array(f.T_DEPENDENCY) + f.array(f.T_DEPENDENCY))
        + f.field(f.T_PROPERTIES, f.array(f.T_PROPERTY)) + block
        + f.field(f.T_DATA_INDEX, f.u32(0)))
    compressed = f.compressed_raw(controller)
    data = f.field(f.T_DATA, f.array(f.T_DATA_UNIT, f.field(f.T_DATA_UNIT, f.array(
        f.T_FILE_DATA, payloads), in_array=True)))

    header = f.u32(f.SIS_UID1) + f.u32(0) + f.u32(pkg.uid)
    header += f.u32(f.uid_checksum(header))
    contents = (f.field(f.T_CONTROLLER_CHECKSUM, f.u16(f.crc16(compressed)))
                + f.field(f.T_DATA_CHECKSUM, f.u16(f.crc16(data))) + compressed + data)
    return header + f.field(f.T_CONTENTS, contents)
