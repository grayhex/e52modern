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

    def version(self) -> str | None:
        if not self.executable:
            return None
        r = run([self.executable, "--version"], timeout=30)
        return r.output.splitlines()[0] if r.ok and r.output else None


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
