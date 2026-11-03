"""``symport doctor``: environment survey. Optional components never block unrelated operations."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from symport.backends import eka2l1, legacy_sdk, modern_sdk, nokia_skin, packaging
from symport.config import Config, ConfigError, find_repo_root
from symport.devices import profiles as prof
from symport.report import ENVIRONMENT, FAIL, PASS, SKIP, WARN, Report


def _module_available(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


def survey(repo: Path | None = None) -> Report:
    rep = Report("doctor")
    rep.verification["static_automated"] = False
    tools: list[dict] = []

    def tool(name: str, found: str | None, needed_for: str, required: bool, hint: str,
             version: str | None = None) -> None:
        ok = bool(found)
        tools.append({"name": name, "found": ok, "path": found, "version": version,
                      "needed_for": needed_for, "required_for_core": required,
                      "hint": None if ok else hint})
        status = PASS if ok else (FAIL if required else WARN)
        msg = f"{found}" + (f" ({version})" if version else "") if ok else f"not found - {hint}"
        rep.add(f"tool.{name}", status, msg, ENVIRONMENT, needed_for=needed_for)

    py_ok = sys.version_info >= (3, 11)
    rep.add("python", PASS if py_ok else FAIL,
            f"Python {sys.version.split()[0]} ({'>=3.11 ok' if py_ok else 'SymPort needs >= 3.11'})",
            ENVIRONMENT)
    pil = _module_available("PIL")
    tools.append({"name": "pillow", "found": pil, "needed_for": "theme build (asset generation)",
                  "required_for_core": False, "hint": None if pil else "pip install pillow"})
    rep.add("python.pillow", PASS if pil else WARN,
            "Pillow available" if pil else "Pillow missing - `theme build` cannot regenerate assets "
            "(pip install pillow); inspect/package still work", ENVIRONMENT)

    cfg = None
    try:
        root = find_repo_root(explicit=repo) if repo else find_repo_root()
        cfg = Config.load(root)
        rep.add("repo", PASS, f"E52Modern checkout at {root}", ENVIRONMENT)
    except ConfigError as e:
        rep.add("repo", WARN, str(e), ENVIRONMENT)

    gxx = shutil.which("g++") or shutil.which("c++")
    tool("g++", gxx, "building skc/bmconv from vendored sources", False, "install g++ (build-essential)")
    if cfg:
        t = nokia_skin.tools(cfg)
        tool("skc", str(t.skc) if t.skc.exists() else None, "theme build (Nokia Skin Data Compiler)",
             False, "run tools/s60/build.sh")
        tool("bmconv", str(t.bmconv) if t.bmconv.exists() else None, "theme build (.mbm)", False,
             "run tools/s60/build.sh")
        tool("mifbuild", str(t.mifbuild) if t.mifbuild.exists() else None, "theme build (.mif)",
             True, "tools/s60/mifbuild.py missing from the checkout")
        tool("s60inspect", str(t.s60inspect) if t.s60inspect.exists() else None,
             "theme inspect (SKN/MBM/MIF structure)", True, "tools/s60/s60inspect.py missing")
        be = packaging.discover(cfg)
        tool("makesis", " ".join(be.makesis) if be.makesis else None,
             "theme package (official SIS packager)", False,
             "install Symbian SDK MakeSIS or set SYMPORT_MAKESIS (see docs/PACKAGING.md)")
        tool("signsis", " ".join(be.signsis) if be.signsis else None,
             "theme package --cert/--key (official signer)", False,
             "install Symbian SDK SignSIS or set SYMPORT_SIGNSIS")
        rep.add("packager.native", WARN, "experimental built-in unsigned writer available "
                "(--backend native); not validated by MakeSIS or a phone", ENVIRONMENT)
        modern = be.modern
        ver = modern.version() if modern.available else None
        tool("symbian", modern.executable, "app build/package/inspect, device staging (symbian-platform)",
             False, "pip install symbian-platform (Python 3.11-3.14, Linux glibc >= 2.28)", ver)
        profs = []
        try:
            profs = prof.list_profiles(cfg.profiles_dirs)
            rep.add("profiles", PASS if profs else WARN,
                    "profiles: " + (", ".join(p.id for p in profs) or "none"), ENVIRONMENT)
        except prof.ProfileError as e:
            rep.add("profiles", FAIL, str(e), ENVIRONMENT)
        rep.data["profiles"] = [p.summary() for p in profs]
    else:
        modern = modern_sdk.locate()
        tool("symbian", modern.executable, "app build/package/inspect (symbian-platform)", False,
             "pip install symbian-platform")

    sdk = legacy_sdk.detect()
    rep.add("legacy_sdk", PASS if sdk.present else SKIP,
            (f"EPOCROOT={sdk.epocroot}; tools: " + ", ".join(k for k, v in sdk.tools.items() if v))
            if sdk.present else "no original Symbian/Carbide SDK detected (optional)", ENVIRONMENT)
    emu = eka2l1.locate()
    tool("eka2l1", emu.executable, "emulator list/test", False,
         "install EKA2L1 and set SYMPORT_EKA2L1 (GPL-3.0, https://github.com/EKA2L1/EKA2L1)")
    openssl = shutil.which("openssl")
    tool("openssl", openssl, "signing identities via symbian-platform", False, "install openssl")
    wine = shutil.which("wine")
    tool("wine", wine, "running Windows makesis/signsis on Linux (optional)", False, "install wine")

    # readiness per operation
    names = {t["name"]: t["found"] for t in tools}
    ready = {
        "theme inspect": bool(cfg) and names.get("s60inspect", False),
        "theme build": bool(cfg) and names.get("skc") and names.get("bmconv") and pil,
        "theme package (makesis)": bool(cfg) and names.get("makesis", False),
        "theme package (native, experimental)": bool(cfg),
        "app build/package (symbian-platform)": names.get("symbian", False),
        "emulator test": names.get("eka2l1", False),
        "device stage": names.get("symbian", False),
    }
    rep.data["tools"] = tools
    rep.data["readiness"] = {k: bool(v) for k, v in ready.items()}
    rep.limitations.append("doctor reports installed tools only; it does not prove they work on the E52.")
    return rep
