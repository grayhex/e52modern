"""Repository discovery, optional configuration (symport.toml) and tool overrides."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ENV_PROFILES = "SYMPORT_PROFILES"


class ConfigError(Exception):
    pass


def find_repo_root(start: Path | None = None, explicit: Path | None = None) -> Path:
    """Locate the E52Modern checkout (the directory holding theme/ and tools/)."""
    def is_root(p: Path) -> bool:
        return (p / "theme" / "manifest.json").is_file() and (p / "tools" / "build_theme.py").is_file()

    if explicit is not None:
        p = Path(explicit).resolve()
        if not is_root(p):
            raise ConfigError(f"{p} is not an E52Modern checkout (theme/manifest.json or "
                              "tools/build_theme.py missing)")
        return p
    if os.environ.get("SYMPORT_REPO"):
        return find_repo_root(explicit=Path(os.environ["SYMPORT_REPO"]))
    for base in [Path(start or Path.cwd()).resolve(), Path(__file__).resolve().parent.parent]:
        for cand in [base, *base.parents]:
            if is_root(cand):
                return cand
    raise ConfigError("E52Modern checkout not found: run inside it or pass --repo / set SYMPORT_REPO")


@dataclass
class Config:
    repo: Path
    data: dict = field(default_factory=dict)

    @classmethod
    def load(cls, repo: Path) -> Config:
        path = repo / "symport.toml"
        data: dict = {}
        if path.is_file():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"{path}: {e}") from e
        return cls(repo=repo, data=data)

    def get(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    @property
    def s60_dir(self) -> Path:
        return self.repo / "tools" / "s60"

    @property
    def profiles_dirs(self) -> list[Path]:
        dirs = []
        if os.environ.get(ENV_PROFILES):
            dirs += [Path(p) for p in os.environ[ENV_PROFILES].split(os.pathsep) if p]
        dirs.append(self.repo / "profiles")
        return dirs

    @property
    def build_dir(self) -> Path:
        return self.repo / "build" / "symport"
