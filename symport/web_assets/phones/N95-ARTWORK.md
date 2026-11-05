# N95 handset artwork

Updated for SymPort on 2026-11-05 following the user's three photographic references. The third,
large straight-on silver N95 photo is the primary shape/control reference; the other two confirm
the original key legends and slider construction. Nokia marks identify the illustrated product.

## Silver N95

`nokia-n95.svg` is the editable production master. The old approximate vector drawing has been
replaced by a reference-based image edit: curved silver front plate, original camera/grille,
chrome navigation surround, small convex centre key, four short direction ticks, blue interlocking
menu glyph, four-corner multimedia diamond, hooked softkeys, call/end controls and pencil/C bar.
The slider is closed and the numeric keypad is hidden, as in the third supplied reference.

The SVG keeps the replaceable photographic handset layer embedded as PNG, an editable clean
silhouette, an opaque case base and a separate blank LCD. There are no external image links.
The surrounding photo background and displayed screen contents are removed. The original
image-edit output is preserved by the image tool; the master contains the production source.
This is a reference-based illustration, not a claim that the underlying photograph is original
vector work or manufacturer-provided live device data.

`nokia-n95.png` and `nokia-n95.webp` are transparent 1000×1868 exports. The UI uses the smaller
lossless WebP. The transform is uniform, preserving body proportions. `device_models.json` records
the corrected 240×320 screen placement: x=145, y=264, width=711, height=948 in the export.

## N95 8GB and unresolved variant

The black `nokia-n95-8gb.svg` remains the separate original vector master with its larger screen
and distinct key assembly, not a recolored silver N95. Its source drawing is distributed under the
repository MIT license. The family SVG is deliberately schematic and only shown for an unresolved
variant. Neither uses a screen image as evidence of a phone connection.

Earlier public photographic layout references inspected (not redistributed):

- [Closed original N95 front](https://commons.wikimedia.org/wiki/File:Nokia_N95_Front_1.jpg)
- [N95 and N95 8GB side by side](https://commons.wikimedia.org/wiki/File:Nokia_N95_and_Nokia_N95_8GB.jpg)
- [Nokia N95 specifications / physical differences](https://en.wikipedia.org/wiki/Nokia_N95)

## Reproduction and review

```sh
# Export both maintained masters, including the corrected silver reference-based SVG:
SYMPORT_BROWSER_EXECUTABLE=/path/to/chromium node tools/assets/render_phones.cjs
# Optional: regenerate only the separate legacy black vector master:
python tools/assets/draw_n95.py
```

Requires Playwright and Pillow. The silver master must be edited directly; the legacy vector
generator refuses to replace it. Tests check embedded content, alpha/padding, proportions and native
LCD alignment. `tools/check_n95_ui.cjs` captures 180/240 px review sheets and responsive UI
screenshots. These captures use explicit synthetic observations, never a physical phone claim.
