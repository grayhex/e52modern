# N95 handset artwork

Both models were corrected for SymPort on 2026-11-05 using separate original-product references.
The third user-supplied silver N95 photo defines the original model; the black N95 8GB uses the
independent [original frontal product photo](https://fdn2.gsmarena.com/vv/pics/nokia/nokia-n95-8gb-01.jpg).
Nokia marks identify the illustrated products. These are reference-based image edits, not claims
that the reference photographs are original vector artwork or manufacturer-provided live data.

## Separate hardware designs

- **Silver N95:** curved silver front plate, original camera/grille, chrome control surround,
  small convex select key, four engraved direction ticks, original blue menu glyph, multimedia
  diamond, hooked softkeys, call/end keys and curved pencil/C bar.
- **Black N95 8GB:** its own black shell and larger display, `N95 8GB` above the screen, `NOKIA`
  below it, a low horizontal chrome control assembly with black menu/multimedia keys, warm metallic
  direction ring and small glossy black select key. It is not a recolored silver model.

Both sliders are closed; hidden numeric/media keypads are not exposed. Screen contents and photo
backgrounds are removed. The family SVG stays deliberately schematic for an unresolved variant.

## Maintained masters and exports

`nokia-n95.svg` and `nokia-n95-8gb.svg` are editable production masters. Each contains its own
replaceable embedded PNG body layer, a clean editable silhouette, opaque case base and separate
blank LCD. There are no external image links. Image-tool outputs remain preserved separately;
the production SVG contains the source needed for deterministic export. The obsolete approximate
vector generator was removed so it cannot overwrite the corrected graphics.

Both export to transparent 1000×1868 PNG and lossless WebP; the app uses WebP. Transforms are uniform,
so the artwork is neither stretched nor squeezed to fill a rectangle. Rounded silhouettes and side
buttons determine the visible bounds. Display geometry lives in `device_models.json`:

| Model | LCD x/y | LCD width/height | Native preview |
|---|---|---|---|
| N95 | 145 / 264 | 711 / 948 | 240×320 |
| N95 8GB | 102 / 240 | 795 / 1060 | 240×320 |

Export both maintained masters:

```sh
SYMPORT_BROWSER_EXECUTABLE=/path/to/chromium node tools/assets/render_phones.cjs
```

Requires Playwright and Pillow. Tests check embedded content, alpha/padding, proportions, distinct
models and LCD alignment. `tools/check_n95_ui.cjs` captures 180/240 px review sheets and responsive
UI screenshots. Capture state is synthetic and never a physical-device claim.

Other photographic layout references inspected (not redistributed):

- [Closed original N95 front](https://commons.wikimedia.org/wiki/File:Nokia_N95_Front_1.jpg)
- [N95 and N95 8GB side by side](https://commons.wikimedia.org/wiki/File:Nokia_N95_and_Nokia_N95_8GB.jpg)
- [N95 8GB media-slider photo](https://fdn2.gsmarena.com/vv/pics/nokia/nokia-n95-8gb-00.jpg)
- [Nokia N95 specifications / physical differences](https://en.wikipedia.org/wiki/Nokia_N95)
