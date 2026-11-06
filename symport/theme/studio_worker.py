"""Isolated, resource-bounded reuse of the existing Nokia skin compiler pipeline."""

from __future__ import annotations

import json
import resource
import subprocess
import sys
from pathlib import Path


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (60, 65))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024**2, 32 * 1024**2))
    repo, project = Path(sys.argv[1]), Path(sys.argv[2])
    spec = json.loads((project / "project.json").read_text(encoding="utf-8"))
    from symport.phone.registry import theme_profiles
    allowed = theme_profiles()
    if spec.get('profile') not in allowed:
        raise ValueError('S60 5th theme processing is not supported; Symbian^3 / Anna / Belle are also unavailable')
    sys.path[:0] = [str(repo / "tools"), str(repo / "tools/s60")]
    import build_assets as ba
    import gen_skin
    import mifbuild
    import s60inspect
    from PIL import Image

    if len(sys.argv) > 3 and sys.argv[3] == "bitmap":
        import tempfile

        task = json.loads((project / "bitmap-task.json").read_text(encoding="utf-8"))
        rows = task["bitmaps"]
        with tempfile.TemporaryDirectory(dir=project) as scratch:
            scratch = Path(scratch)
            targets = [scratch / f"{i}.bmp" for i in range(len(rows))]
            subprocess.run(
                [
                    str(repo / "tools/s60/bin/bmconv"),
                    "-u",
                    str(project / ("resource-" + task["resource"])),
                    *[str(p) for p in targets],
                ],
                check=True,
                timeout=20,
                capture_output=True,
            )
            if task["replace"]:
                bitmap = rows[task["index"]]
                image = Image.open(project / "bitmap-replacement.png").convert(
                    "L" if bitmap["depth"] == 8 else "RGB"
                )
                image.save(targets[task["index"]], "BMP")
                args = [
                    ("-8" if row["depth"] == 8 else "-c16") + str(target)
                    for row, target in zip(rows, targets, strict=True)
                ]
                subprocess.run(
                    [
                        str(repo / "tools/s60/bin/bmconv"),
                        "-q",
                        str(project / "bitmap-output.mbm"),
                        *args,
                    ],
                    check=True,
                    timeout=20,
                    capture_output=True,
                )
            else:
                Image.open(targets[task["index"]]).save(project / "bitmap-preview.png", "PNG")
        return
    geometry = allowed[spec["profile"]]["screen"]
    width, height = geometry["width"], geometry["height"]
    work = project / "generated"
    assets = work / "theme/assets/light"
    assets.mkdir(parents=True, exist_ok=True)
    ba.W, ba.H = width, height
    ba.GRID_W, ba.GRID_H = width // 3, (height - ba.STATUS_H - ba.SOFTKEY_H) // 4
    palette = spec["palette"]
    ba.PALETTES["light"] = palette
    gen_skin.ba = ba
    gen_skin.VARIANTS["light"] = {
        "uid": spec["uid"],
        "title": spec["name"],
        "real": "symportstudio",
    }
    track, thumb = ba.make_scroll(palette)
    images = {
        "background": ba.make_background(palette, "light"),
        "statuspane": ba.make_statuspane(palette),
        "controlpane": ba.make_controlpane(palette),
        "list_highlight": ba.make_list_highlight(palette),
        "list_item_bg": ba.make_list_item_bg(palette),
        "grid_highlight": ba.make_grid_highlight(palette),
        "popup": ba.make_popup(palette),
        "input_field": ba.make_input(palette),
        "tab_active": ba.make_tab(palette, True),
        "tab_inactive": ba.make_tab(palette, False),
        "shortcut_button": ba.make_shortcut_button(palette),
        "scroll_track": track,
        "scroll_thumb": thumb,
    }
    if spec.get("wallpaper"):
        images["background"] = Image.open(project / "wallpaper.png").convert("RGB")
        if images["background"].size != (width, height):
            raise ValueError("Wallpaper geometry differs from the selected profile")
    for name, image in images.items():
        image.save(assets / (name + ".png"))
    src = Path(gen_skin.generate("light", str(work), screen=(width, height)))
    with (src / "skin.txt").open("a", encoding="utf-8") as source:
        for uid in spec.get("icons", {}):
            image = Image.open(project / ("icon-" + uid + ".png")).convert("RGBA")
            stem = "app_" + uid
            masked = gen_skin.save_piece(image, str(src / "gfx" / stem))
            source.write(
                f"\nAPPICON UID=0x{uid}\n  c16 {stem}.bmp"
                + (f" SOFTMASK={stem}_mask_soft.bmp" if masked else "")
                + "\nEND\n"
            )
    out = project / "compiled"
    out.mkdir(exist_ok=True)
    temporary = out / "lists"
    temporary.mkdir(exist_ok=True)
    subprocess.run(
        [
            str(repo / "tools/s60/bin/skc"),
            "-m" + str(temporary) + "/",
            "-t" + str(out) + "/",
            "skin.txt",
            "symportstudio",
        ],
        cwd=src,
        check=True,
        timeout=30,
    )
    mifbuild.build(
        str(temporary / "symportstudio_MIFList.txt"),
        str(src),
        str(out / "symportstudio"),
        str(repo / "tools/s60/bin/bmconv"),
    )
    errors, bitmaps = s60inspect.inspect_mbm(str(out / "symportstudio.mbm"), lambda *_: None)
    issues, _ = s60inspect.inspect_mif(
        str(out / "symportstudio.mif"), len(bitmaps), lambda *_: None
    )
    errors += issues + s60inspect.inspect_skn(
        str(out / "symportstudio.skn"), str(out / "symportstudio"), lambda *_: None
    )
    if errors:
        raise ValueError("; ".join(errors))
    print(json.dumps({"status": "built", "bitmaps": len(bitmaps), "screen": [width, height]}))


if __name__ == "__main__":
    main()
