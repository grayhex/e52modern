#!/usr/bin/env python3
"""Полная сборка тем: PNG -> BMP -> skin.txt -> .skn/.mbm/.mif/.pkg -> проверка.

    python3 tools/build_theme.py [light] [dark]      (по умолчанию обе)

Результат: theme/dist/<variant>/  — файлы для `makesis <real>.pkg` (шаг SIS вне репозитория).
Требует собранных инструментов: tools/s60/build.sh
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
S60 = os.path.join(HERE, "s60")
sys.path.insert(0, HERE)
sys.path.insert(0, S60)
import gen_skin  # noqa: E402
import mifbuild  # noqa: E402

SKC = os.path.join(S60, "bin", "skc")
BMCONV = os.path.join(S60, "bin", "bmconv")


def fail(msg):
    print("ОШИБКА:", msg, file=sys.stderr)
    sys.exit(1)


def build_variant(variant):
    cfg = gen_skin.VARIANTS[variant]
    real = cfg["real"]
    src = gen_skin.generate(variant, ROOT)
    out = os.path.join(ROOT, "theme", "dist", variant)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    tmp = os.path.join(out, ".tmp")
    os.makedirs(tmp)

    r = subprocess.run([SKC, "-m" + tmp + "/", "-t" + out + "/", "skin.txt", real],
                       cwd=src, capture_output=True, text=True)
    log = r.stdout + r.stderr
    notes = [l for l in log.splitlines() if l.startswith("NOTE:") or "rror" in l]
    if r.returncode != 0 or not os.path.isfile(os.path.join(out, real + ".skn")):
        sys.stderr.write(log)
        fail("skc не собрал %s" % real)
    bad = [l for l in notes if "not add" in l or "rror" in l]
    if bad:
        fail("skc сообщил о проблеме:\n" + "\n".join(bad))
    for n in (l for l in notes if l not in bad and "Generated IID" not in l and "Skintype" not in l):
        print("  skc:", n)

    lst = os.path.join(tmp, real + "_MIFList.txt")
    icons, bitmaps = mifbuild.build(lst, src, os.path.join(out, real), BMCONV)

    # .pkg: человекочитаемое имя и вендор
    pkg_path = os.path.join(out, real + ".pkg")
    pkg = open(pkg_path, encoding="ascii", errors="replace").read()
    pkg = re.sub(r'^#\{"[^"]*"\}', '#{"%s"}' % cfg["title"], pkg, count=1, flags=re.M)
    pkg = re.sub(r'^:"[^"]*"', ':"e52modern"', pkg, flags=re.M)
    pkg = re.sub(r'^%\{"[^"]*"\}', '%{"e52modern"}', pkg, flags=re.M)
    open(pkg_path, "w", encoding="ascii", newline="\n").write(pkg)

    shutil.rmtree(tmp)
    rc = subprocess.run([sys.executable, os.path.join(S60, "s60inspect.py"), os.path.join(out, real)]).returncode
    if rc != 0:
        fail("проверка s60inspect не пройдена для %s" % real)
    sizes = {f: os.path.getsize(os.path.join(out, f)) for f in sorted(os.listdir(out))}
    print("  %s: %s" % (variant, ", ".join("%s %d B" % kv for kv in sizes.items())))


def main():
    if not (os.path.isfile(SKC) and os.path.isfile(BMCONV)):
        fail("нет инструментов: запустите tools/s60/build.sh")
    subprocess.run([sys.executable, os.path.join(HERE, "build_assets.py")], check=True)
    for v in (sys.argv[1:] or list(gen_skin.VARIANTS)):
        print("== сборка:", v)
        build_variant(v)
    print("Готово. Дальше: makesis <имя>.pkg в theme/dist/<variant>/ (см. tools/s60/README.md).")


if __name__ == "__main__":
    main()
