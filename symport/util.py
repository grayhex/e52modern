"""Small shared helpers: hashing, subprocess wrapper, tool lookup."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def artifact_entry(path: Path, root: Path | None = None) -> dict:
    p = Path(path)
    shown = str(p.relative_to(root)) if root and p.is_relative_to(root) else str(p)
    return {"path": shown, "size": p.stat().st_size, "sha256": sha256_file(p)}


@dataclass
class RunResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" + self.stderr if self.stderr else "")).strip()


def run(argv: list[str], cwd: Path | None = None, timeout: float | None = 600,
        env: dict | None = None) -> RunResult:
    """Run an external tool, capturing output. Never raises for non-zero exit."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env=full_env, errors="replace")
        return RunResult(list(argv), p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired as e:
        return RunResult(list(argv), -1, (e.stdout or b"").decode(errors="replace")
                         if isinstance(e.stdout, bytes) else (e.stdout or ""),
                         (e.stderr or b"").decode(errors="replace")
                         if isinstance(e.stderr, bytes) else (e.stderr or ""), timed_out=True)
    except FileNotFoundError as e:
        return RunResult(list(argv), 127, "", str(e))
    except OSError as e:
        return RunResult(list(argv), 126, "", str(e))


def which(name: str, env_var: str | None = None) -> str | None:
    """Resolve a tool: explicit env var (path or command) first, then PATH."""
    if env_var and os.environ.get(env_var):
        v = os.environ[env_var]
        found = shutil.which(v) or (v if Path(v).is_file() else None)
        return found
    return shutil.which(name)
