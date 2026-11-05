# Original N95 handset artwork

Created for SymPort, 2026-11-05. Editable original vector drawings, distributed under the repository
MIT license. Nokia marks identify the illustrated product; this is not manufacturer endorsement.
No reference photograph, photo pixels, firmware, proprietary UI or external SVG content is embedded.

Photographic layout/material references inspected (not redistributed):

- [Closed original N95 front](https://commons.wikimedia.org/wiki/File:Nokia_N95_Front_1.jpg)
- [N95 and N95 8GB side by side](https://commons.wikimedia.org/wiki/File:Nokia_N95_and_Nokia_N95_8GB.jpg)
- [Nokia N95 specifications / physical differences](https://en.wikipedia.org/wiki/Nokia_N95)

`nokia-n95.svg`: original silver face, purple slider rail, smaller screen, silver key assembly.
`nokia-n95-8gb.svg`: black face, larger screen and separately dimensioned black/chrome controls.
Closed-slider strict front view, full body, transparent canvas, blank LCD. Hardware shape is an
illustration, not a scan or manufacturing drawing. The optional open-slider angle is not included.
The family SVG is deliberately schematic and only shown when the variant is unresolved.

Reproduce from editable layers:

```sh
python tools/assets/draw_n95.py
SYMPORT_BROWSER_EXECUTABLE=/path/to/chromium node tools/assets/render_phones.cjs
```

Requires Playwright and Pillow. The renderer exports alpha PNG and lossless WebP at 1000×1868.
SVG layer IDs separate shell, rails, brushing, screen glass, earpiece, lens and keys for editing.
`device_models.json` records native display and screen-in-artwork geometry for Theme Studio.
Tests check alpha/padding, body aspect, separate masters and no embedded/reference-photo content.
Review sheets at 180/240 px and screenshots come from `tools/check_n95_ui.cjs`; all phone state in
these captures is synthetic and explicitly identified as such in the documentation.
