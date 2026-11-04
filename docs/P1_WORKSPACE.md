# App collections, Theme Studio & diagnostics

All three modules use the existing authenticated Python API and React/TypeScript UI.
Device operations use the same `DeviceManager` instance as Windows Bridge, Linux
transports, Catalog and Certificate Inspector. No second transport or installer exists.

## Collections & recovery — Applications → Application kits

The existing runtime/ZIP kit builder remains available. The collection editor below
it offers Basic, Internet, Multimedia and Tools starting selections. Templates include
manual-source entries; selecting a template does not assert that its apps are available.

1. Name a collection, select E52 (Symbian 9.3, 240×320) or E72 (9.3, 320×240), choose apps.
2. Save. The manifest pins catalog IDs, versions, required catalog dependencies,
   artifact filenames, sizes and SHA-256. No software or personal data goes into JSON.
3. Export/import `symport.collection/1` JSON (128 KiB, 50 apps). Imported URLs,
   commands, device IDs and installation claims are discarded.
4. Select the new/reset phone connection and target profile, then **Preview recovery**.
   A changed version/hash requires review and saving fresh pins. Missing/manual,
   incompatible, high-risk or unresolved dependency entries cannot be transferred.
   Conflicts and a model mismatch block the batch. Different screen orientation is
   highlighted; an unknown card identity is not treated as a confirmed phone model.
5. Explicitly acknowledge omissions for a partial set, then confirm transfer.
   The server recomputes the preview digest against current catalog and connection
   evidence. The existing catalog queue downloads, verifies and transfers in dependency
   order, retaining per-file results. Review that journal before retrying a failed batch.
6. Open the packages on Nokia and complete installation in the displayed order.
   Restore contacts/calendar/files from their separate backups. A collection does
   not restore application settings, licenses, save games or installed state.

Existing legacy saved selections are migrated once, retaining the old file. Their original versions/hashes are unknown (`legacy-unpinned`), so review and re-save before recovery; current pins are never substituted as historical evidence. Catalog saves selections into this same collection service; the legacy `save-set` API remains for compatibility.

Maximum 40 local collections. A preview is bound to saved content, device and target;
unsaved editor changes are not a saved recovery manifest. Previews expire after ten minutes and are consumed before queuing any write. The server rejects a stale or already-used
preview, but this is not an atomic installer: disconnects can leave a partially sent set.

## Advanced Theme Studio — Personalisation → Theme editor

**Editable CLEAR projects:** all declared palette roles, contrast readings, centre-cropped
wallpaper, 48×48 RGBA application icons keyed by real app UID. Both native screen profiles
are compiled, not just stretched in the browser. Menu/list/dialog previews sit inside
existing E52/E72 artwork and retain native pixel proportions. They are schematic;
firmware determines actual system layout and where skin resources are used.

**Import:** upload a SIS/SISX theme (8 MiB). The shared SIS reader/validator checks
checksums and payload hashes, extracts at most 100 files/16 MiB and inventories
MBM/MIF/SKN targets, dimensions, bit depths and SHA-256. The uploaded original is
retained. Only whitelisted skin paths can be repacked; executable, conditional,
embedded, multilingual, nonstandard file-operation or undecoded package semantics block export when they cannot
be preserved. Product-specific target/version constraints also block a lossy repack.

**Resources:** export original resources, inspect MIF reference tables and SKN envelope,
preview supported MBM bitmaps through existing Nokia `bmconv`, replace a selected
bitmap with PNG, or replace a whole validated MBM/MIF/SKN. The bitmap editor preserves
index order, dimensions and depths; only 8-bit grey/16-bit RGB without palettes are
supported. Other depths/palettes and embedded SVG-T stay opaque. A generated CLEAR
project regenerates MBM from its design inputs; import its SIS for individual bitmap edits.
Compiled SKN colour/item tables are not reversibly decoded. Imported appearance is
therefore shown only in Emulator Lab; the editor labels the reference illustration.

