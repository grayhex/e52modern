"""Structural SIS 9.x inspector.

Verifies UID checksum, controller/data CRC16, decodes the controller (stored or zlib-deflated),
lists installed files and checks every embedded file against its SHA-1 hash. It does not verify
signature chains cryptographically and does not decode conditional blocks or embedded SIS.
It is NOT a substitute for installing the package on a phone.
"""
from __future__ import annotations

import hashlib
import struct
import zlib

from . import fields as f
from .fields import Cursor, SisFormatError


def _decompress(payload: bytes) -> bytes:
    if len(payload) < 12:
        raise SisFormatError("truncated compressed field")
    algo = struct.unpack_from("<I", payload, 0)[0]
    size = struct.unpack_from("<Q", payload, 4)[0]
    body = payload[12:]
    if algo == 0:
        if size != len(body):
            raise SisFormatError("stored data length mismatch")
        return body
    if algo == 1:
        try:
            out = zlib.decompress(body)
        except zlib.error:
            try:
                out = zlib.decompress(body, -15)
            except zlib.error as e:
                raise SisFormatError(f"cannot inflate data: {e}") from e
        if len(out) != size:
            raise SisFormatError("inflated data length mismatch")
        return out
    raise SisFormatError(f"unknown compression algorithm {algo}")


def _strings(array_payload_fields: list[bytes]) -> list[str]:
    return [p.decode("utf-16-le", errors="replace") for p in array_payload_fields]


def inspect(data: bytes) -> dict:
    """Return a dict describing the package. Raises SisFormatError for malformed input."""
    return _inspect(data)[0]


def extract(data: bytes) -> dict[str, bytes]:
    """Embedded file contents by install target (single-data-unit packages only)."""
    info, blobs = _inspect(data)
    if info["data_units"] != 1:
        raise SisFormatError("extraction supports single-data-unit packages only")
    return {fi["target"]: blobs[fi["file_index"]] for fi in info["files"]
            if fi["file_index"] < len(blobs)}


