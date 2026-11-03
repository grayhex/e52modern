"""Adapter for the existing E52Modern skin pipeline (tools/build_theme.py, tools/s60/*)."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from symport.config import Config
from symport.util import RunResult, run


@dataclass
class SkinTools:
    skc: Path
    bmconv: Path
    mifbuild: Path
    s60inspect: Path
    build_script: Path

    def missing(self) -> list[str]:
        return [n for n, p in vars(self).items() if not Path(p).exists()]


def tools(cfg: Config) -> SkinTools:
    s60 = cfg.s60_dir
    return SkinTools(skc=s60 / "bin" / "skc", bmconv=s60 / "bin" / "bmconv",
                     mifbuild=s60 / "mifbuild.py", s60inspect=s60 / "s60inspect.py",
                     build_script=cfg.repo / "tools" / "build_theme.py")


def bootstrap(cfg: Config) -> RunResult:
    """Build skc and bmconv from the vendored Nokia/Symbian sources (tools/s60/build.sh)."""
    return run(["bash", str(cfg.s60_dir / "build.sh")], cwd=cfg.repo, timeout=900)


def build_variant(cfg: Config, variants: list[str]) -> RunResult:
    """Run the unchanged pipeline entry point: ``python3 tools/build_theme.py [variant...]``."""
    return run([sys.executable, str(cfg.repo / "tools" / "build_theme.py"), *variants],
               cwd=cfg.repo, timeout=900)


def load_s60inspect(cfg: Config):
    """Import tools/s60/s60inspect.py so its low-level checks are reused, not duplicated."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("s60inspect", cfg.s60_dir / "s60inspect.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
