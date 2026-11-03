# NOKIA / SymPort asset pack

Original vector artwork made for the independent project [E52Modern](https://github.com/grayhex/e52modern). Inspired by classic Nokia-era proportions. **Not an official Nokia logo** or brand partnership.

## Brand
- `brand/nokia-blue.svg`: standalone blue NOKIA wordmark drawn as vector paths; no fonts required.
- `brand/nokia-navy.svg`, `brand/nokia-white.svg`: contrast variants.
- `brand/nokia-symport-horizontal.svg`: main lockup for SymPort splash/sidebar, with E52 MODERN subtitle.
- `brand/appmark.svg`: 1:1 icon for favicon, app and PWA, PNG 32 / 192 / 512 included.

## Icons
- `icons/outline/*.svg`: 18 **48×48** navigation line icons, scale to `20–24px` in sidebar. For CSS-managed color, replace `#0F172A` with `currentColor` (the source uses a hardcoded navy for portable previews).
- `icons/tiles/*.svg`: matching illustrated 128×128 square icons for cards and home pages.
- `icons/png/*.png`: rasterized 128px versions of the tiles.
- `icons.json`: names and navigation mapping.

## Practical integration
Copy assets to `symport/web_assets/brand` and `symport/web_assets/icons`. Use `brand/appmark.svg` as `/favicon.svg`, and `nokia-symport-horizontal.svg` in `.brand`. Replace symbolic characters in `<a class="nav-link">` with SVG images or inline SVG. Keep existing accessible labels. Logo sizes: 185–220 px horizontal in the 256px sidebar; standalone NOKIA ~180px wide; nav icons ~20px; card tiles 48–64px.

Existing UI palette from the repository: `#0F172A` navy, `#F8FAFC` background, `#059669` sage accent. The standalone Nokia blue uses `#124191`.

Integration: original files preserved; inline icon colors adapt to Nimbus via nimbus.css. No official brand affiliation is claimed.
