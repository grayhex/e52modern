#!/usr/bin/env python3
"""Генератор ресурсов темы E52 / CLEAR (S60 3rd Ed. FP2, 240x320).

Запуск:  python3 tools/build_assets.py
Результат: theme/assets/{light,dark}/*.png, theme/manifest.json,
           theme/colours.json, theme/preview/*.png

Все графические ресурсы рисуются с 4x суперсэмплингом и уменьшаются,
поэтому края получаются гладкими. Результат детерминирован (seed фиксирован).
"""
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "theme")
SS = 4  # supersampling

# ---------------------------------------------------------------- палитра
PALETTES = {
    "light": {
        "bg":          "#F7F8F7",   # из задания
        "bg_glow":     "#E6ECF4",
        "panel":       "#FFFFFF",   # поле списка / popup
        "text":        "#212B35",   # из задания
        "text_second": "#566472",
        "text_disabled": "#9AA6B2",
        "accent":      "#4384CC",   # из задания
        "accent_dark": "#2F6AAE",
        "hl_fill_top": "#DCE9F7",
        "hl_fill_bot": "#C8DCF2",
        "hl_text":     "#10263D",
        "line":        "#CCD6E2",   # из задания
        "status":      "#EEF2F7",
        "softkey":     "#E4EAF2",
        "softkey_text": "#212B35",
        "tab_active":  "#FFFFFF",
        "tab_inactive": "#E9EEF4",
    },
    "dark": {
        "bg":          "#171B23",   # из задания
        "bg_glow":     "#26303F",
        "panel":       "#202733",
        "text":        "#DAE4ED",   # из задания
        "text_second": "#9AA9BA",
        "text_disabled": "#667385",
        "accent":      "#2161A0",   # из задания
        "accent_dark": "#17497D",
        "hl_fill_top": "#2D70B5",
        "hl_fill_bot": "#2161A0",
        "hl_text":     "#FFFFFF",
        "line":        "#505E6F",   # из задания
        "status":      "#1B212B",
        "softkey":     "#12161C",
        "softkey_text": "#DAE4ED",
        "tab_active":  "#2A3342",
        "tab_inactive": "#1C222C",
    },
}

W, H = 240, 320
STATUS_H = 44    # статус-панель (часы/оператор)
SOFTKEY_H = 28   # control pane (софт-клавиши)
ROW_H = 24       # строка списка
TAB_W, TAB_H = 40, 32  # 6 вкладок по 40 px
GRID_W, GRID_H = 80, 61  # ячейка меню 3 x 4


def rgb(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def lerp(c1, c2, t):
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(4))


def canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def finish(img):
    w, h = img.size[0] // SS, img.size[1] // SS
    return img.resize((w, h), Image.LANCZOS)


def vgrad(w, h, top, bot):
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for y in range(h):
        c = lerp(top, bot, y / max(1, h - 1))
        for x in range(w):
            px[x, y] = c
    return img


def rounded(w, h, r, fill_top, fill_bot, border, border_w=1, corners=(1, 1, 1, 1)):
    """Скруглённый прямоугольник с вертикальным градиентом и обводкой."""
    iw, ih = w * SS, h * SS
    img = canvas(w, h)
    mask = Image.new("L", (iw, ih), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, iw - 1, ih - 1], r * SS, fill=255, corners=tuple(bool(c) for c in corners))
    img.paste(vgrad(iw, ih, fill_top, fill_bot), (0, 0), mask)
    if border and border_w:
        inner = Image.new("L", (iw, ih), 0)
        idr = ImageDraw.Draw(inner)
        bw = border_w * SS
        idr.rounded_rectangle([bw, bw, iw - 1 - bw, ih - 1 - bw], max(0, (r - border_w)) * SS,
                              fill=255, corners=tuple(bool(c) for c in corners))
        ring = Image.new("L", (iw, ih), 0)
        ring.paste(mask, (0, 0))
        ring_px, in_px = ring.load(), inner.load()
        for y in range(ih):
            for x in range(iw):
                if in_px[x, y]:
                    ring_px[x, y] = 0
        solid = Image.new("RGBA", (iw, ih), border)
        img.paste(solid, (0, 0), ring)
    return img


# ------------------------------------------------------------ ресурсы
def make_background(p, name):
    rnd = random.Random(52)
    base, glow = rgb(p["bg"]), rgb(p["bg_glow"])
    img = Image.new("RGBA", (W, H))
    px = img.load()
    gx, gy = W * 0.72, H * 0.86
    rmax = math.hypot(W, H) * 0.62
    for y in range(H):
        for x in range(W):
            d = min(1.0, math.hypot(x - gx, y - gy) / rmax)
            t = (1 - d) ** 2 * 0.85
            c = lerp(base, glow, t)
            n = rnd.randint(-1, 1)  # едва заметное зерно против бандинга
            px[x, y] = (max(0, min(255, c[0] + n)), max(0, min(255, c[1] + n)), max(0, min(255, c[2] + n)), 255)
    return img


