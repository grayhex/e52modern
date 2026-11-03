"""CLI-facing operations of the phone workspace; each returns a ``symport.report`` Report."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from symport.report import DEVICE, FAIL, PASS, SKIP, UNKNOWN, WARN, Report
from symport.sis import reader
from symport.sis.fields import SisFormatError
from symport.util import artifact_entry, sha256_file

from . import archive, gammu_calendar, inventory

NOT_TESTED = "no physical Nokia E52 has been used; mounted-volume behaviour was tested on temporary directories"


def _base(command: str) -> Report:
    rep = Report(command)
    rep.limitations.append(NOT_TESTED)
    return rep


def backup_create(volume: Path, dest: Path, label: str, exclude: tuple[str, ...], max_bytes: int | None) -> Report:
    rep = _base("phone backup create")
    kw = {"max_bytes": max_bytes} if max_bytes else {}
    try:
        res = archive.create(volume, dest, label=label, exclude=exclude, **kw)
    except archive.BackupError as e:
        rep.add("backup.create", FAIL, str(e))
        return rep
    rep.add("backup.create", PASS if res.complete else WARN,
            f"{res.files} files, {res.bytes} bytes copied" + ("" if res.complete else
                                                              f"; {len(res.skipped)} item(s) skipped (backup is NOT complete)"))
    for s in res.skipped[:50]:
        rep.add("backup.skipped", WARN, f"{s.path}: {s.reason}")
    v = archive.verify(dest)
    rep.add("backup.verify", PASS if v["ok"] else FAIL, f"re-read and hashed {v['checked']} files from the backup"
            + ("" if v["ok"] else f"; problems: missing={v['missing'][:5]} mismatched={v['mismatched'][:5]}"))
    rep.artifacts.append(artifact_entry(dest / "manifest.json"))
    rep.data.update(files=res.files, bytes=res.bytes, complete=res.complete)
    rep.limitations.append("File backup only: not contacts, SMS, calendar, the phone-memory application registry or firmware.")
    return rep


def backup_verify(backup: Path) -> Report:
    rep = _base("phone backup verify")
    try:
        v = archive.verify(backup)
    except archive.BackupError as e:
        rep.add("backup.manifest", FAIL, str(e))
        return rep
    rep.add("backup.verify", PASS if v["ok"] else FAIL,
            f"{v['checked']} files re-hashed" if v["ok"] else
            f"missing={v['missing'][:10]} mismatched={v['mismatched'][:10]} extra={v['extra'][:10]} unsafe={v['unsafe'][:10]}")
    rep.add("backup.complete", PASS if v["complete_at_creation"] else WARN,
            "backup was complete when created" if v["complete_at_creation"] else
            f"backup was INCOMPLETE when created ({len(v['skipped_at_creation'])} skipped item(s))")
    rep.data["verify"] = v
    return rep


def backup_restore(backup: Path, volume: Path, apply: bool, only: str | None) -> Report:
    rep = _base("phone backup restore")
    try:
        r = archive.restore(backup, volume, apply=apply, only=only)
    except archive.BackupError as e:
        rep.add("restore", FAIL, str(e))
        return rep
    p = r["plan"]
    rep.add("restore.plan", PASS if not p["blocked"] else WARN,
            f"new={p['new']} identical={p['identical']} conflict={p['conflict']} blocked={p['blocked']}; "
            "existing files are never overwritten and nothing is deleted")
    if p["conflict"]:
        rep.add("restore.conflicts", WARN, f"{p['conflict']} file(s) exist with different content and will stay untouched",
                paths=r["details"]["conflict"][:20])
    if not apply:
        rep.add("restore.apply", SKIP, "dry run: pass --apply to write the new files")
    else:
        ok = not r["failed"] and r["written"] == r["verified"]
        rep.add("restore.apply", PASS if ok else FAIL,
                f"wrote {r['written']} file(s), {r['verified']} verified by read-back hash"
                + ("" if ok else f"; failures: {r['failed'][:5]}"))
    rep.data["restore"] = {k: r[k] for k in ("applied", "plan", "bytes_needed", "bytes_free", "written", "verified", "failed")}
    return rep


def apps_inventory(volume: Path) -> Report:
    rep = _base("phone apps inventory")
    inv = inventory.scan(volume)
    rep.add("inventory.scan", PASS, f"{len(inv['packages'])} SIS/SISX package file(s) found, "
            f"{len(inv['unreadable'])} unreadable")
    bad = [p["path"] for p in inv["packages"] if not p["checksums_ok"]]
    if bad:
        rep.add("inventory.integrity", FAIL, f"checksum mismatch: {bad[:10]}")
    for uid, paths in inv["duplicates_by_uid"].items():
        rep.add("inventory.duplicate", WARN, f"UID {uid} appears in {len(paths)} files: {paths}")
    rep.add("inventory.installed_state", UNKNOWN,
            "installed state on the phone is not observable from a mounted volume", level=DEVICE)
    rep.data["inventory"] = inv
    return rep


def calendar_read(config: str | None) -> Report:
    rep = _base("phone calendar read")
    if not config:
        rep.add("gammu.config", FAIL, "no Gammu configuration (use --gammu-config or SYMPORT_GAMMU_CONFIG)")
        rep.unsupported("Calendar access needs Gammu with a working configuration on the PC connected to the phone.",
                        ["Install Gammu and verify: gammu --config <file> identify", "Then: symport phone calendar read --gammu-config <file>"])
        return rep
    if shutil.which("gammu") is None:
        rep.add("gammu.binary", FAIL, "gammu not found on PATH", "environment")
        rep.unsupported("gammu is not installed.", ["Install the official Gammu package (GPL-2.0)."])
        return rep
    try:
        data = gammu_calendar.read(config)
    except ValueError as e:
        rep.add("calendar.read", FAIL, str(e), DEVICE)
        return rep
    status = data.pop("status")
    rep.add("calendar.read", PASS if status == "read" else WARN,
            f"{len(data['events'])} event(s), {len(data['todos'])} to-do(s)" if status == "read" else
            "no entries: empty calendar or unsupported by this phone/driver (indistinguishable)", DEVICE)
    rep.add("calendar.compat", UNKNOWN, "E52 + Gammu calendar support has not been verified on hardware", DEVICE)
    rep.data["calendar"] = data
    rep.limitations.append("Read-only: nothing is written to the phone.")
    return rep


def stage_sis(sis: Path, volume: Path, folder: str = "Installs") -> Report:
    """Copy a validated SIS onto an enrolled volume. Transfer only: it does not install anything."""
    rep = _base(f"phone stage {Path(sis).name}")
    try:
        data = Path(sis).read_bytes()
        info = reader.inspect(data)
    except (OSError, SisFormatError) as e:
        rep.add("sis.valid", FAIL, f"refusing to stage an unreadable/invalid SIS: {e}")
        return rep
    ok = info["uid_checksum_ok"] and info["controller_crc_ok"] and info["data_crc_ok"]
    rep.add("sis.valid", PASS if ok else FAIL, "SIS structure and checksums verified before copying")
    if not ok:
        return rep
    rep.add("sis.signed", PASS if info["signed"] else WARN,
            "signed package" if info["signed"] else "UNSIGNED package: the phone may refuse to install it")
    volume = Path(volume)
    if not volume.is_dir() or volume.is_symlink() or Path(folder).is_absolute() or ".." in Path(folder).parts:
        rep.add("target", FAIL, "volume must be a directory and the folder a relative path without '..'")
        return rep
    target_dir = volume / folder
    if target_dir.is_symlink():
        rep.add("target", FAIL, "target folder is a symlink")
        return rep
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = target_dir / Path(sis).name
    if dst.exists():
        rep.add("target", FAIL, f"{dst.name} already exists on the volume; refusing to overwrite")
        return rep
    if shutil.disk_usage(target_dir).free < len(data) + 1024 * 1024:
        rep.add("target", FAIL, "not enough free space on the volume")
        return rep
    tmp = dst.with_name(dst.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, dst)
    same = sha256_file(dst) == sha256_file(Path(sis))
    rep.add("stage.copy", PASS if same else FAIL, f"copied to {folder}/{dst.name}; read-back SHA-256 "
            + ("matches" if same else "DIFFERS"), DEVICE)
    rep.add("device.install", UNKNOWN, "staged only: open the file on the phone and record the result with the "
            "manual checklist (docs/DEVICE_TEST.md)", DEVICE)
    rep.verification["physical_device"] = "staged-not-installed" if same else "failed"
    if same:
        rep.artifacts.append(artifact_entry(dst))
    return rep
