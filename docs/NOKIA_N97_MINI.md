# Nokia N97 mini

N97 mini is a separate SymPort target: **Symbian OS 9.4 / S60 5th Edition (Symbian^1)**,
360×640 portrait, 640×360 landscape with its slide-out QWERTY keyboard and touch input.
The original N97 is not treated as a mini. Themes for S60 5th are outside this implementation.

## Identity and documented facts

`profiles/nokia-n97-mini.toml` retains a source/status for every fact. The shared
`device_models.json` supplies the target name, screen modes and tool availability to Python,
React and Windows Bridge. [Nokia N97 mini specifications](https://en.wikipedia.org/wiki/Nokia_N97_mini)
are documentary references, reviewed 2026-11-05, not measurements from a connected phone.

Exact software-name forms from [issue #31](https://github.com/grayhex/s60modern/issues/31) are
normalised for case, whitespace and the stated `-1` suffix: `N97 mini`, `N97mini`, `N97 mini-1`.
Unsupported suffixes such as `mini-2` do not silently select mini. Specific registered names take
precedence over the `N97` family. Conflicting model/RM evidence has no Mini profile.

No verified RM/product-code database is shipped for mini. A reported RM is kept as an observation;
`RM-555` alone does not identify mini. Plain `N97` remains generic N97 with no Mini geometry,
toolchain target or artwork. Discovery never infers mini from a drive capacity, display size or
Bluetooth friendly name. Manufacturer/serial/paired-device host records are **candidates** until
a real phone/transport probe answers.

Firmware version, product code, current screen/slider state, write permissions and mounted volumes
remain unknown until reported. The documented 8 GB internal mass memory and microSDHC design does
not create a drive mapping or a free-space counter. There is no verified Mini handset illustration
in this change: Dashboard and Inspector use the existing **labelled generic placeholder**, without
passing it off as a miniature N97 body or a live screen.

## Connect through the existing Bridge

Use [Windows Bridge](WINDOWS_BRIDGE.md) or the existing local Linux adapters. In the browser open
**Connection** and the first-connection wizard. Choose the connection you actually configured;
phone identity and a mounted filesystem may appear as separate rows.
The Windows discovery and connection-reset fixes require Bridge **0.3.1** or later; installer and
portable builds are produced by the existing Windows workflow.

| Connection | Evidence needed | Available scope |
|---|---|---|
| USB PC Suite / Nokia Suite | Nokia serial candidate, working driver, Gammu identity reply, then individual status calls | Identity and only the telemetry/PIM stores that answer |
| USB Mass Storage | Actual Nokia USB/CIM disk association and observed volume, or operator-enrolled Linux mount | Exposed filesystem, media and file backup; no phone identity, PIM or `C:` inference |
| Bluetooth Gammu / RFCOMM | Paired host connection, configured driver/COM port and actual identity/store replies | Same per-store probes as USB, independently scoped |
| OBEX FTP | Trusted installed ObexFTP, actual USB interface or SDP-reported Bluetooth channel, successful listing/read | Only the server-exposed namespace; fresh-folder transfers with read-back where supported |
| OBEX OPP | Explicit paired destination/service | Package push receipt; no browse, PIM, read-back or installation claim |
| Gammu S60 Remote | Voluntary compatible applet/runtime and a working existing Gammu S60 profile | Whatever its status calls actually prove; no automatic applet installation |

On Windows, ObexFTP is **not bundled**. A profile requiring an absent executable reports the
reason; it does not become supported because the target is mini. Gammu/libGammu support depends
on the actual driver, wheel/platform build and phone mode. No new protocol, Nokia USB driver,
firmware, phone applet or system patch is included. Existing source/license boundaries are in
[TRANSPORTS.md](TRANSPORTS.md).

Windows USB disk discovery accepts removable and fixed USB mass-memory volumes only behind the
existing Nokia physical-disk association, excluding the system drive. This accommodates phones
whose internal mass memory is reported as a fixed disk. Native connection configuration changes,
USB mode, Bluetooth destination and filesystem root/device/inode changes alter fingerprints.
PIM previews are discarded on changed config/observed identity or disconnect; write proofs do not
follow a different root. Auto-discovered USB disk identity changes refresh enrollment and clear
old proofs, even when Windows reuses the same drive letter. Config fingerprints use an ephemeral
HMAC; no raw configuration, PIN, root path, USB identifier or contact content is added to logs.

## Common workflows

- **Dashboard / Diagnostics:** returned model, RM/firmware, link and actual counters; missing values
  stay unavailable. Screen modes are documented capabilities, not a measured slider position.
- **Files / Media / Ringtone Studio:** use an explicitly chosen filesystem or usable OBEX path.
  Protected-path, overwrite, confirmation, SHA/read-back and size limits remain in force. Downloading
  an MP3 or copying it to a folder does not prove the phone can use it as its active ringtone.
- **Contacts / SMS / Calendar / Tasks:** each native store is probed separately. Unavailable reads
  show the driver's reason, not a successful empty list. Export JSON/vCard/iCalendar where supported;
  full native iCalendar encoding uses python-gammu (included in Docker/Windows Bridge). If a driver
  cannot read the store, export vCard/iCalendar with Nokia Suite and import that file. Direct writes
  keep the existing backup, preview, explicit confirmation and read-back requirements. SMS send
  remains blocked without a verified send profile and confirmation.
- **Backup / Restore:** file backup covers only the selected filesystem/folder. PIM snapshots are
  separate. A file ZIP is not a complete system backup or factory-reset recovery image.
- **Applications:** select `Nokia N97 mini` in Catalog, Collections or Inspector. SIS/SISX/JAR/JAD
  delivery uses the actual transfer capability; delivery never means installation. Installed-app
  state is not inferred from static catalog entries or a directory of packages.

## Compatibility and theme boundary

Mini's documented product UID is **`0x1028315F` (S60 5th)**. S60 3rd/FP1/FP2-only prerequisites are
not automatically accepted. A package declaring both 3rd and 5th can satisfy the platform check;
that says nothing about touch usability, native APIs, certificates or runtime execution. Unknown
product IDs/versions remain unknown. Native ABI/capability/signature checks are reused, and DLL
availability stays unknown without an exact user-supplied Mini firmware profile.

Catalog model/platform evidence is separate from E52/E72/N95 results. Collections include Mini's
platform and geometry but do not turn an untested set into a verified recovery kit.

**Theme Studio does not create, import, build or preview Mini themes.** It displays «Пока не
поддерживается» / “Not supported yet”; creation/import controls are disabled. The backend rejects
Mini targets and retargeted projects before generating files. The isolated resource worker has the
same guard. No S60 5th SKN/MBM/MIF templates or theme packages have been added. Generic file delivery
of a user-owned package is not a Mini theme installation feature.

## Physical N97 mini checklist — not tested on device

1. Save consented model text, RM, firmware, OS/driver and transport in a private report; redact IMEI
   and do not paste contacts or messages into ordinary logs.
2. Confirm `N97 mini` from the handset response. Compare a plain `N97` or RM-only reply: it must not
   silently become mini. Record regional codes separately before adding a sourced mapping.
3. Start in PC Suite/Nokia Suite USB mode with the appropriate original driver. Record candidate,
   identity probe and **each** store's actual `available/not-tested/unsupported/error` result.
4. Read/export a small contact set, calendar and tasks. Try SMS reading only when its probe permits
   it; keep SMS sending disabled unless a verified transport is explicitly enrolled.
5. Switch to Mass Storage. Check internal memory and microSD as actual separate volumes. No native
   PIM or `C:` access should appear. Download a harmless file and inspect media on the chosen volume.
6. Review backup coverage. Explicitly confirm a small new-file transfer, compare bytes/hash and
   test a conflict/overwrite rejection. Preview restore before any write; preserve an original copy.
7. Switch USB modes, reconnect, replace a volume and switch Bluetooth/USB profiles. Old available
   capabilities, PIM previews and data views must not carry across the changed connection.
8. Pair Bluetooth in Windows/Linux and verify real SDP services. Test Gammu, FTP and OPP separately;
   absence of FTP or an executable is a reported limitation, not a reason to fabricate support.
9. Inspect a benign 5th-edition SIS and a 3rd-only SIS. Record transfer and manual installer outcome
   separately. Check firmware-bound analysis without claiming actual installation from a green check.
10. Confirm Mini's Theme Studio remains unavailable. Do not flash, jailbreak, patch the system,
    change installer security or apply themes as part of this checklist.

Hardware status remains **not-tested** until a real Mini/firmware/transport report exists. CI,
stateful mock Gammu records, temporary filesystem volumes and emulator success are not handset tests.

## Review screenshots

The screenshots use an explicitly synthetic Mini identity and stateful test stores. Files are read
from a real temporary filesystem; production discovery contains no demo phone.

[390px](screenshots/n97-mini/overview-390.png) · [768px](screenshots/n97-mini/overview-768.png) ·
[1366px](screenshots/n97-mini/overview-1366.png) · [Contacts](screenshots/n97-mini/contacts.png) ·
[Inspector](screenshots/n97-mini/inspector.png) ·
[Unavailable themes](screenshots/n97-mini/themes-unavailable-1366.png) ·
[Russian / mobile](screenshots/n97-mini/themes-unavailable-ru.png).
