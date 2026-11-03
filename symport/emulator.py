"""``symport emulator list|test``: run an external EKA2L1 command in an isolated session.

No emulator flags are assumed. The command template comes from ``symport.toml``::

    [emulator]
    command = ["/path/to/eka2l1_qt", "--your-flag", "{sis}"]   # placeholders: {sis} {workdir} {log}
    data_root = "/path/to/prepared/eka2l1-data"                 # optional; copied per session
    timeout = 120
    success_marker = "regex found in the log when the app has started"   # optional, user-defined
    screenshot = "{workdir}/screenshot.png"                     # optional, only if the tool writes one

A zero exit status or a marker in the log is reported as exactly that - *never* as a verified
installation or application start.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from symport.backends import eka2l1, modern_sdk
from symport.config import Config
from symport.devices.profiles import Profile
from symport.report import EMULATOR, ENVIRONMENT, FAIL, PASS, UNKNOWN, WARN, Report
from symport.sis import reader
from symport.sis.fields import SisFormatError
from symport.util import artifact_entry, run, sha256_file


def list_emulators(cfg: Config) -> Report:
    rep = Report("emulator list")
    emu = eka2l1.locate()
    rep.add("eka2l1", PASS if emu.available else WARN,
            f"{emu.executable} (from {emu.source})" if emu.available
            else "EKA2L1 not found (set SYMPORT_EKA2L1 or add it to PATH)", ENVIRONMENT)
    sdk = modern_sdk.locate()
    rep.add("symbian.emulator", PASS if sdk.available else WARN,
            "symbian CLI present: use `symbian emulator list/doctor` for its disposable sessions"
            if sdk.available else "symbian CLI (symbian-platform) not found", ENVIRONMENT)
    emu_cfg = cfg.data.get("emulator", {})
    rep.add("config.command", PASS if emu_cfg.get("command") else WARN,
            "launch command template configured" if emu_cfg.get("command")
            else "no [emulator] command configured in symport.toml (required for `emulator test`)",
            ENVIRONMENT)
    rep.data["eka2l1"] = {"path": emu.executable, "source": emu.source,
                          "license": "GPL-3.0 (separate program; not bundled)"}
    rep.data["rom_profiles"] = {"note": "ROM/firmware images are user-supplied and never redistributed",
                                "configured_data_root": emu_cfg.get("data_root")}
    rep.limitations.append("EKA2L1 documents no stable headless CLI; SymPort does not guess its flags.")
    return rep


def test_package(cfg: Config, sis: Path, profile: Profile, out_dir: Path | None = None) -> Report:
    rep = Report(f"emulator test {sis.name}")
    emu_cfg = cfg.data.get("emulator", {})
    try:
        info = reader.inspect(Path(sis).read_bytes())
        rep.add("sis.valid", PASS if info["controller_crc_ok"] and info["data_crc_ok"] else FAIL,
                "SIS structure verified before launch")
    except (OSError, SisFormatError) as e:
        rep.add("sis.valid", FAIL, f"refusing to test an unreadable/invalid SIS: {e}")
        return rep
    command = emu_cfg.get("command")
    if not command:
        rep.add("config.command", FAIL, "no [emulator] command configured")
        rep.unsupported("Emulator launch command is not configured; no emulation was performed.",
                        ["Add to symport.toml: [emulator] command = [\"/path/eka2l1\", ..., \"{sis}\"]",
                         "Provide your own ROM/firmware data (never committed or redistributed)."])
        return rep
    exe_ok = Path(command[0]).exists() or shutil.which(command[0])
    if not exe_ok:
        rep.add("emulator.binary", FAIL, f"{command[0]} not found")
        rep.unsupported("Configured emulator binary does not exist.", [])
        return rep

    out_dir = out_dir or (cfg.build_dir / "emulator")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="symport-emu-") as tmp:
        workdir = Path(tmp)
        staged = workdir / sis.name
        shutil.copy2(sis, staged)
        env = {}
        if emu_cfg.get("data_root"):
            dst = workdir / "data-root"
            shutil.copytree(emu_cfg["data_root"], dst)
            env["EKA2L1_DATA_ROOT"] = str(dst)
            rep.add("session.isolated", PASS, "emulator data root copied into a disposable directory",
                    EMULATOR)
        else:
            rep.add("session.isolated", WARN, "no data_root configured: only the working directory "
                    "is isolated, emulator state outside it is shared", EMULATOR)
        log_path = out_dir / f"{sis.stem}.emulator.log"
        argv = [c.format(sis=str(staged), workdir=str(workdir), log=str(log_path)) for c in command]
        r = run(argv, cwd=workdir, timeout=float(emu_cfg.get("timeout", 120)), env=env)
        log_path.write_text(f"$ {' '.join(argv)}\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}\n",
                            encoding="utf-8")
        rep.artifacts.append(artifact_entry(log_path))
        rep.add("emulator.process", PASS if r.ok else FAIL,
                "emulator process exited with status 0" if r.ok else
                ("emulator process timed out" if r.timed_out else f"emulator exited with status {r.returncode}"),
                EMULATOR, exit_code=r.returncode, timed_out=r.timed_out)
        marker = emu_cfg.get("success_marker")
        if marker:
            seen = re.search(marker, r.stdout + "\n" + r.stderr) is not None
            rep.add("emulator.marker", PASS if seen else FAIL,
                    f"user-defined log marker {marker!r} {'found' if seen else 'NOT found'}", EMULATOR)
        shot = emu_cfg.get("screenshot")
        if shot:
            sp = Path(shot.format(workdir=str(workdir), sis=str(staged), log=str(log_path)))
            if sp.is_file():
                keep = out_dir / f"{sis.stem}.screenshot{sp.suffix}"
                shutil.copy2(sp, keep)
                rep.artifacts.append(artifact_entry(keep))
                rep.add("emulator.screenshot", PASS, "screenshot written by the emulator command", EMULATOR,
                        sha256=sha256_file(keep))
            else:
                rep.add("emulator.screenshot", WARN, "configured screenshot file was not produced", EMULATOR)
    rep.add("emulator.install", UNKNOWN, "SIS installation inside the emulator is NOT confirmed: "
            "a process exit/log marker is not an installation result", EMULATOR)
    rep.add("emulator.app_start", UNKNOWN, "application start is NOT confirmed", EMULATOR)
    rep.verification["emulator"] = "launched-unconfirmed" if r.ok else "failed"
    rep.data["target"] = profile.id
    rep.limitations.append("physical_device: not-tested. Emulator coverage of system services is incomplete.")
    return rep
