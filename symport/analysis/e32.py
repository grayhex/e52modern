"""E32 image (Symbian EXE/DLL) header and import analysis.

Header layout follows the public Symbian ``e32image.h`` structure as exercised by the
reference implementation in symbian-platform (cpp/symbian/e32/e32.cc). Scope: uncompressed
EKA2 images with the V header for full import decoding; compressed images are reported with
header facts only. A parsed header is NOT a statement that a firmware loader accepts the image.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from symport.sis.fields import uid_checksum

CRC_INITIALISER = 0xC90FDAA2

COMPRESSION = {0: "none", 0x101F7AFC: "deflate", 0x102822AA: "bytepair"}
CPU = {0: "unknown", 0x1000: "x86", 0x2000: "armv4", 0x2001: "armv5", 0x2002: "armv6", 0x4000: "mcore"}
CAPABILITIES = [
    "TCB", "CommDD", "PowerMgmt", "MultimediaDD", "ReadDeviceData", "WriteDeviceData", "DRM",
    "TrustedUI", "ProtServ", "DiskAdmin", "NetworkControl", "AllFiles", "SwEvent",
    "NetworkServices", "LocalServices", "ReadUserData", "WriteUserData", "Location",
    "SurroundingsDD", "UserEnvironment",
]
# Capabilities a user can grant at install time on a phone (self-signed packages): per public
# Symbian platform-security documentation. Others need a certificate the phone trusts.
USER_GRANTABLE = {"NetworkServices", "LocalServices", "ReadUserData", "WriteUserData", "Location",
                  "UserEnvironment"}

_DLLNAME = re.compile(r"^(?P<stem>.+?)(?:\{(?P<ver>[0-9a-fA-F]{8})\})?(?:\[(?P<uid>[0-9a-fA-F]{8})\])?"
                      r"\.(?P<ext>dll|exe)$", re.I)


class E32Error(ValueError):
    pass


@dataclass
class ImportBlock:
    dll: str
    stem: str
    uid: int | None
    ordinals: list[int] = field(default_factory=list)
    count: int = 0

    def to_dict(self) -> dict:
        return {"dll": self.dll, "name": self.stem.lower() + ".dll",
                "uid": None if self.uid is None else f"{self.uid:#010x}",
                "count": self.count, "ordinals": self.ordinals}


def header_crc(data: bytes, header_size: int) -> int:
    crc = 0
    for i in range(header_size):
        byte = (CRC_INITIALISER >> ((i - 20) * 8)) & 0xFF if 20 <= i < 24 else data[i]
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return crc


def is_e32(data: bytes) -> bool:
    return len(data) >= 24 and data[16:20] == b"EPOC"


def capability_names(low: int, high: int = 0) -> list[str]:
    bits = low | (high << 32)
    return [n for i, n in enumerate(CAPABILITIES) if bits >> i & 1]


def analyze(data: bytes) -> dict:
    if not is_e32(data):
        raise E32Error("not an E32 image (missing 'EPOC' signature at offset 16)")
    if len(data) < 128:
        raise E32Error("truncated E32 header")
    u = lambda o: struct.unpack_from("<I", data, o)[0]  # noqa: E731
    h = lambda o: struct.unpack_from("<H", data, o)[0]  # noqa: E731
    flags = u(44)
    hdr_fmt = (flags >> 24) & 0xF
    imp_fmt = (flags >> 28) & 0xF
    eptype = (flags >> 5) & 0x7
    abi = (flags >> 3) & 0x3
    info: dict = {
        "uids": [f"{u(0):#010x}", f"{u(4):#010x}", f"{u(8):#010x}"],
        "uid3": u(8),
        "uid_checksum_ok": u(12) == uid_checksum(data[:12]),
        "flags": f"{flags:#010x}",
        "is_dll": bool(flags & 1),
        "header_format": {0: "original", 1: "J", 2: "V"}.get(hdr_fmt, f"unknown({hdr_fmt})"),
        "import_format": {0: "pe", 1: "elf", 2: "pe2"}.get(imp_fmt, f"unknown({imp_fmt})"),
        "abi": {0: "gcc98r2", 1: "eabi"}.get(abi, f"unknown({abi})"),
        "kernel": {0: "eka1", 1: "eka2"}.get(eptype, f"unknown({eptype})"),
        "module_version": f"{u(24) >> 16}.{u(24) & 0xFFFF}",
        "compression": COMPRESSION.get(u(28), f"unknown({u(28):#x})"),
        "code_size": u(48), "data_size": u(52), "bss_size": u(68),
        "heap_min": u(56), "heap_max": u(60), "stack_size": u(64),
        "entry_point_offset": u(72), "dll_ref_count": u(84),
        "export_count": u(92), "code_offset": u(100),
        "cpu": CPU.get(h(122), f"unknown({h(122):#x})"), "cpu_raw": f"{h(122):#06x}",
        "file_size": len(data),
    }
    header_size = u(100)
    info["header_crc_ok"] = (header_size <= len(data) and u(20) == header_crc(data, header_size)
                             if header_size >= 24 else None)
    if hdr_fmt == 2 and len(data) >= 148:
        info["secure_id"] = f"{u(128):#010x}"
        info["vendor_id"] = f"{u(132):#010x}"
        caps = capability_names(u(136), u(140))
        info["capabilities"] = caps
        info["restricted_capabilities"] = [c for c in caps if c not in USER_GRANTABLE]
    else:
        info["secure_id"] = info["vendor_id"] = None
        info["capabilities"] = None
        info["restricted_capabilities"] = None
    info["imports"] = None
    info["imports_note"] = None
    if info["compression"] != "none":
        info["imports_note"] = ("image is compressed; imports not decoded (headers only). "
                                "Supply an uncompressed image (e.g. from a firmware dump) for import analysis.")
    elif info["dll_ref_count"]:
        try:
            info["imports"] = [b.to_dict() for b in _imports(data, info, u)]
        except (E32Error, struct.error) as e:
            info["imports_note"] = f"import table could not be decoded: {e}"
    else:
        info["imports"] = []
    return info


def _cstr(section: bytes, off: int) -> str:
    end = section.find(b"\0", off)
    if off < 0 or end < 0:
        raise E32Error("unterminated import name")
    return section[off:end].decode("ascii", errors="replace")


def _imports(data: bytes, info: dict, u) -> list[ImportBlock]:
    header_size = u(100)
    import_off = u(108)
    if import_off == 0 or import_off + 4 > len(data):
        raise E32Error("import offset outside file")
    end = u(112) or u(116) or len(data)
    section = data[import_off:end]
    if len(section) < 4 or struct.unpack_from("<I", section, 0)[0] > len(section):
        raise E32Error("bad import section size")
    code = data[header_size:header_size + info["code_size"]]
    blocks: list[ImportBlock] = []
    pos = 4
    for _ in range(info["dll_ref_count"]):
        name_off, count = struct.unpack_from("<II", section, pos)
        pos += 8
        name = _cstr(section, name_off)
        m = _DLLNAME.match(name)
        blk = ImportBlock(dll=name, stem=m.group("stem") if m else name,
                          uid=int(m.group("uid"), 16) if m and m.group("uid") else None, count=count)
        if count > 4096 or pos + 4 * count > len(section):
            raise E32Error("implausible import count")
        for i in range(count):
            val = struct.unpack_from("<I", section, pos + 4 * i)[0]
            if info["import_format"] == "elf":
                if val + 4 > len(code):
                    raise E32Error("import slot outside code")
                blk.ordinals.append(struct.unpack_from("<I", code, val)[0] & 0xFFFF)
            else:
                blk.ordinals.append(val & 0xFFFF)
        pos += 4 * count
        blocks.append(blk)
    return blocks
