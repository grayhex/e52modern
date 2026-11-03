"""``symport app init|build|package|inspect`` - thin, honest wrappers over the ``symbian`` CLI."""
from __future__ import annotations

from pathlib import Path

from symport.analysis import e32 as e32mod
from symport.analysis.compat import FirmwareProfile
from symport.application import project as proj
from symport.backends import modern_sdk
from symport.devices.profiles import Profile
from symport.report import FAIL, PASS, UNKNOWN, WARN, Report
from symport.sis import reader
from symport.sis.fields import SisFormatError
from symport.util import artifact_entry


def _need_sdk(rep: Report, sdk: modern_sdk.ModernSdk) -> bool:
    if sdk.available:
        return True
    rep.add("backend.symbian", FAIL, "symbian CLI (symbian-platform) not found", "environment")
    rep.unsupported("This operation needs the modern open-source SDK (symbian-platform); no "
                    "implementation of it is bundled.", modern_sdk.INSTALL_HINT)
    return False


def init_project(name: str, dest: Path, profile: Profile, sdk: modern_sdk.ModernSdk) -> Report:
    rep = Report("app init")
    try:
        proj.validate_name(name)
    except proj.ProjectError as e:
        rep.add("name", FAIL, str(e))
        return rep
    if dest.exists() and any(dest.iterdir()):
        rep.add("dest", FAIL, f"{dest} is not empty; refusing to overwrite")
        return rep
    if not _need_sdk(rep, sdk):
        return rep
    abi = profile.value("cpu.target_abi", "armv5")
    arch = {"armv5": "armv5t", "armv6": "armv6"}.get(abi)
    if arch is None:
        rep.add("target.arch", FAIL, f"profile {profile.id} has no mappable ABI ({abi})")
        return rep
    r, parsed = sdk.json(["init", str(dest), "--name", name, "--non-interactive", "--architecture", arch])
    rep.add("symbian.init", PASS if r.ok else FAIL,
            f"`symbian init` ({arch}) {'succeeded' if r.ok else 'failed'}: {modern_sdk.summarize(r, parsed)}",
            "environment")
    if not r.ok:
        return rep
    uid3, pkg_uid = proj.suggest_uids(name)
    rep.data.update({"project": str(dest), "target": profile.id, "architecture": arch,
                     "suggested_test_uids": [f"{uid3:#010x}", f"{pkg_uid:#010x}"]})
    rep.limitations += [
        "The SDK starter is a generic Window Server app (touch + Clear/Exit softkey); keypad "
        "handling on the E52 is untested.",
        "Build success does not mean the E52 firmware provides every imported DLL (run `symport "
        "app analyze` with a firmware profile).",
    ]
    return rep


def build_project(project: Path, profile: Profile, sdk: modern_sdk.ModernSdk, mode: str = "app",
                  compiler: str | None = None, linker: str | None = None) -> Report:
    """``mode='app'``: `symbian app build` (needs an installed native SDK, produced by `symbian init`).
    ``mode='toolchain'``: low-level `symbian build` with the host Clang/LLD only (works for the SDK's
    freestanding probe-style projects; no libc++/Window Server runtime)."""
    rep = Report("app build")
    try:
        cfg = proj.read_config(project)
    except proj.ProjectError as e:
        rep.add("project", FAIL, str(e))
        return rep
    arch = cfg.get("project", {}).get("architecture")
    want = {"armv5": "armv5t"}.get(profile.value("cpu.target_abi", ""), None)
    explicit_flag = mode == "toolchain" and arch is None     # the low-level build takes --architecture
    ok_arch = arch == want or explicit_flag
    rep.add("project.architecture", PASS if ok_arch else FAIL,
            (f"project does not set an architecture; passing --architecture {want} explicitly"
             if explicit_flag else f"project architecture {arch!r}; profile {profile.id} needs {want!r} "
             "(set it in symbian.toml / `symbian app configure`)"))
    if not ok_arch:
        return rep
    if not _need_sdk(rep, sdk):
        return rep
    if mode == "toolchain":
        args = ["build", "--project", str(project), "--output", str(Path(project) / ".symbian" / "build"),
                "--architecture", want]
        args += ["--compiler", compiler] if compiler else []
        args += ["--linker", linker] if linker else []
        rep.limitations.append("toolchain mode uses the SDK's low-level `symbian build`: no installed native "
                               "SDK, so only freestanding E32 images (no libc++/Window Server runtime).")
    else:
        args = ["app", "build", "--project", str(project)]
    r, parsed = sdk.json(args)
    rep.add("symbian.build", PASS if r.ok else FAIL,
            modern_sdk.summarize(r, parsed) if not r.ok else "build finished", "environment", mode=mode)
    exe = proj.built_executable(project, cfg)
    if r.ok and exe:
        rep.artifacts.append(artifact_entry(exe))
        rep.data["executable"] = str(exe)
    elif r.ok:
        rep.add("build.artifact", FAIL, "build reported success but .symbian/build/<name>.exe is missing")
    return rep


