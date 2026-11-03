"""Inventory of SIS/SISX packages found on an enrolled volume (files only, nothing is installed)."""
from __future__ import annotations

import os
from pathlib import Path

from symport.sis import reader
from symport.sis.fields import SisFormatError
from symport.theme import uids

MAX_SIS = 64 * 1024 * 1024
SUFFIXES = (".sis", ".sisx")


def scan(volume: Path, *, max_files: int = 5000) -> dict:
    """List packages under ``volume``. Whether a package is *installed* on the phone is unknowable
    from a mounted card: the registry lives in the phone's own file system."""
    volume = Path(volume)
    rows, errors = [], []
    for cur, dirs, names in os.walk(volume, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(cur) / d).is_symlink()]
        for n in sorted(names):
            if not n.lower().endswith(SUFFIXES):
                continue
            p = Path(cur) / n
            rel = p.relative_to(volume).as_posix()
            if p.is_symlink() or not p.is_file():
                continue
            if len(rows) + len(errors) >= max_files:
                errors.append({"path": rel, "error": "scan limit reached"})
                continue
            if p.stat().st_size > MAX_SIS:
                errors.append({"path": rel, "error": "larger than the 64 MiB scan limit"})
                continue
            try:
                info = reader.inspect(p.read_bytes())
            except (SisFormatError, OSError, ValueError, KeyError) as e:
                errors.append({"path": rel, "error": f"not a readable SIS 9.x package: {e}"})
                continue
            pk = info["package"]
            ok = info["uid_checksum_ok"] and info["controller_crc_ok"] and info["data_crc_ok"]
            rows.append({
                "path": rel, "size": p.stat().st_size, "uid": f"{pk['uid']:#010x}",
                "uid_class": uids.classify(pk["uid"]), "name": (pk["names"] or [""])[0],
                "vendor": (pk["vendor_names"] or [""])[0],
                "version": ".".join(map(str, pk["version"] or [])), "signed": info["signed"],
                "files": len(info["files"]), "checksums_ok": bool(ok),
                "dependency_elements": info["dependencies"]["declared"],
            })
    by_uid: dict[str, list[dict]] = {}
    for r in rows:
        by_uid.setdefault(r["uid"], []).append(r)
    duplicates = {u: [x["path"] for x in v] for u, v in by_uid.items() if len(v) > 1}
    return {"packages": rows, "unreadable": errors, "duplicates_by_uid": duplicates,
            "note": "Packages found as files; installed state on the phone is not observable from a volume."}
