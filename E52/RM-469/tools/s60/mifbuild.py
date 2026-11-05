#!/usr/bin/env python3
"""mifbuild — замена `mifconv` для растровых (bitmap-only) скалируемых скинов S60.

Вход:  список, который пишет Nokia Skin Compiler (`skc -m<dir> ...`, файл *_MIFList.txt)
Выход: <name>.mbm (через bmconv) и <name>.mif

Формат MIF v2 восстановлен по открытым исходникам ридера Nokia
(oss.FCL.sf.mw.uiresources: uigraphics/AknIcon — AknIconLoader.h/.cpp,
AknIconLocationInfo.cpp, MifToCdlIndex/MifHandler.h, mifconvdefs.h):

    int32 uid       = 0x34232342        (KUidAvkonMultiIconFile)
    int32 version   = 2
    int32 arrayOff  = 16                (сразу за заголовком)
    int32 arrayLen  = 2 * <число иконок>
    arrayLen раз:  int32 offset, int32 length
        элемент 2k   — растр иконки k, 2k+1 — её маска
        offset <= 0  => иконка лежит в .mbm под индексом -offset (в mbm)
        offset  > 0  => иконка (SVG) внутри самого .mif — здесь НЕ поддерживается

Идентификатор иконки в .skn = 16384 + номер элемента, поэтому порядок записей
списка обязан совпадать с порядком, в котором их нумерует skc.

Ограничения: SVG-иконки не поддерживаются (нет SVG-T энкодера). Маска ищется по
соглашению mifconv: `<имя>_mask_soft.bmp` для ",8" и `<имя>_mask.bmp` для ",1".
"""
import argparse
import os
import struct
import subprocess
import sys

MIF_UID = 0x34232342
MIF_VERSION = 2
MIF_ID_FIRST = 16384


def parse_list(path):
    """Возвращает [(depth, mask_depth|None, bmp_path)] в порядке файла."""
    entries = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for n, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line == "-E":
                continue
            if line.startswith("-A "):
                raise SystemExit("%s:%d: анимированный SVG не поддерживается" % (path, n))
            opt, _, rest = line.partition(" ")
            if not opt.startswith("-") or not rest:
                raise SystemExit("%s:%d: не понимаю строку: %r" % (path, n, line))
            if rest.startswith("-A "):
                raise SystemExit("%s:%d: анимированный SVG не поддерживается" % (path, n))
            depth, _, mask = opt[1:].partition(",")
            src = rest.strip()
            if src.lower().endswith(".svg"):
                raise SystemExit("%s:%d: SVG-иконки не поддерживаются (%s)" % (path, n, src))
            entries.append((depth, mask or None, src))
    return entries


def mask_path(bmp, mask_depth):
    stem, ext = os.path.splitext(bmp)
    suffix = {"8": "_mask_soft", "1": "_mask"}.get(mask_depth)
    if suffix is None:
        raise SystemExit("маска глубиной %s не поддерживается: %s" % (mask_depth, bmp))
    return stem + suffix + ext


def build(list_file, srcdir, outbase, bmconv):
    entries = parse_list(list_file)
    if not entries:
        raise SystemExit("пустой список: %s (нечего упаковывать)" % list_file)

    args, elements, idx = [], [], 0
    for depth, mdepth, rel in entries:
        bmp = os.path.abspath(os.path.join(srcdir, rel))
        if not os.path.isfile(bmp):
            raise SystemExit("нет файла: %s" % bmp)
        args.append("-%s%s" % (depth, bmp))
        elements.append((-idx, 0))
        idx += 1
        if mdepth:
            mp = mask_path(bmp, mdepth)
            if not os.path.isfile(mp):
                raise SystemExit("нет файла маски: %s" % mp)
            args.append("-%s%s" % (mdepth, mp))
            elements.append((-idx, 0))
            idx += 1
        else:
            elements.append((0, 0))

    mbm = outbase + ".mbm"
    if os.path.exists(mbm):
        os.remove(mbm)
    r = subprocess.run([bmconv, "-q", mbm] + args, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(mbm):
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("bmconv завершился с ошибкой")

    mif = outbase + ".mif"
    with open(mif, "wb") as f:
        f.write(struct.pack("<4i", MIF_UID, MIF_VERSION, 16, len(elements)))
        for off, ln in elements:
            f.write(struct.pack("<2i", off, ln))
    return len(entries), idx


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("list", help="*_MIFList.txt от skc")
    ap.add_argument("outbase", help="путь без расширения: будут созданы .mif и .mbm")
    ap.add_argument("--srcdir", default=".", help="каталог, от которого считаются пути из списка")
    ap.add_argument("--bmconv", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "bmconv"))
    a = ap.parse_args()
    icons, bitmaps = build(a.list, a.srcdir, a.outbase, a.bmconv)
    print("mifbuild: %d иконок, %d растров в .mbm -> %s.{mif,mbm}" % (icons, bitmaps, a.outbase))


if __name__ == "__main__":
    main()
