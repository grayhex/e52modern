"""Project helpers for symbian-platform projects (``symbian.toml``)."""
from __future__ import annotations

import re
import tomllib
import zlib
from pathlib import Path

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


class ProjectError(Exception):
    pass


def validate_name(name: str) -> None:
    if not NAME_RE.match(name):
        raise ProjectError("name must match [a-z][a-z0-9_]{1,30} (executable basename for SIS)")


def suggest_uids(name: str) -> tuple[int, int]:
    """Deterministic *test-range* UIDs (0xE...): never use them for published software."""
    h = zlib.crc32(name.encode()) & 0x0FFFFFF0
    return 0xE0000000 | h, 0xE0000000 | (h + 1)


def read_config(project: Path) -> dict:
    p = Path(project) / "symbian.toml"
    if not p.is_file():
        raise ProjectError(f"{p} not found (not a symbian-platform project)")
    try:
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{p}: {e}") from e


def built_executable(project: Path, cfg: dict) -> Path | None:
    """Where the SDK writes the converted E32 image (docs: .symbian/build/<name>.exe)."""
    name = cfg.get("project", {}).get("name") or cfg.get("package", {}).get("executable_name", "").removesuffix(".exe")
    if not name:
        return None
    p = Path(project) / ".symbian" / "build" / f"{name}.exe"
    return p if p.is_file() else None
