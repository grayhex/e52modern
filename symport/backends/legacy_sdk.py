"""Detection of an original Symbian/Carbide SDK (``EPOCROOT``) and its official tools.

SymPort only *uses* tools it finds; it never bundles proprietary SDK files.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

OFFICIAL_TOOLS = ("makesis", "signsis", "createsis", "rcomp", "elf2e32", "mifconv", "bmconv", "petran")


@dataclass
class LegacySdk:
    epocroot: Path | None
    tools: dict[str, str | None] = field(default_factory=dict)

    @property
    def present(self) -> bool:
        return any(self.tools.values()) or self.epocroot is not None


def detect(env: dict | None = None) -> LegacySdk:
    env = env if env is not None else os.environ
    root = None
    if env.get("EPOCROOT"):
        p = Path(env["EPOCROOT"])
        root = p if p.exists() else None
    tools: dict[str, str | None] = {}
    for t in OFFICIAL_TOOLS:
        tools[t] = shutil.which(t)
        if tools[t] is None and root is not None:
            for cand in (root / "epoc32" / "tools" / t, root / "epoc32" / "tools" / f"{t}.exe"):
                if cand.is_file():
                    tools[t] = str(cand)
                    break
    return LegacySdk(epocroot=root, tools=tools)
