#!/usr/bin/env python3
"""s60inspect — независимая проверка собранных файлов скина (.skn/.mbm/.mif).

Не использует вендорные инструменты, поэтому ловит ошибки их связки:
  * .mbm: UID, trailer, заголовки растров, границы данных;
  * .mif: UID/версия, таблица смещений, каждый индекс указывает на реальный растр в .mbm;
  * .skn: заявленная длина равна размеру файла, имена .mbm/.mif в теле совпадают.

Использование:  s60inspect.py <имя без расширения> [--quiet]
Код возврата 0 — проблем нет.
"""
import os
import struct
import sys

MBM_UID1, MBM_UID2 = 0x10000037, 0x10000042
MIF_UID = 0x34232342


def inspect_mbm(path, log):
    d = open(path, "rb").read()
    problems = []
    if len(d) < 24:
        return ["mbm слишком короткий"], []
    u1, u2, u3, crc, trailer = struct.unpack_from("<5I", d, 0)
    if (u1, u2) != (MBM_UID1, MBM_UID2):
        problems.append("mbm: UID1/UID2 = %08x/%08x" % (u1, u2))
    if trailer + 4 > len(d):
        return problems + ["mbm: trailer за пределами файла"], []
    n = struct.unpack_from("<I", d, trailer)[0]
    if trailer + 4 + 4 * n > len(d):
        return problems + ["mbm: таблица смещений за пределами файла"], []
    offs = struct.unpack_from("<%dI" % n, d, trailer + 4)
    bitmaps = []
    for i, o in enumerate(offs):
        if o + 40 > len(d):
            problems.append("mbm[%d]: заголовок за пределами файла" % i)
            continue
        size, hdr, w, h, tw, th, bpp, color, pal, comp = struct.unpack_from("<10I", d, o)
        if hdr != 40 or o + size > len(d) or w <= 0 or h <= 0:
            problems.append("mbm[%d]: некорректный заголовок (size=%d hdr=%d %dx%d)" % (i, size, hdr, w, h))
        bitmaps.append((w, h, bpp, comp))
    log("mbm: %d растров, %d байт" % (n, len(d)))
    return problems, bitmaps


def inspect_mif(path, mbm_count, log):
    d = open(path, "rb").read()
    problems = []
    if len(d) < 16:
        return ["mif слишком короткий"], 0
    uid, ver, aoff, alen = struct.unpack_from("<4i", d, 0)
    if uid != MIF_UID:
        problems.append("mif: UID %08x" % (uid & 0xFFFFFFFF))
    if ver != 2:
        problems.append("mif: версия %d (ожидалась 2)" % ver)
    if alen % 2:
        problems.append("mif: число элементов нечётное (%d)" % alen)
    if aoff + 8 * alen > len(d):
        return problems + ["mif: таблица смещений за пределами файла"], 0
    used = set()
    for k in range(alen):
        off, ln = struct.unpack_from("<2i", d, aoff + 8 * k)
        if off > 0:
            problems.append("mif[%d]: иконка внутри mif (SVG) — не ожидалась" % k)
        elif -off >= mbm_count and not (off == 0 and k % 2 == 1):
            problems.append("mif[%d]: индекс mbm %d вне диапазона (в mbm %d)" % (k, -off, mbm_count))
        elif not (off == 0 and k % 2 == 1):
            if -off in used:
                problems.append("mif[%d]: индекс mbm %d использован дважды" % (k, -off))
            used.add(-off)
    log("mif: %d иконок (%d элементов), задействовано растров mbm: %d из %d"
        % (alen // 2, alen, len(used), mbm_count))
    if len(used) != mbm_count:
        problems.append("mif: не все растры mbm адресуются из mif (%d из %d)" % (len(used), mbm_count))
    return problems, alen // 2


def inspect_skn(path, base, log):
    d = open(path, "rb").read()
    problems = []
    length, typ, ver = struct.unpack_from("<IHH", d, 0)
    if length != len(d):
        problems.append("skn: заявленная длина %d != размеру файла %d" % (length, len(d)))
    for ext in (".mbm", ".mif"):
        name = (os.path.basename(base) + ext).encode("utf-16-le")
        if name not in d:
            problems.append("skn: не найдено имя %s в теле" % ext)
    log("skn: %d байт, тип %d, версия %d" % (len(d), typ, ver))
    return problems


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 2
    base = args[0]
    log = (lambda *_: None) if quiet else print
    problems = []
    for ext in (".skn", ".mbm", ".mif"):
        if not os.path.isfile(base + ext):
            problems.append("нет файла %s%s" % (base, ext))
    if not problems:
        p, bitmaps = inspect_mbm(base + ".mbm", log)
        problems += p
        p, _ = inspect_mif(base + ".mif", len(bitmaps), log)
        problems += p
        problems += inspect_skn(base + ".skn", base, log)
    for p in problems:
        print("ПРОБЛЕМА:", p)
    print("OK" if not problems else "НАЙДЕНО ПРОБЛЕМ: %d" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
