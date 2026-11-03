"""Cross-check SymPort's E32 analysis against the independent inspector of symbian-platform.

``symbian inspect --format e32`` (native C++ code of the SDK) and ``symport.analysis.e32`` were
written independently; agreement on the same image is evidence that the header is read correctly.
It is NOT evidence about firmware acceptance. The SDK inspector only accepts its own narrow profile
(uncompressed EKA2 V-header images produced by its converter) and reports Unimplemented otherwise.
"""
from __future__ import annotations

import struct
from pathlib import Path

from symport.analysis import e32 as e32mod
from symport.backends import modern_sdk
from symport.report import FAIL, PASS, SKIP, UNKNOWN, Report

ARCH = {"armv5": "armv5t", "armv6": "armv6", "armv4": "armv4"}


def compare(info: dict, raw: bytes, sdk_meta: dict) -> list[tuple[str, object, object, bool]]:
    """Field-by-field comparison; returns (field, symport, sdk, equal)."""
    mine_caps = 0
    for name in info.get("capabilities") or []:
        mine_caps |= 1 << e32mod.CAPABILITIES.index(name)
    rows = [
        ("uid3", info["uid3"], sdk_meta.get("uid3")),
        ("secure_id", int(info["secure_id"], 16) if info.get("secure_id") else None, sdk_meta.get("secure_id")),
        ("flags", int(info["flags"], 16), sdk_meta.get("flags")),
        ("kernel", info["kernel"], sdk_meta.get("kernel")),
        ("architecture", ARCH.get(info["cpu"], info["cpu"]), sdk_meta.get("architecture")),
        ("code_size", info["code_size"], sdk_meta.get("code_size")),
        ("data_size", info["data_size"], sdk_meta.get("data_size")),
        ("bss_size", info["bss_size"], sdk_meta.get("bss_size")),
        ("entry_offset", info["entry_point_offset"], sdk_meta.get("entry_offset")),
        ("header_size", info["code_offset"], sdk_meta.get("header_size")),
        ("header_crc", struct.unpack_from("<I", raw, 20)[0], sdk_meta.get("header_crc")),
        ("capabilities", mine_caps, sdk_meta.get("capabilities")),
        ("dll", info["is_dll"], sdk_meta.get("dll")),
        ("export_count", info["export_count"], len(sdk_meta.get("exports", []) or [])),
    ]
    mine_imp = info.get("imports")
    sdk_imp = sdk_meta.get("imports")
    if isinstance(mine_imp, list) and isinstance(sdk_imp, list):
        rows.append(("import_dll_count", len(mine_imp), len(sdk_imp)))
    return [(k, a, b, a == b) for k, a, b in rows]


def crosscheck_file(path: Path, info: dict, rep: Report) -> None:
    sdk = modern_sdk.locate()
    if not sdk.available:
        rep.add("crosscheck.e32", SKIP, "symbian CLI not found: independent cross-check not performed", "environment")
        return
    r, parsed = sdk.json(["inspect", "--format", "e32", str(path)], timeout=120)
    meta = (parsed or {}).get("result", {}).get("metadata") if parsed else None
    if not r.ok or not meta:
        msg = modern_sdk.summarize(r, parsed)
        # Unimplemented = the SDK inspector does not cover this image profile; not a disagreement.
        rep.add("crosscheck.e32", UNKNOWN,
                f"symbian inspect could not evaluate this image (outside its supported profile?): {msg}",
                "environment")
        return
    rows = compare(info, Path(path).read_bytes(), meta)
    bad = [(k, a, b) for k, a, b, ok in rows if not ok]
    rep.add("crosscheck.e32", FAIL if bad else PASS,
            f"{len(rows)} fields agree with `symbian inspect --format e32`" if not bad
            else "DISAGREEMENT with symbian-platform inspector: " + "; ".join(
                f"{k}: symport={a!r} sdk={b!r}" for k, a, b in bad),
            "environment", fields=len(rows), version=sdk.version())