def _inspect(data: bytes) -> tuple[dict, list[bytes]]:
    if len(data) < 16:
        raise SisFormatError("truncated UID header")
    uid1, uid2, uid3, chk = struct.unpack_from("<4I", data, 0)
    if uid1 != f.SIS_UID1:
        raise SisFormatError(f"not a SIS 9.x file (UID1 {uid1:#010x}, expected {f.SIS_UID1:#010x})")
    out: dict = {"uid1": uid1, "uid2": uid2, "uid3": uid3, "size": len(data)}
    out["uid_checksum_ok"] = chk == f.uid_checksum(data[:12])

    root = Cursor(data, 16)
    _, contents_payload, _ = root.field(f.T_CONTENTS)
    if not root.done():
        out["trailing_bytes"] = len(data) - root.pos
    c = Cursor(contents_payload)
    _, crc_c, _ = c.field(f.T_CONTROLLER_CHECKSUM)
    _, crc_d, _ = c.field(f.T_DATA_CHECKSUM)
    _, comp_payload, comp_raw = c.field(f.T_COMPRESSED)
    _, data_payload, data_raw = c.field(f.T_DATA)
    if not c.done():
        raise SisFormatError("unsupported extra top-level fields (embedded controllers?)")
    out["controller_crc_ok"] = struct.unpack("<H", crc_c[:2])[0] == f.crc16(comp_raw)
    out["data_crc_ok"] = struct.unpack("<H", crc_d[:2])[0] == f.crc16(data_raw)

    controller_bytes = _decompress(comp_payload)
    cc = Cursor(controller_bytes)
    _, ctrl, _ = cc.field(f.T_CONTROLLER)
    k = Cursor(ctrl)
    _, info, _ = k.field(f.T_INFO)
    ic = Cursor(info)
    _, uid_payload, _ = ic.field(f.T_UID)
    package_uid = struct.unpack("<I", uid_payload)[0]
    _, vendor_unique, _ = ic.field(f.T_STRING)
    _, names = ic.array(f.T_STRING)
    _, vendors = ic.array(f.T_STRING)
    _, version, _ = ic.field(f.T_VERSION)
    out["package"] = {
        "uid": package_uid, "uid_matches_header": package_uid == uid3,
        "names": _strings(names), "vendor_unique_name": vendor_unique.decode("utf-16-le"),
        "vendor_names": _strings(vendors),
        "version": list(struct.unpack("<3I", version[:12])) if len(version) >= 12 else None,
    }

    signature_count = 0
    files: list[dict] = []
    deps_declared = 0
    dep_uids: list[int] = []
    unparsed: list[int] = []
    while not k.done():
        t = k.peek_type()
        if t == f.T_INSTALL_BLOCK:
            _, block, _ = k.field(f.T_INSTALL_BLOCK)
            bc = Cursor(block)
            _, descs = bc.array(f.T_FILE_DESCRIPTION)
            for d in descs:
                files.append(_file_description(d))
            for _ in range(2):  # embedded controllers, conditional blocks: listed, not decoded
                if not bc.done():
                    _, items = bc.array()
                    if items:
                        unparsed.append(len(items))
        elif t == f.T_PREREQUISITES:
            _, pre, _ = k.field(f.T_PREREQUISITES)
            pc = Cursor(pre)
            while not pc.done():
                _, items = pc.array(f.T_DEPENDENCY)
                deps_declared += len(items)
                for it in items:
                    ic2 = Cursor(it)
                    if ic2.peek_type() == f.T_UID:
                        _, p, _ = ic2.field(f.T_UID)
                        dep_uids.append(struct.unpack("<I", p)[0])
        elif t == f.T_SIGNATURE_CHAIN:
            _, sig, _ = k.field(f.T_SIGNATURE_CHAIN)
            sc = Cursor(sig)
            _, items = sc.array(f.T_SIGNATURE)
            signature_count += len(items)
        else:
            k.field()  # options, languages, properties, data index: skipped
    out["files"] = files
    out["signed"] = signature_count > 0
    out["signature_count"] = signature_count
    out["dependencies"] = {"declared": deps_declared, "uids_best_effort": dep_uids}
    if unparsed:
        out["undecoded_blocks"] = unparsed

    # embedded file data
    dc = Cursor(data_payload)
    _, units = dc.array(f.T_DATA_UNIT)
    blobs: list[bytes] = []
    for u in units:
        uc = Cursor(u)
        _, blob_items = uc.array(f.T_FILE_DATA)
        for b in blob_items:
            bcur = Cursor(b)
            _, comp, _ = bcur.field(f.T_COMPRESSED)
            blobs.append(_decompress(comp))
    out["data_units"] = len(units)
    if len(units) == 1:
        for fi in files:
            idx = fi["file_index"]
            if idx >= len(blobs):
                fi["data_present"] = False
                fi["hash_ok"] = False
                continue
            fi["data_present"] = True
            fi["actual_length"] = len(blobs[idx])
            fi["actual_sha1"] = hashlib.sha1(blobs[idx]).hexdigest()
            fi["hash_ok"] = fi["actual_sha1"] == fi.get("sha1") and len(blobs[idx]) == fi["length"]
    else:
        out["data_note"] = "multiple data units: embedded file hashes not checked"
    return out, blobs


def _file_description(payload: bytes) -> dict:
    c = Cursor(payload)
    _, target, _ = c.field(f.T_STRING)
    _, mime, _ = c.field(f.T_STRING)
    caps = None
    if c.peek_type() == f.T_CAPABILITIES:
        _, cp, _ = c.field(f.T_CAPABILITIES)
        caps = cp.hex()
    _, hashp, _ = c.field(f.T_HASH)
    hc = Cursor(hashp)
    algo = hc.read_u32()
    _, blob, _ = hc.field(f.T_BLOB)
    op = c.read_u32()
    op_opts = c.read_u32()
    length = struct.unpack("<Q", c.take(8))[0]
    ulength = struct.unpack("<Q", c.take(8))[0]
    index = c.read_u32()
    return {
        "target": target.decode("utf-16-le"), "mime_type": mime.decode("utf-16-le"),
        "capabilities_raw": caps, "hash_algorithm": algo, "sha1": blob.hex() if algo == 1 else None,
        "operation": op, "operation_options": op_opts, "length": length,
        "uncompressed_length": ulength, "file_index": index,
    }
