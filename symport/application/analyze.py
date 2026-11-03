"""``symport app analyze``, ``app inspect <exe>``, ``sis inspect``: static compatibility reports."""
from __future__ import annotations

import struct
from pathlib import Path

from symport.analysis import compat
from symport.analysis import e32 as e32mod
from symport.devices.profiles import Profile
from symport.report import FAIL, PASS, UNKNOWN, WARN, Report
from symport.sis import reader
from symport.sis.fields import SisFormatError

SIS_UID1 = 0x10201A7A


def sniff(data: bytes) -> str:
    if data[:4] == b"\x7fELF":
        return "elf"
    if len(data) >= 4 and struct.unpack_from("<I", data, 0)[0] == SIS_UID1:
        return "sis"
    if e32mod.is_e32(data):
        return "e32"
    return "unknown"


def analyze_e32_bytes(data: bytes, profile: Profile, fw: compat.FirmwareProfile | None,
                      rep: Report, label: str = "") -> str | None:
    try:
        info = e32mod.analyze(data)
    except (e32mod.E32Error, struct.error) as e:
        rep.add(f"e32.parse{label}", FAIL, f"{e}")
        return None
    rep.data.setdefault("images", []).append({"label": label or "image", **info})
    return compat.evaluate(info, profile, fw, rep)


def _elf_note(data: bytes, rep: Report) -> None:
    if len(data) < 52:
        rep.add("elf.parse", FAIL, "truncated ELF header")
        return
    machine = struct.unpack_from("<H", data, 18)[0]
    flags = struct.unpack_from("<I", data, 36)[0]
    rep.add("elf.kind", WARN, f"ELF (machine {machine}, ARM EABI v{flags >> 24}): an intermediate build "
            "product, not an installable Symbian image; convert with the SDK (`symbian app build`)")
    rep.data["compatibility"] = {"status": "not-tested", "reason": "ELF is not an E32 image"}


def analyze_file(path: Path, profile: Profile, fw: compat.FirmwareProfile | None,
                 cross_check: bool = False) -> Report:
    rep = Report(f"app inspect {Path(path).name}")
    rep.verification["static_automated"] = True
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        rep.add("file", FAIL, str(e))
        return rep
    kind = sniff(data)
    rep.data["kind"] = kind
    if kind == "e32":
        analyze_e32_bytes(data, profile, fw, rep)
        if cross_check and rep.data.get("images"):
            from symport.analysis import crosscheck
            crosscheck.crosscheck_file(Path(path), rep.data["images"][0], rep)
    elif kind == "sis":
        return analyze_sis(path, profile, fw)
    elif kind == "elf":
        _elf_note(data, rep)
    else:
        rep.add("file.kind", FAIL, "not an E32 image, SIS or ELF file")
    rep.limitations.append("Static analysis only; nothing was executed or installed.")
    return rep


def analyze_sis(path: Path, profile: Profile, fw: compat.FirmwareProfile | None) -> Report:
    rep = Report(f"sis inspect {Path(path).name}")
    rep.verification["static_automated"] = True
    try:
        data = Path(path).read_bytes()
        info = reader._inspect(data)[0]
    except (OSError, SisFormatError, struct.error) as e:
        rep.add("sis.parse", FAIL, f"cannot parse SIS: {e}")
        return rep
    ok = info["uid_checksum_ok"] and info["controller_crc_ok"] and info["data_crc_ok"]
    rep.add("sis.checksums", PASS if ok else FAIL, "UID checksum and controller/data CRC16"
            + (" verified" if ok else " MISMATCH"))
    bad = [f["target"] for f in info["files"] if f.get("hash_ok") is False]
    rep.add("sis.file_hashes", FAIL if bad else PASS,
            f"{len(info['files'])} embedded files match their SHA-1 hashes" if not bad
            else f"hash/length mismatch: {bad}")
    rep.add("sis.signature", PASS if info["signed"] else WARN,
            "signature chain present (not cryptographically verified)" if info["signed"]
            else "unsigned package: the E52 installation policy decides whether it installs")
    dep = info["dependencies"]
    rep.add("sis.dependencies", PASS if dep["declared"] else WARN,
            f"{dep['declared']} dependency elements; UIDs (best effort) "
            f"{[hex(u) for u in dep['uids_best_effort']]}" if dep["declared"]
            else "no dependency elements: S60 version / required packages are not checked on install")
    rep.data["sis"] = {k: info[k] for k in ("size", "signed", "uid3", "package", "files", "data_units")}
    verdicts = []
    try:
        blobs = reader.extract(data)
    except SisFormatError:
        blobs = {}
    for target, blob in blobs.items():
        if e32mod.is_e32(blob) and target.lower().rsplit(".", 1)[-1] in ("exe", "dll"):
            v = analyze_e32_bytes(blob, profile, fw, rep, label=f" [{target}]")
            if v:
                verdicts.append(v)
    if verdicts:
        worst = ("incompatible" if "incompatible" in verdicts else
                 "unknown" if "unknown" in verdicts else "compatible")
        rep.data["compatibility"] = {"target": profile.id, "status": worst, "runtime": "not-tested",
                                     "images": len(verdicts)}
    else:
        rep.data["compatibility"] = {"target": profile.id, "status": "not-tested",
                                     "reason": "package contains no E32 executables/DLLs "
                                               "(resource-only package, e.g. a theme)"}
        rep.add("compat.scope", UNKNOWN, "no E32 payload to evaluate; installation on the E52 "
                "is not tested", level="firmware")
    rep.limitations += ["Structural inspection only; signature chains are not verified and "
                        "installation on a phone is not tested."]
    return rep


def analyze_project(project: Path, profile: Profile, fw: compat.FirmwareProfile | None,
                    cross_check: bool = False) -> Report:
    """Project directory: configuration + built E32 image if present."""
    from symport.application import project as proj
    from symport.application.workflow import inspect_project
    rep = inspect_project(project, profile)
    rep.command = "app analyze"
    try:
        cfg = proj.read_config(project)
    except proj.ProjectError:
        return rep
    exe = proj.built_executable(project, cfg)
    if exe is None:
        rep.add("e32.image", UNKNOWN, "no built E32 image (.symbian/build/<name>.exe); "
                "build first - binary compatibility cannot be assessed from source", level="static")
        rep.data["compatibility"] = {"target": profile.id, "status": "not-tested",
                                     "reason": "project not built"}
        return rep
    analyze_e32_bytes(exe.read_bytes(), profile, fw, rep)
    if cross_check and rep.data.get("images"):
        from symport.analysis import crosscheck
        crosscheck.crosscheck_file(exe, rep.data["images"][0], rep)
    rep.verification["static_automated"] = True
    rep.limitations.append("Static analysis only; runtime behaviour not tested.")
    return rep