def package_project(project: Path, profile: Profile, sdk: modern_sdk.ModernSdk,
                    output: Path | None = None, cert: Path | None = None,
                    key: Path | None = None) -> Report:
    rep = Report("app package")
    try:
        cfg = proj.read_config(project)
    except proj.ProjectError as e:
        rep.add("project", FAIL, str(e))
        return rep
    exe = proj.built_executable(project, cfg)
    if exe is None:
        rep.add("artifact", FAIL, "no built executable: run `symport app build` first")
        return rep
    if not _need_sdk(rep, sdk):
        return rep
    out = output or (project / ".symbian" / "package")
    args = ["package", "--project", str(project), "--artifact", str(exe), "--output", str(out)]
    if cert and key:
        args += ["--signing-certificate", str(cert), "--signing-key", str(key)]
    r, parsed = sdk.json(args)
    rep.add("symbian.package", PASS if r.ok else FAIL,
            modern_sdk.summarize(r, parsed) if not r.ok else "packaged", "environment")
    if not r.ok:
        return rep
    sis_files = sorted(Path(out).glob("*.sis")) if Path(out).is_dir() else []
    for s in sis_files:
        rep.artifacts.append(artifact_entry(s))
        try:
            info = reader.inspect(s.read_bytes())
            rep.add(f"sis.{s.name}", PASS if info["controller_crc_ok"] and info["data_crc_ok"] else FAIL,
                    f"SIS CRCs valid; {len(info['files'])} files; signed={info['signed']}")
        except SisFormatError as e:
            rep.add(f"sis.{s.name}", FAIL, str(e))
    if not sis_files:
        rep.add("sis.output", FAIL, f"no .sis found in {out}")
    rep.limitations += ["Packaged by symbian-platform's SIS writer: executable apps only; "
                        "installation on the E52 is untested."]
    return rep


def inspect_project(project: Path, profile: Profile) -> Report:
    rep = Report("app inspect")
    try:
        cfg = proj.read_config(project)
    except proj.ProjectError as e:
        rep.add("project", FAIL, str(e))
        return rep
    p, pk = cfg.get("project", {}), cfg.get("package", {})
    rep.add("project.config", PASS, f"project {p.get('name')!r}, architecture {p.get('architecture')!r}")
    want = {"armv5": "armv5t"}.get(profile.value("cpu.target_abi", ""))
    rep.add("project.architecture", PASS if p.get("architecture") == want else WARN,
            f"architecture {p.get('architecture')!r} vs E52 profile {want!r}")
    uid3, puid = p.get("uid3"), pk.get("uid")
    for label, v in (("uid3", uid3), ("package.uid", puid)):
        if isinstance(v, int):
            rep.add(f"uid.{label}", PASS if 0xE0000000 <= v <= 0xEFFFFFFF else WARN,
                    f"{label} {v:#010x} "
                    + ("(test range)" if 0xE0000000 <= v <= 0xEFFFFFFF else "(outside the test range supported by the SDK writer)"))
    if isinstance(uid3, int) and uid3 == puid:
        rep.add("uid.distinct", FAIL, "package UID equals executable UID3 (must differ)")
    exe = proj.built_executable(project, cfg)
    rep.data["built_executable"] = str(exe) if exe else None
    rep.data["application"] = cfg.get("application", {})
    return rep


def e32_inspect_file(path: Path) -> dict:
    return e32mod.analyze(Path(path).read_bytes())


def load_fw(path: Path | None) -> FirmwareProfile | None:
    from symport.analysis.compat import load_firmware_profile
    return load_firmware_profile(path) if path else None


__all__ = ["init_project", "build_project", "package_project", "inspect_project", "UNKNOWN"]
