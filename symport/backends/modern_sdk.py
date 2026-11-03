"""Adapter for the modern open-source SDK https://github.com/hpnkv/symbian-platform (``symbian`` CLI).

Verified facts (from that project's documentation and source, 0.3.0):
  * SIS writer packages one EKA2 E32 *executable* (+ optional libraries/registration assets).
    Arbitrary files, historical .pkg scripts, dependencies, upgrades are NOT supported, so it
    cannot package a theme (.skn/.mbm/.mif).
  * ``symbian inspect --format {elf32,e32,sis}``, ``symbian build/package``, ``symbian device
    list/info/install --package``, ``symbian emulator ...`` exist. SymPort shells out to them.
This module never imports the SDK; the ``symbian`` executable is an optional external backend.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from symport.util import RunResult, run

ENV_VAR = "SYMPORT_SYMBIAN"

CAPABILITIES = {
    "theme_packaging": False,   # arbitrary files / skin install paths unsupported
    "application_packaging": True,
    "e32_build": True,
    "device_staging": True,
}


@dataclass
class ModernSdk:
    executable: str | None

    @property
    def available(self) -> bool:
        return self.executable is not None

    def run(self, args: list[str], cwd: Path | None = None, timeout: float = 900) -> RunResult:
        if not self.executable:
            return RunResult(["symbian", *args], 127, "", "symbian CLI not found")
        return run([self.executable, *args], cwd=cwd, timeout=timeout)

    def json(self, args: list[str], cwd: Path | None = None, timeout: float = 900) -> tuple[RunResult, dict | None]:
        """Run with the CLI's canonical JSON output (``--output-format json`` is a global option)."""
        r = self.run(["--output-format", "json", *args], cwd=cwd, timeout=timeout)
        try:
            parsed = json.loads(r.stdout)
            return r, parsed if isinstance(parsed, dict) else None
        except ValueError:
            return r, None

    def version(self) -> str | None:
        """Installed distribution version. The CLI has no --version, so ask its own interpreter."""
        if not self.executable:
            return None
        try:
            first = Path(self.executable).read_text(encoding="utf-8", errors="ignore").splitlines()[0]
        except (OSError, IndexError):
            return None
        if not first.startswith("#!"):
            return None
        py = first[2:].strip().split()[0]
        r = run([py, "-c", "import importlib.metadata as m; print(m.version('symbian-platform'))"], timeout=30)
        return r.stdout.strip() or None if r.ok else None


def locate() -> ModernSdk:
    cand = os.environ.get(ENV_VAR) or shutil.which("symbian")
    if cand and not Path(cand).exists() and shutil.which(cand):
        cand = shutil.which(cand)
    return ModernSdk(cand if cand and Path(cand).exists() else None)


INSTALL_HINT = [
    "python3 -m venv ~/.venvs/symbian && . ~/.venvs/symbian/bin/activate",
    "pip install symbian-platform   # Apache-2.0; requires Python 3.11-3.14, Linux glibc >= 2.28",
    "symbian doctor",
    "symbian sdk install ~/dev/symbian-sdk --archive <native SDK archive>   # glibc >= 2.39",
]


def summarize(r: RunResult, parsed: dict | None) -> str:
    """One-line outcome for reports: the CLI's own status when JSON was returned."""
    if parsed and isinstance(parsed.get("status"), dict):
        st = parsed["status"]
        text = f"{st.get('name', '?')}" + (f": {st['message']}" if st.get("message") else "")
    else:
        text = (r.output or "no output")[-600:]
    return hint(text) or text


KNOWN_HINTS = [
    ("Ninja 1.12", "the SDK looks for `ninja` NEXT TO the compiler first; a system ninja older than 1.12 "
                   "(e.g. /usr/bin/ninja 1.11) shadows a newer one on PATH. Put ninja>=1.12 (pip install ninja) "
                   "plus symlinks to clang++, ld.lld and cmake in one directory and pass it with "
                   "--compiler/--linker."),
    ("symbian-native", "E32 publishing needs the standalone `symbian-native` tool from the native SDK "
                       "archive/installed SDK (`symbian sdk install ...`); the pip wheel alone is not enough."),
]


def hint(text: str) -> str | None:
    for needle, advice in KNOWN_HINTS:
        if needle in text:
            return f"{text}\n  hint: {advice}"
    return None
