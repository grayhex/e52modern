"""Read the generated skin source (theme/src/<variant>/skin.txt + gfx/*.bmp)."""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

_BMP_LINE = re.compile(r"^\s*(?:BMP\s+\S+\s+)?c16\s+(\S+\.bmp)(?:\s+SOFTMASK=(\S+\.bmp))?", re.I)


@dataclass
class ExpectedBitmap:
    name: str
    mask: str | None
    size: tuple[int, int]
    mask_size: tuple[int, int] | None


def bmp_size(path: Path) -> tuple[int, int]:
    """Width/height of a Windows BMP from its header (no imaging library needed)."""
    d = Path(path).read_bytes()[:30]
    if len(d) < 26 or d[:2] != b"BM":
        raise ValueError(f"{path}: not a BMP")
    w, h = struct.unpack_from("<ii", d, 18)
    return abs(w), abs(h)


def skin_uid(skin_txt: Path) -> int | None:
    for line in Path(skin_txt).read_text(encoding="ascii", errors="replace").splitlines():
        m = re.match(r"\s*UID\s+(0x[0-9a-fA-F]+)", line)
        if m:
            return int(m.group(1), 16)
    return None


def expected_bitmaps(src_dir: Path) -> list[ExpectedBitmap]:
    """Bitmaps in the order the Nokia compiler allocates icon ids (first appearance)."""
    gfx = Path(src_dir) / "gfx"
    out: list[ExpectedBitmap] = []
    seen: set[str] = set()
    for line in (Path(src_dir) / "skin.txt").read_text(encoding="ascii", errors="replace").splitlines():
        m = _BMP_LINE.match(line)
        if not m:
            continue
        name, mask = m.group(1), m.group(2)
        if name in seen:
            continue
        seen.add(name)
        out.append(ExpectedBitmap(name, mask, bmp_size(gfx / name),
                                  bmp_size(gfx / mask) if mask else None))
    return out
