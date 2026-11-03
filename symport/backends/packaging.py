"""SIS packaging backends for S60 3rd Edition packages.

Backends (selection: ``symport.toml [packaging] backend`` or ``--backend``):

* ``makesis``     official Symbian MakeSIS (+ SignSIS) found on PATH, via $SYMPORT_MAKESIS /
                  $SYMPORT_SIGNSIS or config. Supports the full .pkg syntax, dependencies,
                  compression. Windows/Symbian-SDK tool; may be run through Wine (config list).
* ``native``      symport's experimental writer: arbitrary files, unsigned, no dependency
                  elements. Never used unless explicitly selected.
* ``modern-sdk``  hpnkv symbian-platform: packages E32 executables only -> cannot package themes.

``auto`` picks ``makesis`` when available and otherwise reports *unsupported* with instructions;
it never silently falls back to the experimental writer.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from symport.backends import modern_sdk
from symport.config import Config
from symport.theme.pkgfile import Pkg
from symport.util import RunResult, run

ENV_MAKESIS = "SYMPORT_MAKESIS"
ENV_SIGNSIS = "SYMPORT_SIGNSIS"
ENV_SIGN_PASS = "SYMPORT_SIGN_PASSPHRASE"


def _resolve(cmd_cfg, env_var: str, name: str) -> list[str] | None:
    """Config value (string or list, e.g. ["wine", "makesis.exe"]) > env var > PATH."""
    raw = os.environ.get(env_var) or cmd_cfg
    if raw:
        parts = raw if isinstance(raw, list) else str(raw).split()
        exe = shutil.which(parts[0]) or (parts[0] if Path(parts[0]).is_file() else None)
        return [exe, *parts[1:]] if exe else None
    found = shutil.which(name)
    return [found] if found else None


@dataclass
class Backends:
    makesis: list[str] | None
    signsis: list[str] | None
    modern: modern_sdk.ModernSdk
    configured: str

    def status(self) -> dict:
        return {
            "makesis": self.makesis, "signsis": self.signsis,
            "native": "built-in (experimental)",
            "modern-sdk": self.modern.executable,
            "configured": self.configured,
        }


def discover(cfg: Config) -> Backends:
    return Backends(
        makesis=_resolve(cfg.get("packaging", "makesis"), ENV_MAKESIS, "makesis"),
        signsis=_resolve(cfg.get("packaging", "signsis"), ENV_SIGNSIS, "signsis"),
        modern=modern_sdk.locate(),
        configured=cfg.get("packaging", "backend", "auto"),
    )


CAPABILITY_MATRIX = {
    "makesis":    {"arbitrary_files": True,  "dependencies": True,  "signing": "via signsis", "status": "official"},
    "native":     {"arbitrary_files": True,  "dependencies": False, "signing": False, "status": "experimental"},
    "modern-sdk": {"arbitrary_files": False, "dependencies": False, "signing": "applications only",
                   "status": "cannot package themes"},
}

MAKESIS_HELP = [
    "Install the official MakeSIS/SignSIS (Symbian SDK, S60 3rd Ed. FP2 SDK, Carbide.c++ or "
    "Symbian^3 SDK) - Windows tools; under Linux run them via Wine.",
    "Point SymPort at them: export SYMPORT_MAKESIS=/path/makesis (or SYMPORT_MAKESIS='wine /path/makesis.exe'), "
    "same for SYMPORT_SIGNSIS; or set [packaging] makesis/signsis in symport.toml.",
    "Or opt into the experimental unsigned writer: symport theme package --variant <v> --backend native",
]


def run_makesis(cmd: list[str], pkg: Path, out: Path) -> RunResult:
    """Official MakeSIS: ``makesis <pkg> <sis>`` executed in the package directory."""
    return run([*cmd, pkg.name, str(out.resolve())], cwd=pkg.parent, timeout=300)


def run_signsis(cmd: list[str], unsigned: Path, signed: Path, cert: Path, key: Path) -> RunResult:
    argv = [*cmd, str(unsigned), str(signed), str(cert), str(key)]
    passphrase = os.environ.get(ENV_SIGN_PASS)
    if passphrase:
        argv.append(passphrase)
    return run(argv, timeout=120)


def to_sis_package(pkg: Pkg, base_dir: Path):
    """Convert a parsed .pkg into the native writer's model; returns (SisPackage, dropped notes)."""
    from symport.sis.writer import SisFile, SisPackage
    dropped: list[str] = []
    files = []
    for e in pkg.files:
        if e.options.upper().startswith("FN"):
            dropped.append(f"null placeholder {e.dest} (FN) not encoded")
            continue
        files.append(SisFile(e.dest, (base_dir / e.source).read_bytes()))
    if pkg.platform_deps:
        dropped.append("platform dependency lines " + ", ".join(hex(x) for x in pkg.platform_deps)
                       + " not encoded (installer will not check the S60 version)")
    if pkg.package_deps:
        dropped.append("package dependency lines " + ", ".join(hex(x) for x in pkg.package_deps)
                       + " not encoded (installer will not check skin-support packages)")
    sp = SisPackage(uid=pkg.uid, name=pkg.name, vendor=pkg.vendor or "unknown",
                    version=pkg.version, files=files)
    return sp, dropped
