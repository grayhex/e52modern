"""EKA2L1 emulator adapter.

EKA2L1 (GPL-3.0, https://github.com/EKA2L1/EKA2L1) documents no stable headless CLI in its
README. SymPort therefore does NOT assume flags: the launch command is a user-supplied
template (symport.toml ``[emulator] command``), and a successful process exit is never reported
as a successful SIS installation or application start.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

ENV_VAR = "SYMPORT_EKA2L1"
CANDIDATE_NAMES = ("eka2l1_qt", "eka2l1_sdl", "eka2l1_stage", "eka2l1")


@dataclass
class Emulator:
    executable: str | None
    source: str

    @property
    def available(self) -> bool:
        return self.executable is not None


def locate() -> Emulator:
    env = os.environ.get(ENV_VAR)
    if env:
        found = shutil.which(env) or (env if Path(env).is_file() else None)
        return Emulator(found, f"${ENV_VAR}")
    for n in CANDIDATE_NAMES:
        found = shutil.which(n)
        if found:
            return Emulator(found, "PATH")
    return Emulator(None, "not found")
