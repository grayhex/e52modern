"""Experimental, read-only EKA1 ROM → RPKG converter (#47). Not a flashing tool and not an EKA2 importer.

The user supplies their own EKA1 ROM dump (ROM base ``0x50000000``). The Z: tree is read with the
bounds-checked core-ROM reader (``rom.py``; same TRomHeader/TRomEntry layout the EKA2L1 loader
uses) and packed into an RPKG v1 file. The conversion says only that the *structure* was converted;
``accepted-by-emulator`` and ``booted`` are never claimed here. Written from the public structure
descriptions, not copied from any other tool, and verified only on synthetic images: real EKA1 dumps
are ``not-tested``. Compression of the ROM image is not examined (the header fields that say so were
not confirmed) and a compressed ROM would fail as damaged entries rather than being "supported".
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .rom import RomError, RomImage
from .rpkg import MAX_FILE, RpkgError, write_v1

EKA1_ROM_BASE = 0x50000000
MAX_ROM = 48 * 1024 * 1024
MAX_FILES = 100_000
DEADLINE = 60.0
STATUSES = ('converted', 'accepted-by-emulator', 'booted', 'unsupported')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def report_base(raw: bytes, name: str) -> dict:
    return {'schema': 'symport.eka1-rpkg/1', 'status': 'unsupported', 'input': {'name': str(name)[:120], 'size': len(raw), 'sha256': sha(raw)},
            'accepted_by_emulator': 'not-attempted', 'booted': 'not-tested', 'real_image_tested': False,
            'emulation_claim': 'none: this converts a file structure; it does not boot or emulate a phone',
            'scope': 'EKA1 ROMs only. Not Nokia E52/E72/N95 (EKA2) firmware.'}


def convert(raw: bytes, output: Path, name: str = 'rom.dmp', deadline: float = DEADLINE) -> dict:
    report = report_base(raw, name)
    if not raw or len(raw) > MAX_ROM:
        report['reason'] = 'The ROM dump must be between 1 byte and 48 MiB.'
        return report
    started = time.monotonic()
    try:
        rom = RomImage(raw)
    except RomError as exc:
        report['reason'] = f'Not a readable core ROM image: {exc}'
        return report
    if rom.base != EKA1_ROM_BASE:
        report['reason'] = (f'ROM base {rom.base:#010x} is not the EKA1 base {EKA1_ROM_BASE:#010x}: EKA2 and other ROMs are not converted here '
                            '(use the existing Firmware Explorer for a core ROM).')
        return report
    try:
        found = []
        for path, address, size in rom.entries():
            if size == 0:
                continue
            if size > MAX_FILE:
                raise RomError('a file inside the ROM is implausibly large')
            if len(found) >= MAX_FILES:
                raise RomError('too many files in the ROM')
            if time.monotonic() - started > deadline:
                raise RomError('the conversion exceeded its time limit')
            found.append(('Z:\\' + path.replace('/', '\\'), address, size))
        if not found:
            raise RomError('the ROM contains no files')

        def entries():
            for rpath, address, size in found:
                if time.monotonic() - started > deadline:
                    raise RomError('the conversion exceeded its time limit')
                yield rpath, size, (rom.read(address, size),)

        written = write_v1(output, entries(), len(found), rom.version[:2] + (rom.version[2],) if len(rom.version) == 3 else (0, 0, 0))
    except (RomError, RpkgError) as exc:
        output.unlink(missing_ok=True)
        report['reason'] = f'The ROM structure is damaged or unsupported: {exc}'
        return report
    result = output.read_bytes()
    report.update(status='converted', output={'size': written, 'sha256': sha(result), 'entries': len(found), 'format': 'rpkg-v1'},
                  rom={'base': f'{rom.base:#010x}', 'size': rom.size, 'version': '.'.join(str(x) for x in rom.version)},
                  seconds=round(time.monotonic() - started, 2),
                  limitations=['Structure converted only: not accepted by an emulator and not booted.',
                               'Verified on synthetic EKA1 images; no real EKA1 ROM was available (not-tested).',
                               'Compression of the ROM image is not examined; a compressed image would appear as damaged entries.',
                               'Zero-size files and directory entries are not written; entry times and attributes are zero.'])
    return report


def report_json(report: dict) -> bytes:
    return json.dumps(report, ensure_ascii=False, indent=2).encode()