def make_statuspane(p):
    img = vgrad(W, STATUS_H, rgb(p["status"]), lerp(rgb(p["status"]), rgb(p["bg"]), 0.5))
    ImageDraw.Draw(img).line([(0, STATUS_H - 1), (W, STATUS_H - 1)], fill=rgb(p["line"]))
    return img


def make_controlpane(p):
    img = vgrad(W, SOFTKEY_H, lerp(rgb(p["softkey"]), rgb(p["bg"]), 0.35), rgb(p["softkey"]))
    ImageDraw.Draw(img).line([(0, 0), (W, 0)], fill=rgb(p["line"]))
    return img


def make_list_highlight(p):
    return finish(rounded(W, ROW_H, 4, rgb(p["hl_fill_top"]), rgb(p["hl_fill_bot"]), rgb(p["accent"]), 1))


def make_list_item_bg(p):
    img = Image.new("RGBA", (W, ROW_H), rgb(p["panel"]))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 2):  # пунктирный разделитель как в оригинале
        d.point((x, ROW_H - 1), fill=rgb(p["line"]))
    return img


def make_grid_highlight(p):
    fill_t, fill_b = rgb(p["hl_fill_top"], 235), rgb(p["hl_fill_bot"], 235)
    return finish(rounded(GRID_W, GRID_H, 9, fill_t, fill_b, rgb(p["accent"]), 2))


def make_popup(p):
    return finish(rounded(64, 48, 7, rgb(p["panel"]), lerp(rgb(p["panel"]), rgb(p["bg"]), 0.5), rgb(p["accent"]), 1))


def make_input(p):
    return finish(rounded(48, ROW_H, 3, rgb(p["panel"]), rgb(p["panel"]), rgb(p["line"]), 1))


def make_tab(p, active):
    key = "tab_active" if active else "tab_inactive"
    top = rgb(p[key])
    bot = lerp(top, rgb(p["bg"]), 0.0 if active else 0.4)
    border = rgb(p["accent"]) if active else rgb(p["line"])
    return finish(rounded(TAB_W, TAB_H, 6, top, bot, border, 1, corners=(1, 1, 0, 0)))


def make_shortcut_button(p):
    """Рамка кнопки быстрого доступа внизу экрана (как «голосовая почта» в оригинале)."""
    return finish(rounded(84, 30, 5, rgb(p["panel"]), lerp(rgb(p["panel"]), rgb(p["bg"]), 0.4), rgb(p["accent"]), 2))


def make_scroll(p):
    track = finish(rounded(6, 120, 3, rgb(p["line"], 120), rgb(p["line"], 120), None, 0))
    thumb = finish(rounded(6, 40, 3, rgb(p["accent"]), rgb(p["accent_dark"]), None, 0))
    return track, thumb


