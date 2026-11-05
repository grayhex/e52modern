"""EKA2L1 ``.rpkg`` (v1) reader and writer, written from the format as the emulator's own reader reads it.

Layout (little endian): a 16-byte magic (the letters ``R P K G`` each stored as a 32-bit word), a
header ``<BBHI`` (ROM major, minor, build, entry count), then per entry ``<QQQ`` (attributes, time,
path length in UTF-16 code units), the UTF-16LE path, ``<Q`` data length and the data. Paths start
with ``Z:\\``. Only v1 is written; a v2 file (``R P K 2``) is recognised and refused. Nothing here is
verified against a real emulator: see the converter's ``accepted-by-emulator`` status.
"""
from __future__ import annotations

import struct
from collections.abc import Iterable
from pathlib import Path

MAGIC_V1 = b"".join(struct.pack("<I", ord(c)) for c in "RPKG")
MAGIC_V2 = b"".join(struct.pack("<I", ord(c)) for c in "RPK2")
HEADER = struct.Struct("<BBHI")
ENTRY = struct.Struct("<QQQ")
MAX_ENTRIES = 200_000
MAX_PATH = 512
MAX_FILE = 256 * 1024 * 1024


class RpkgError(ValueError):
    pass


def is_rpkg(head: bytes) -> bool:
    return head[:16] in (MAGIC_V1, MAGIC_V2)


def write_v1(path: Path, entries: Iterable[tuple[str, int, Iterable[bytes]]], count: int, version=(0, 0, 0)) -> int:
    """Write ``(path, size, chunks)`` entries; returns the number of bytes written. Streaming, no whole-image copy."""
    written = 0
    with open(path, "wb") as out:
        for blob in (MAGIC_V1, HEADER.pack(version[0] & 0xFF, version[1] & 0xFF, version[2] & 0xFFFF, count)):
            out.write(blob)
            written += len(blob)
        seen = 0
        for name, size, chunks in entries:
            encoded = name.encode("utf-16-le")
            head = ENTRY.pack(0, 0, len(encoded) // 2) + encoded + struct.pack("<Q", size)
            out.write(head)
            written += len(head)
            sent = 0
            for chunk in chunks:
                out.write(chunk)
                sent += len(chunk)
            if sent != size:
                raise RpkgError("entry data length differs from its declared size")
            written += sent
            seen += 1
        if seen != count:
            raise RpkgError("entry count differs from the header")
    return written


def read_entries(data) -> tuple[dict, list[tuple[str, int, int]]]:
    """Header and ``(path, data_offset, size)`` for each entry of an in-memory/mmap v1 image. Bounds-checked."""
    if len(data) < 24 or bytes(data[:16]) not in (MAGIC_V1, MAGIC_V2):
        raise RpkgError("not an RPKG file")
    if bytes(data[:16]) == MAGIC_V2:
        raise RpkgError("RPKG v2 is recognised but not supported by this reader")
    major, minor, build, count = HEADER.unpack_from(data, 16)
    position, entries = 24, []
    while position < len(data):
        if len(entries) >= MAX_ENTRIES:
            raise RpkgError("too many RPKG entries")
        if position + ENTRY.size > len(data):
            raise RpkgError("truncated RPKG entry header")
        _attrib, _time, length = ENTRY.unpack_from(data, position)
        position += ENTRY.size
        if not 0 < length <= MAX_PATH or position + 2 * length + 8 > len(data):
            raise RpkgError("damaged RPKG path")
        name = bytes(data[position:position + 2 * length]).decode("utf-16-le", errors="replace")
        position += 2 * length
        (size,) = struct.unpack_from("<Q", data, position)
        position += 8
        if size > MAX_FILE or position + size > len(data):
            raise RpkgError("RPKG entry data outside the file")
        entries.append((name, position, size))
        position += size
    if count != len(entries):
        raise RpkgError("RPKG entry count differs from the header")
    return {"major": major, "minor": minor, "build": build, "count": count}, entries
