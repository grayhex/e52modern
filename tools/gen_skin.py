#!/usr/bin/env python3
"""Генератор исходников скина S60 из PNG-ресурсов темы.

Берёт theme/assets/<variant>/*.png (их делает tools/build_assets.py) и пишет
theme/src/<variant>/skin.txt + gfx/*.bmp — то, что понимает Nokia Skin Compiler.

Определяются (всё остальное наследуется от системной темы телефона):
  * фон экрана (QsnBgScreen / QsnBgScreenIdle);
  * рамки: подсветка списка и сетки меню, popup/подменю, поле ввода;
  * цветовые таблицы: текст, иконки, линии, прочее, подсветка, компоненты.
Расшифровка индексов цветов — в заголовке AknsConstants.h (см. COLOR_ROLES ниже).
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_assets as ba  # noqa: E402  (палитры)

ROOT = os.path.abspath(os.path.join(HERE, ".."))

VARIANTS = {
    # uid — из тестового диапазона 0xE0000000+ (self-signed установка);
    # перед публикацией выдать собственный UID (Symbian Signed).
    "light": {"uid": 0xE0E52C01, "title": "E52 Clear Light", "real": "e52clearlight"},
    "dark":  {"uid": 0xE0E52C02, "title": "E52 Clear Dark",  "real": "e52cleardark"},
}

# (имя ресурса, префикс файлов, поле 9-slice в пикселях)
FRAMES = [
    ("QsnFrList", "list", "list_highlight", 6),
    ("QsnFrGrid", "grid", "grid_highlight", 12),
    ("QsnFrPopup", "popup", "popup", 10),
    ("QsnFrPopupSub", "popsub", "popup", 10),
    ("QsnFrInput", "input", "input_field", 6),
]
PARTS = ["tl", "tr", "bl", "br", "t", "b", "l", "r", "c"]  # порядок, которого требует FRAME

# Размеры таблиц = числу значений в enum AknsConstants.h
N_TEXT, N_ICON, N_LINE, N_OTHER, N_HIGHLIGHT, N_COMPONENT = 83, 33, 15, 22, 3, 25
FIXED_DARK = "#212B35"  # «бумага» Заметок/Калькулятора рисуется системой светлой в обоих вариантах


def hexrgb(h):
    return "0x%s" % h.lstrip("#").upper()


def slice9(img, m, side=8):
    """9 фрагментов. m — ширина рамки; side — размер «растяжимой» части."""
    w, h = img.size
    cx, cy = (w - side) // 2, (h - side) // 2
    return {
        "tl": img.crop((0, 0, m, m)),
        "tr": img.crop((w - m, 0, w, m)),
        "bl": img.crop((0, h - m, m, h)),
        "br": img.crop((w - m, h - m, w, h)),
        "t": img.crop((cx, 0, cx + side, m)),
        "b": img.crop((cx, h - m, cx + side, h)),
        "l": img.crop((0, cy, m, cy + side)),
        "r": img.crop((w - m, cy, w, cy + side)),
        "c": img.crop((cx, cy, cx + side, cy + side)),
    }


def save_piece(piece, base):
    """Сохраняет RGB-BMP и, если есть прозрачность, 8-битную мягкую маску. Возвращает True, если маска нужна."""
    rgba = piece.convert("RGBA")
    rgba.convert("RGB").save(base + ".bmp", "BMP")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 255:
        alpha.save(base + "_mask_soft.bmp", "BMP")
        return True
    return False


def color_tables(p):
    text = [p["text"]] * N_TEXT
    over = {
        3: p["text_second"],                 # неактивная вкладка
        4: "#FFFFFF",                        # режим энергосбережения (чёрный экран)
        9: p["hl_text"], 10: p["hl_text"], 11: p["hl_text"],   # подсветка списка/сетки/значения
        12: p["softkey_text"], 13: p["softkey_text"],
        16: p["softkey_text"], 17: p["softkey_text"],
        20: p["text_disabled"],              # календарь: неактивные дни
        23: p["hl_text"],                    # copy/paste
        27: "#FFFFFF",                       # тень текста режима энергосбережения
        28: FIXED_DARK, 29: FIXED_DARK, 30: FIXED_DARK,        # калькулятор
        33: FIXED_DARK,                      # заметки
        60: p["text_disabled"],
        63: p["accent"],
    }
    for i, c in over.items():
        text[i] = c

    icons = [p["text"]] * N_ICON
    for i, c in {8: p["text_second"], 15: p["hl_text"], 16: p["hl_text"], 17: p["hl_text"]}.items():
        icons[i] = c

    lines = [p["text_second"]] * N_LINE
    for i in (3, 4, 5, 6, 10, 14):
        lines[i] = p["line"]
    for i in (7, 8, 9):
        lines[i] = p["accent"]

    other = ["#1E90FF", "#F08080", "#000000", "#FFD700", "#FFFFFF", "#2F918F", "#FF0066", "#0099FF",
             p["line"],                                           # 8  фон VKB/HWR
             p["bg"], p["status"], p["line"], p["panel"], p["hl_fill_top"], p["accent"],  # 9-14 eSWT
             p["text"],                                           # 15
             "#000000", "#FFFFFF",                                # 16/17 fade black/white map
             p["accent"], "#FFFFFF", p["bg"], p["panel"]]         # 18-21
    assert len(other) == N_OTHER

    highlight = [p["accent"], p["hl_fill_bot"], p["accent"]]
    component = [p["text"]] * N_COMPONENT
    return {"QsnTextColors": text, "QsnIconColors": icons, "QsnLineColors": lines,
            "QsnOtherColors": other, "QsnHighlightColors": highlight, "QsnComponentColors": component}


def generate(variant, root=ROOT):
    cfg = VARIANTS[variant]
    p = ba.PALETTES[variant]
    assets = os.path.join(root, "theme", "assets", variant)
    src = os.path.join(root, "theme", "src", variant)
    gfx = os.path.join(src, "gfx")
    os.makedirs(gfx, exist_ok=True)
    for f in os.listdir(gfx):
        os.remove(os.path.join(gfx, f))

    # фон
    bg = Image.open(os.path.join(assets, "background.png")).convert("RGB")
    assert bg.size == (240, 320), bg.size
    bg.save(os.path.join(gfx, "bg_screen.bmp"), "BMP")

    L = []
    w = L.append
    w("// Generated by tools/gen_skin.py - do not edit by hand.")
    w("SKINTYPE scalable")
    w("UID 0x%08X" % cfg["uid"])
    w('NAME 1 "%s"' % cfg["title"])
    w('AUTHOR "e52modern"')
    w('COPYRIGHT "e52modern"')
    w("")
    w("BITMAPPATH gfx/")
    w("SCALABLEITEM IID=QsnBgScreen INPUT=none OUTPUT=0/RGB")
    w("  EFFECT UID=0x101F8748 INPUTA=none INPUTB=none OUTPUT=0/RGB")
    w("    BMP f c16 bg_screen.bmp")
    w("    INT ms 1")
    w("  END")
    w("END")
    w("SCALABLEITEM IID=QsnBgScreenIdle REFIID=QsnBgScreen")
    w("")
    for iid, prefix, asset, margin in FRAMES:
        img = Image.open(os.path.join(assets, asset + ".png")).convert("RGBA")
        pieces = slice9(img, margin)
        w("FRAME IID=%s" % iid)
        for part in PARTS:
            base = "%s_%s" % (prefix, part)
            masked = save_piece(pieces[part], os.path.join(gfx, base))
            if masked:
                w("  c16 %s.bmp SOFTMASK=%s_mask_soft.bmp STRETCH" % (base, base))
            else:
                w("  c16 %s.bmp STRETCH" % base)
        w("END")
        w("")
    for name, vals in color_tables(p).items():
        w("COLORTABLE IID=%s" % name)
        for v in vals:
            w("  RGB=%s" % hexrgb(v))
        w("END")
        w("")
    path = os.path.join(src, "skin.txt")
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    return src


if __name__ == "__main__":
    for v in (sys.argv[1:] or VARIANTS):
        print("gen_skin:", generate(v))
