"""File-format sniffing for Symbian firmware contents.

Each parser is bounds-checked and works on bytes already in memory. Kinds are derived from magic
numbers when a magic exists (E32 image, UID-typed files, MBM, MIF, SIS) and from the extension
otherwise; ``basis`` says which, so extension-only guesses are never presented as facts.
"""
from __future__ import annotations

import struct

from symport.analysis import e32
from symport.sis.fields import SIS_UID1, uid_checksum

UID_EXE, UID_DLL = 0x1000007A, 0x10000079
UID_FILE_STORE, UID_MBM = 0x10000037, 0x10000042
UID_APP = 0x100039CE
MIF_MAGIC = 0x34232342
MAX_BITMAPS = 4096

EXTENSION_KINDS = {
    "rsc": "resource", "r01": "resource", "r02": "resource", "r03": "resource", "mbm": "mbm", "mif": "mif",
    "dll": "e32-dll", "exe": "e32-exe", "sis": "sis", "sisx": "sis", "ini": "text", "txt": "text", "xml": "text",
    "html": "text", "css": "text", "js": "text", "png": "image", "jpg": "image", "jpeg": "image", "gif": "image",
    "bmp": "image", "svg": "image", "mp3": "audio", "aac": "audio", "wav": "audio", "mid": "audio", "amr": "audio",
    "ttf": "font", "otf": "font", "pfr": "font", "mdl": "plugin", "prt": "plugin", "agt": "plugin", "fsy": "plugin",
    "pdd": "plugin", "ldd": "plugin", "pdl": "plugin", "csy": "plugin", "tsy": "plugin", "nif": "plugin",
    "dat": "data", "bin": "data", "idx": "data", "db": "data", "cfg": "data", "dta": "data",
}
KINDS = ("e32-exe", "e32-dll", "rom-image-exe", "rom-image-dll", "mbm", "mif", "resource", "sis", "plugin", "text",
         "image", "audio", "font", "data", "uid-typed", "other")


def uid_header(data: bytes) -> dict | None:
    """The first four words as a Symbian UID type, when its checksum validates."""
    if len(data) < 16:
        return None
    uid1, uid2, uid3, check = struct.unpack_from("<4I", data, 0)
    if uid1 == 0 and uid2 == 0 and uid3 == 0:
        return None
    if check != uid_checksum(data[:12]):
        return None
    return {"uids": [f"{uid1:#010x}", f"{uid2:#010x}", f"{uid3:#010x}"], "uid1": uid1, "uid2": uid2, "uid3": uid3}


def extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def classify(name: str, head: bytes) -> tuple[str, str]:
    """(kind, basis) from the first bytes of a file and its name."""
    if len(head) >= 24 and head[16:20] == b"EPOC":
        return ("e32-dll" if len(head) >= 48 and struct.unpack_from("<I", head, 44)[0] & 1 else "e32-exe"), "magic"
    uid = uid_header(head)
    if uid:
        if uid["uid1"] == UID_FILE_STORE and uid["uid2"] == UID_MBM:
            return "mbm", "magic"
        if uid["uid1"] == SIS_UID1:
            return "sis", "magic"
        if uid["uid1"] in (UID_EXE, UID_DLL):
            return ("rom-image-exe" if uid["uid1"] == UID_EXE else "rom-image-dll"), "magic"
    if len(head) >= 4 and struct.unpack_from("<I", head, 0)[0] == MIF_MAGIC:
        return "mif", "magic"
    kind = EXTENSION_KINDS.get(extension(name))
    if kind:
        return kind, "extension"
    return ("uid-typed", "magic") if uid else ("other", "none")


def mbm_info(data: bytes) -> dict:
    """Multi-bitmap file: bitmap count and per-bitmap geometry (SEpocBitmapHeader, 40 bytes)."""
    if len(data) < 24:
        raise ValueError("truncated MBM")
    trailer = struct.unpack_from("<I", data, 16)[0]
    if trailer + 4 > len(data):
        raise ValueError("MBM trailer outside file")
    count = struct.unpack_from("<I", data, trailer)[0]
    if count > MAX_BITMAPS or trailer + 4 + 4 * count > len(data):
        raise ValueError("implausible MBM bitmap count")
    bitmaps = []
    for i in range(min(count, 64)):
        offset = struct.unpack_from("<I", data, trailer + 4 + 4 * i)[0]
        if offset + 40 > len(data):
            raise ValueError("MBM bitmap header outside file")
        size, struct_size, width, height, _tw, _th, bpp, color, palette, compression = struct.unpack_from("<10I", data, offset)
        if struct_size != 40:
            raise ValueError("unexpected MBM bitmap header size")
        bitmaps.append({"width": width, "height": height, "bits_per_pixel": bpp, "color": bool(color), "palette_entries": palette,
                        "compression": {0: "none", 1: "rle8", 2: "rle12", 3: "rle16", 4: "rle24", 5: "rle32"}.get(compression, str(compression)),
                        "data_size": size})
    return {"count": count, "bitmaps": bitmaps, "listed": len(bitmaps)}


def mif_info(data: bytes) -> dict:
    if len(data) < 12 or struct.unpack_from("<I", data, 0)[0] != MIF_MAGIC:
        raise ValueError("not a MIF file")
    return {"magic": f"{MIF_MAGIC:#010x}", "format_version": struct.unpack_from("<I", data, 4)[0],
            "note": "MIF icon directory is not decoded; magic and version word observed in Nokia mifconv output."}


def e32_summary(data: bytes) -> dict:
    """Trimmed E32 analysis for indexes (full analysis stays available per file)."""
    a = e32.analyze(data)
    return {"uids": a["uids"], "secure_id": a["secure_id"], "vendor_id": a["vendor_id"], "capabilities": a["capabilities"],
            "restricted_capabilities": a["restricted_capabilities"], "is_dll": a["is_dll"], "kernel": a["kernel"],
            "cpu": a["cpu"], "abi": a["abi"], "compression": a["compression"], "module_version": a["module_version"],
            "header_format": a["header_format"], "export_count": a["export_count"], "code_size": a["code_size"],
            "heap_min": a["heap_min"], "heap_max": a["heap_max"], "stack_size": a["stack_size"],
            "imports": None if a["imports"] is None else [i["name"] for i in a["imports"]],
            "imports_note": a["imports_note"], "header_crc_ok": a["header_crc_ok"], "uid_checksum_ok": a["uid_checksum_ok"]}
