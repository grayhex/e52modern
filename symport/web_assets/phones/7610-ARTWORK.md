# Nokia 7610 Black / Ruby Red artwork

Reference: the product photograph of the original Nokia 7610 supplied by the user in this
conversation on 2026-11-06. It shows the black outer body, chrome left edge, curved ruby-red
insert and the distinctive diagonal, sculpted keypad. It is not the 7610 Supernova.

The replacement is a photo-reference-based generated illustration, following the realistic
handset treatment used by the other SymPort models. The previous generic vector body and
regular keyboard have been removed. The reference photograph itself is not redistributed.
The LCD is inactive black glass, without the reference's handshake image or a baked-in UI.
Nokia branding identifies the illustrated product; the asset does not establish hardware or
emulator compatibility.

`nokia-7610.svg` is self-contained: an embedded replaceable RGBA body, editable canvas clipping
and a separate LCD guide. It is not a fully vector-traced photograph. The 840×1674 canvas uses
only translation/cropping of transparent margins; the handset is never stretched. The guide
is decorative and does not enable S60 2nd Edition theme previews or emulator controls.

`nokia-7610.png` and lossless `nokia-7610.webp` are transparent exports of the master. Dashboard,
sidebar and model cards share the existing registry's WebP URL, avoiding an old cached PNG.

Re-export using the existing asset pipeline (Chromium, Playwright and Pillow):

```sh
SYMPORT_BROWSER_EXECUTABLE=/path/to/chromium node tools/assets/render_phones.cjs nokia-7610
```

Browser screenshots in `docs/screenshots/nokia-7610-overview*.png` use the existing explicit
identity-only test transport, not a connected physical 7610.
