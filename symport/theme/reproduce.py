"""Reproducibility check: build a variant twice in isolated copies and compare after normalisation.

The Nokia compiler stamps the build time into the SKN *Information* chunk (type 11). That 8-byte
timestamp is the only permitted difference; everything else must be byte-identical.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from symport.config import Config
from symport.report import FAIL, PASS, Report

INFO_CHUNK_TYPE = 11


def find_timestamp_ranges(skn: bytes) -> list[tuple[int, int]]:
    """Byte ranges of the build timestamp(s) inside the SKN Information chunk(s)."""
    ranges = []
    for i in range(0, len(skn) - 16):
        length, ctype, ver = struct.unpack_from("<IHH", skn, i)
        if ctype == INFO_CHUNK_TYPE and ver == 2 and 16 <= length <= 96 and i + length <= len(skn):
            ranges.append((i + 8, i + 16))
    return ranges


def normalise_skn(skn: bytes) -> bytes:
    b = bytearray(skn)
    for lo, hi in find_timestamp_ranges(skn):
        b[lo:hi] = b"\0" * (hi - lo)
    return bytes(b)


def compare_dirs(a: Path, b: Path) -> dict:
    result: dict = {"files": {}, "identical": True}
    names = sorted({p.name for p in a.iterdir() if p.is_file()} | {p.name for p in b.iterdir() if p.is_file()})
    for name in names:
        pa, pb = a / name, b / name
        if not (pa.is_file() and pb.is_file()):
            result["files"][name] = "missing in one build"
            result["identical"] = False
            continue
        da, db = pa.read_bytes(), pb.read_bytes()
        if da == db:
            result["files"][name] = "identical"
        elif name.endswith(".skn") and normalise_skn(da) == normalise_skn(db):
            result["files"][name] = "identical after normalising the build timestamp"
        else:
            result["files"][name] = "DIFFERENT"
            result["identical"] = False
    return result


def _copy_workspace(cfg: Config, dest: Path) -> None:
    def ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n in {"dist", "__pycache__", ".build", ".git"}]
    shutil.copytree(cfg.repo / "tools", dest / "tools", ignore=ignore, symlinks=False)
    (dest / "theme").mkdir()
    # the pipeline regenerates theme/assets, theme/src and theme/dist from tools/ alone


def check_reproducible(cfg: Config, variant: str) -> Report:
    rep = Report(f"theme reproduce --variant {variant}")
    rep.verification["static_automated"] = True
    with tempfile.TemporaryDirectory(prefix="symport-repro-") as tmp:
        outs = []
        for n in ("a", "b"):
            ws = Path(tmp) / n
            ws.mkdir()
            _copy_workspace(cfg, ws)
            r = subprocess.run([sys.executable, "tools/build_theme.py", variant], cwd=ws,
                               capture_output=True, text=True)
            if r.returncode != 0:
                rep.add(f"build.{n}", FAIL, f"isolated build {n} failed: {(r.stdout + r.stderr)[-400:]}")
                return rep
            outs.append(ws / "theme" / "dist" / variant)
        result = compare_dirs(*outs)
    rep.add("repro.identical", PASS if result["identical"] else FAIL,
            "two isolated builds are identical (SKN timestamp normalised)" if result["identical"]
            else "builds differ beyond the allowed timestamp", files=result["files"])
    rep.data["comparison"] = result
    return rep
