# Nokia N8 / E7 handset artwork

Separate reference-based illustrations prepared for SymPort, 2026-11-06:

- **N8:** dark charcoal anodized body, tapered endcaps and the actual lower-left menu key.
  [Original Nokia product gallery reference](https://fdn.gsmarena.com/vv/reviewsimg/nokia-n8/gal/ofic/gsmarena_001.jpg).
- **E7 closed:** its own silver aluminum body, centered menu key, camera/grille and black glass.
- **E7 open:** a separate landscape tilt-slider/QWERTY view, not a rotated/recolored N8 or N97.
  [Original E7 closed/open product reference](https://fdn2.gsmarena.com/vv/pics/nokia/nokia-e7-1.jpg).

These are photo-reference image edits, not manufacturer-supplied photographs, live screens or
hardware certification. Original source photographs are not redistributed. Nokia marks identify
the illustrated products; keyboard legends in the open illustration do not determine the actual
handset's regional layout or a CFW keyboard variant.

`nokia-n8.svg`, `nokia-e7.svg`, `nokia-e7-open.svg` are maintained, self-contained editable masters:
replaceable embedded body layer, clean editable silhouette clipping for the closed views, and
a separate blank LCD layer. The open illustration retains its perspective and blank screen;
it is not a perspective-correct emulator or theme overlay. No external image loads.

PNG/WebP exports have transparency and use only uniform translation/padding; no stretching.
The shared registry stores closed-view canvas/LCD geometry and both E7 illustration choices.
LCD rectangles have the native 9:16 aspect ratio, but tool availability is separate: the generic
Theme Studio frame rejects unsupported models even when a decorative handset has geometry.

Re-export just these masters (Playwright/Chromium and Pillow for lossless WebP conversion):

```sh
SYMPORT_BROWSER_EXECUTABLE=/path/to/chromium node tools/assets/render_phones.cjs nokia-n8 nokia-e7 nokia-e7-open
```

Generated source outputs are preserved separately in the execution workspace. Tests cover image
load, alpha, proportions, embedded master layers, LCD geometry, responsive UI and the E7 view
switch. There are no OS menus, proprietary ROM contents or personal data in these assets.