# ---------------------------------------------------- контраст (WCAG)
def luminance(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def colour_table(name, p):
    pairs = [
        ("Основной текст на фоне", p["text"], p["bg"]),
        ("Текст списка на поле списка", p["text"], p["panel"]),
        ("Вторичный текст на поле списка", p["text_second"], p["panel"]),
        ("Текст выделенной строки", p["hl_text"], p["hl_fill_bot"]),
        ("Текст выделенной строки (верх градиента)", p["hl_text"], p["hl_fill_top"]),
        ("Текст софт-клавиш на control pane", p["softkey_text"], p["softkey"]),
        ("Текст статус-панели", p["text"], p["status"]),
        ("Текст popup", p["text"], p["panel"]),
    ]
    rows = []
    for label, fg, bg in pairs:
        rows.append({"role": label, "fg": fg, "bg": bg, "contrast": contrast(rgb(fg), rgb(bg))})
    return rows


# ------------------------------------------------------ превью-экран
def font(size, bold=False):
    f = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(f, size)
    except OSError:
        return ImageFont.load_default()


def make_mock(p, assets):
    scr = assets["background"].copy()
    scr.alpha_composite(assets["statuspane"], (0, 0))
    d = ImageDraw.Draw(scr)
    d.text((10, 8), "Beeline", font=font(15, True), fill=rgb(p["text"]))
    d.text((10, 26), "Без звука", font=font(10), fill=rgb(p["text_second"]))
    # вкладки
    for i in range(6):
        t = assets["tab_active"] if i == 5 else assets["tab_inactive"]
        scr.alpha_composite(t, (i * TAB_W, STATUS_H))
    y0 = STATUS_H + TAB_W - 8
    rows = ["Настройки", "Заметок на сегодня нет", "Поиск WLAN выключен", "Поиск", "Настроить чат и интерн.-тел."]
    for i, text in enumerate(rows):
        y = y0 + i * ROW_H
        scr.alpha_composite(assets["list_item_bg"], (0, y))
        if i == 0:
            scr.alpha_composite(assets["list_highlight"], (0, y))
        d.text((28, y + 5), text, font=font(11), fill=rgb(p["hl_text"] if i == 0 else p["text"]))
        d.rectangle([6, y + 6, 20, y + 18], outline=rgb(p["accent"]))  # место под оригинальную иконку
    # popup
    pop = assets["popup"].resize((120, 26), Image.LANCZOS)
    scr.alpha_composite(pop, (118, y0 + 6))
    d.text((124, y0 + 12), "Перекл. на Личный", font=font(9), fill=rgb(p["text"]))
    # кнопка
    scr.alpha_composite(assets["shortcut_button"], (150, H - SOFTKEY_H - 38))
    # софт-клавиши
    scr.alpha_composite(assets["controlpane"], (0, H - SOFTKEY_H))
    for text, x in (("Меню", 6), ("Открыть", 92), ("Контакты", 168)):
        d.text((x, H - SOFTKEY_H + 7), text, font=font(12, True), fill=rgb(p["softkey_text"]))
    return scr


def main():
    manifest = {
        "target": "Nokia E52, S60 3rd Edition FP2, 240x320 portrait",
        "status": "ASSETS ONLY: .skn/.sis не собран; собирать в Carbide.ui Theme Edition (S60v3 FP2)",
        "geometry": {"screen": [W, H], "status_pane_h": STATUS_H, "control_pane_h": SOFTKEY_H,
                     "list_row_h": ROW_H, "tab": [TAB_W, TAB_H], "menu_grid_cell": [GRID_W, GRID_H],
                     "menu_grid": "3 columns x 4 rows"},
        "assets": {},
    }
    nine = {"list_highlight": [6, 6, 6, 6], "popup": [10, 10, 10, 10], "input_field": [6, 6, 6, 6],
            "grid_highlight": [12, 12, 12, 12]}
    colours = {}
    for name, p in PALETTES.items():
        d = os.path.join(OUT, "assets", name)
        os.makedirs(d, exist_ok=True)
        track, thumb = make_scroll(p)
        assets = {
            "background": make_background(p, name),
            "statuspane": make_statuspane(p),
            "controlpane": make_controlpane(p),
            "list_highlight": make_list_highlight(p),
            "list_item_bg": make_list_item_bg(p),
            "grid_highlight": make_grid_highlight(p),
            "popup": make_popup(p),
            "input_field": make_input(p),
            "tab_active": make_tab(p, True),
            "tab_inactive": make_tab(p, False),
            "shortcut_button": make_shortcut_button(p),
            "scroll_track": track,
            "scroll_thumb": thumb,
        }
        for k, img in assets.items():
            fn = "%s.png" % k
            img.save(os.path.join(d, fn))
            manifest["assets"].setdefault(k, {"file": fn, "size": list(img.size)})
            if k in nine:
                manifest["assets"][k]["nine_slice_margins_ltrb"] = nine[k]
        os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
        make_mock(p, assets).save(os.path.join(OUT, "preview", "mock_%s_240x320.png" % name))
        colours[name] = {"palette": p, "contrast": colour_table(name, p)}

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "colours.json"), "w", encoding="utf-8") as f:
        json.dump(colours, f, ensure_ascii=False, indent=2)

    # сводный лист для беглого просмотра
    sheet = Image.new("RGBA", (W * 2 + 30, H + 20), (200, 204, 210, 255))
    for i, name in enumerate(PALETTES):
        sheet.alpha_composite(Image.open(os.path.join(OUT, "preview", "mock_%s_240x320.png" % name)), (10 + i * (W + 10), 10))
    sheet.save(os.path.join(OUT, "preview", "overview.png"))

    bad = [(n, r) for n, c in colours.items() for r in c["contrast"] if r["contrast"] < 4.5]
    for n, r in bad:
        print("WARN contrast <4.5 [%s] %s: %s" % (n, r["role"], r["contrast"]), file=sys.stderr)
    print("OK:", len(manifest["assets"]), "assets x", len(PALETTES), "themes")


if __name__ == "__main__":
    main()