**Build:** explicit acknowledgement produces an **unsigned** SIS using the existing
Nokia Skin Compiler, `bmconv`, MIF builder and native SIS writer. CLEAR projects get
random development UIDs. Repacked imports preserve the skin UID and declared dependencies,
raise the patch version, and replace publisher/name metadata with the new project;
original signatures are removed. Installing such an update can replace an existing theme; keep its original installer. Nokia may reject unsigned or expired certificates.
The tool does not sign with someone else's identity or alter installer protection.

Static checks cover generated resource consistency, SIS CRC/payload hashes and exact
extraction round-trip. `static-checked` does not mean installed or hardware-tested.
Inspector and Emulator Lab resolve the same built bytes and recheck their hash. A theme
is applied through Symbian's Themes menu, never launched by UID. Inspector offers
explicit phone transfer; installation still takes place on Nokia.

No new theme engine/compiler was written. Native processing runs in a separate Linux
worker: 60 seconds CPU, 768 MiB address space, 32 MiB output-file ceiling, 50/90 seconds
wall timeout. Input raster images are limited to 4 MiB/16 MP and normalized before
compilation; MBM decode has per-bitmap and aggregate pixel limits. Commands use argument
arrays, no shell. The Docker image already builds the required vendored tools.

Projects (maximum 40) live in private `build/symport/theme-studio/<id>` folders in the
existing persistent build volume. They remain until explicitly deleted; original uploads,
normalized design assets, resources and output are all removed with that project.
The supported deployment is the existing Linux Docker backend; Windows Bridge only
handles phone transport and does not need a compiler.

## Device diagnostics — Tools → Diagnostics

Choose a connection and **Read measurements**. Discovery and, where advertised,
`device-details` supply model, RM, firmware, battery/signal percentages, storage
free/capacity, USB mode, service statuses and lifetime hours. Unknown/non-finite,
invalid or inconsistent values remain absent; 0% is a measured zero. Storage counters
are not free RAM. Mounted storage cannot supply battery, SMS or a handset identity.
Current adapters do not expose Nokia's lifetime counter; no counter is inferred.

Optional recording every 15 seconds runs only while the view is active. At most 500
samples per connection are retained. Charts preserve gaps, percentages use a 0–100
axis, storage has its own scale. Series are separated by reported model/RM/firmware/
transport; this is not a unique handset identity, so clear the history when replacing
a phone by another of the same model on the same connection. No automatic trend or
battery-health estimate is invented.

JSON/CSV reports contain only whitelisted measurements and service status codes, never
IMEI, fingerprints, SMS, contact data, phone paths or raw transport errors. CSV values
are protected against formula interpretation. The logical operation journal records
only action, status and time. Histories persist in the build volume and can be cleared
with confirmation; they are private but not encrypted backups.

## API / verification

Existing session token, Host and Origin checks apply to `/api/catalog` collection
operations, `/api/theme-studio` and `/api/diagnostics`. None exposes an unauthenticated
phone-control endpoint. Bridge pairing and native approval remain unchanged.

`tests/test_p1_workspace.py` covers pinned recovery, dependency ordering, stale previews,
partial consent, imports, data privacy, actual compiler output for both profiles,
MBM replacement and Inspector's byte-identical transfer. Compiler checks run after
`tools/s60/build.sh`; no external app binaries or ROMs are test fixtures.
`tools/check_p1_ui.cjs` exercises the browser against the real Python backend/compiler
with explicit catalog/transport/MGO doubles, including RU/EN, themes and mobile layout.
No test result here establishes physical E52/E72 compatibility.

The Docker CI job also runs `python tools/check_p1_container.py --image <built-image>`:
non-root API/compile checks for both profiles, session/Origin rejection, collection
pins, then container replacement against the same temporary volume and SIS hash
verification. Only its uniquely named disposable container/volume are removed.
