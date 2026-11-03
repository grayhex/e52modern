"""Parser for the subset of Symbian .pkg syntax emitted by the Nokia Skin Compiler."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class PkgError(ValueError):
    pass


@dataclass
class PkgFileEntry:
    source: str
    dest: str
    options: str = ""


@dataclass
class Pkg:
    name: str = ""
    uid: int | None = None
    version: tuple[int, int, int] = (0, 0, 0)
    languages: list[str] = field(default_factory=list)
    platform_deps: list[int] = field(default_factory=list)   # [0x....] lines
    package_deps: list[int] = field(default_factory=list)    # (0x....) lines
    vendor: str = ""
    localised_vendor: str = ""
    files: list[PkgFileEntry] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)


_HEADER = re.compile(r'^#\s*\{\s*"([^"]*)"[^}]*\}\s*,\s*\(\s*(0x[0-9a-fA-F]+|\d+)\s*\)\s*,\s*'
                     r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)')
_PLATFORM = re.compile(r'^\[\s*(0x[0-9a-fA-F]+)\s*\]\s*,')
_DEP = re.compile(r'^\(\s*(0x[0-9a-fA-F]+)\s*\)\s*,')
_FILE = re.compile(r'^"([^"]*)"\s*-\s*"([^"]*)"\s*(?:,\s*([A-Za-z, ]+))?\s*$')


def parse(text: str) -> Pkg:
    pkg = Pkg()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("&"):
            pkg.languages = [x.strip() for x in line[1:].split(",") if x.strip()]
        elif line.startswith("#"):
            m = _HEADER.match(line)
            if not m:
                raise PkgError(f"unparseable package header: {line!r}")
            pkg.name = m.group(1)
            pkg.uid = int(m.group(2), 0)
            pkg.version = (int(m.group(3)), int(m.group(4)), int(m.group(5)))
        elif line.startswith("["):
            m = _PLATFORM.match(line)
            if not m:
                raise PkgError(f"unparseable platform dependency: {line!r}")
            pkg.platform_deps.append(int(m.group(1), 16))
        elif line.startswith("("):
            m = _DEP.match(line)
            if not m:
                raise PkgError(f"unparseable dependency: {line!r}")
            pkg.package_deps.append(int(m.group(1), 16))
        elif line.startswith(":"):
            m = re.match(r':\s*"([^"]*)"', line)
            pkg.vendor = m.group(1) if m else ""
        elif line.startswith("%"):
            m = re.match(r'%\s*\{\s*"([^"]*)"', line)
            pkg.localised_vendor = m.group(1) if m else ""
        elif line.startswith('"'):
            m = _FILE.match(line)
            if not m:
                raise PkgError(f"unparseable file line: {line!r}")
            pkg.files.append(PkgFileEntry(m.group(1), m.group(2), (m.group(3) or "").strip()))
        else:
            pkg.unparsed.append(line)
    if pkg.uid is None:
        raise PkgError("package header (#{...},(0xUID),...) not found")
    return pkg
