"""Low-level SIS 9.x field encoding (little-endian TLV with 4-byte padding)."""
from __future__ import annotations

import struct

# field type ids (as used by the reference implementation / SIS 9.x format)
T_STRING, T_ARRAY, T_COMPRESSED, T_VERSION = 1, 2, 3, 4
T_DATE, T_TIME, T_DATETIME, T_UID, T_LANGUAGE = 6, 7, 8, 9, 11
T_CONTENTS, T_CONTROLLER, T_INFO, T_SUPPORTED_LANGUAGES = 12, 13, 14, 15
T_SUPPORTED_OPTIONS, T_PREREQUISITES, T_DEPENDENCY, T_PROPERTIES, T_PROPERTY = 16, 17, 18, 19, 20
T_CERTIFICATE_CHAIN, T_FILE_DESCRIPTION, T_HASH, T_IF = 22, 24, 25, 26
T_INSTALL_BLOCK, T_DATA, T_DATA_UNIT, T_FILE_DATA, T_SUPPORTED_OPTION = 28, 30, 31, 32, 33
T_CONTROLLER_CHECKSUM, T_DATA_CHECKSUM, T_SIGNATURE, T_BLOB = 34, 35, 36, 37
T_SIGNATURE_ALGORITHM, T_SIGNATURE_CHAIN, T_DATA_INDEX, T_CAPABILITIES = 38, 39, 40, 41

SIS_UID1 = 0x10201A7A


class SisFormatError(ValueError):
    pass


def crc16(data: bytes) -> int:
    """Symbian CRC16: polynomial 0x1021, initial 0, no final complement."""
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def uid_checksum(first12: bytes) -> int:
    """Checksum word of a Symbian UID type (three UIDs): even/odd byte CRC16 pair."""
    if len(first12) < 12:
        raise SisFormatError("need 12 bytes of UIDs")
    crc = [0, 0]
    for i in range(12):
        v = crc[i % 2] ^ (first12[i] << 8)
        for _ in range(8):
            v = ((v << 1) ^ 0x1021) & 0xFFFF if v & 0x8000 else (v << 1) & 0xFFFF
        crc[i % 2] = v
    return (crc[1] << 16) | crc[0]


def u32(v: int) -> bytes:
    return struct.pack("<I", v & 0xFFFFFFFF)


def u64(v: int) -> bytes:
    return struct.pack("<Q", v)


def u16(v: int) -> bytes:
    return struct.pack("<H", v & 0xFFFF)


def field(ftype: int, payload: bytes, in_array: bool = False) -> bytes:
    out = b"" if in_array else u32(ftype)
    out += u32(len(payload)) + payload
    out += b"\0" * ((4 - len(payload) % 4) % 4)
    return out


def array(element_type: int, elements: bytes = b"") -> bytes:
    return field(T_ARRAY, u32(element_type) + elements)


def utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def string(text: str) -> bytes:
    return field(T_STRING, utf16(text))


def strings(text: str) -> bytes:
    return array(T_STRING, field(T_STRING, utf16(text), True))


def compressed_raw(data: bytes) -> bytes:
    """Compressed-data field using algorithm 0 (stored)."""
    return field(T_COMPRESSED, u32(0) + u64(len(data)) + data)


class Cursor:
    """Bounds-checked reader over a byte string."""

    def __init__(self, data: bytes, pos: int = 0, end: int | None = None):
        self.data, self.pos, self.end = data, pos, len(data) if end is None else end

    def done(self) -> bool:
        return self.pos >= self.end

    def peek_type(self) -> int | None:
        return struct.unpack_from("<I", self.data, self.pos)[0] if self.pos + 4 <= self.end else None

    def read_u32(self) -> int:
        if self.pos + 4 > self.end:
            raise SisFormatError("truncated integer")
        (v,) = struct.unpack_from("<I", self.data, self.pos)
        self.pos += 4
        return v

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > self.end:
            raise SisFormatError("truncated data")
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def field(self, expect: int | None = None, in_array: bool = False) -> tuple[int, bytes, bytes]:
        """Read one field; returns (type, payload, raw bytes including padding)."""
        start = self.pos
        ftype = -1 if in_array else self.read_u32()
        if expect is not None and not in_array and ftype != expect:
            raise SisFormatError(f"expected field {expect}, found {ftype} at offset {start}")
        length = self.read_u32()
        if length & 0x80000000:
            raise SisFormatError("large (64-bit length) fields are not supported")
        padded = (length + 3) & ~3
        if self.pos + padded > self.end:
            raise SisFormatError(f"field of {length} bytes exceeds its container (offset {start})")
        payload = self.data[self.pos:self.pos + length]
        if any(self.data[self.pos + length:self.pos + padded]):
            raise SisFormatError("non-zero field padding")
        self.pos += padded
        return ftype, payload, self.data[start:self.pos]

    def array(self, expect_element: int | None = None) -> tuple[int, list[bytes]]:
        """Read an array field; returns (element type, element payloads)."""
        _, payload, _ = self.field(T_ARRAY)
        c = Cursor(payload)
        etype = c.read_u32()
        if expect_element is not None and etype != expect_element:
            raise SisFormatError(f"array of {etype}, expected {expect_element}")
        items = []
        while not c.done():
            _, p, _ = c.field(in_array=True)
            items.append(p)
        return etype, items
