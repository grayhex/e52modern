# Nokia S60 transports

Research and implementation audit: 2026-11-03. Scope is **Nokia / S60 3rd and 5th
Edition only**, with E52 / Symbian 9.3 / 3rd FP2 the primary manual-test target.
No Sony Ericsson protocols, flashing, jailbreak or security changes are enabled.

## Existing architecture and changes

The existing `DeviceManager` is the single action/capability/journal boundary.
`LocalTransports` still composes enrolled mounted volumes and Gammu; its Gammu
implementation is extracted to `GammuAdapter`, shared by configured USB, Bluetooth
and S60 Remote profiles. The existing native Gammu worker, PIM snapshots, previews,
backups, confirmation and read-back verification are reused, not reimplemented.
`ObexAdapter` invokes an installed ObexFTP executable. No third-party protocol code
was copied into SymPort. The old authenticated loopback `PCBridge` remains usable
on Linux and Windows.

Windows Bridge uses that same manager in a portable tray executable. Browser pairing
opens an **outbound** authenticated HTTPS lease; backend workflows, including Catalog,
Inspector, Lab and media Range responses, continue through the same manager. No phone
API is opened on the LAN/Internet. See [WINDOWS_BRIDGE.md](WINDOWS_BRIDGE.md).

A profile is a connection, not another invented phone. The UI chooses among actual
responses or explicitly configured OPP destinations. Capabilities come from store
probes/OBEX listing, not the connection name. Host USB/Bluetooth records are shown as
candidates; a friendly Bluetooth name is not device identity. Model-to-edition data
is labelled a documented reference, not a measured OS version.

## Source audit and licenses

| Source | Audited version | Finding / reuse | License boundary |
|---|---|---|---|
| [Gammu](https://github.com/gammu/gammu) | `f78a98d43b713e909b4f59f69b13e0fca6e3c109` | Existing public libGammu/python API; USB serial, Bluetooth and S60 driver | libGammu GPL-2.0-or-later; python-gammu GPL-2.0-or-later. Existing MIT SymPort source is compatible; combined Windows distribution GPL-3.0-or-later with corresponding sources |
| [Series60-Remote](https://sourceforge.net/projects/series60-remote/) | Project listing 0.4.0 / GPLv2; Gammu applet source examined | Historic desktop Python/PyQt stack is not embedded. Reuse Gammu's extended applet driver instead | SourceForge identifies GPLv2. No original desktop/app code redistributed |
| [S60 protocol](https://docs.gammu.org/protocol/s60.html) | Gammu protocol documentation and `libgammu/phone/s60/s60phone.c` at commit above | Extended protocol is **not fully compatible** with original Series60-Remote. Read/write support depends on actual Gammu driver/app combination | Protocol implementation remains in separately licensed Gammu |
| [ObexFTP](https://github.com/zuckschwerdt/obexftp) | `79b3a4bc8731b009f65d0705f3223bf834e4d894` | External executable; USB or Bluetooth FTP, explicit-channel OPP | Component-wise licensing: library/CLI source headers LGPL-2.0-or-later; other tools GPL-2.0-or-later. Do not assume the whole repository has one license |
| [s60v3-obex](https://github.com/fizolas/s60v3-obex) | `de1cac245c0c906708f040fc3a12e4fe565e3ae9` | Debian wrapper around bluetoothctl/sdptool/obexfs; useful host-service discovery reference. No script execution/copy | GPL-3.0. Its sudo/rfkill toggles, mount mutation and shell loops are deliberately not incorporated |

The Windows build uses official x64 python-gammu wheels; their bundled libGammu
version is recorded by the **actual frozen worker**. ObexFTP is not bundled for
Windows. The distribution includes own sources/build recipe, Gammu/python-gammu
and pystray sources, GPL text and dependency metadata. No proprietary Nokia driver,
unsigned SIS applet, Nokia SDK, firmware or signing key is packaged into Bridge.exe.

## Compatibility and capability matrix

All physical E52 transport rows below: **не проверено на устройстве**. Successful
mock, host enumeration and executable checks do not change that status.

| Connection | Identity / diagnostics | Files / packages | Contacts, SMS, calendar/tasks | Restrictions |
|---|---|---|---|---|
| Enrolled USB Mass Storage | Real accessible filesystem/free space; no model inference from drive letter | List, upload/download, safe mkdir/delete, gallery/Range/ZIP, file backup | No direct stores; Google CSV / Apple vCard preparation and vCard file staging remain available | Card only. Not internal C:/, installed-app registry, phone firmware or battery |
| USB Serial / PC Suite + Gammu | Real model/manufacturer/firmware and supported battery/signal getters | No automatic file capability from an AT response | Each store separately probed; unsupported AT stores remain disabled | Nokia COM driver needed on Windows. Nokia Suite may hold the port. Modern driver signing/OS availability varies |
| Bluetooth Classic + Gammu | Configured paired device / actual driver response | No file support inferred from SPP/RFCOMM | Depends on selected Gammu driver and real store probes | Pair in OS first; use discovered service/channel/COM profile. No automatic pairing or rfkill changes |
| Bluetooth S60 Remote + Gammu | `blues60` / `bluerfs60`, extended optional on-phone applet | Gammu S60 file getters/putters are **NOTIMPLEMENTED** in audited driver | Driver implements contacts/SMS/calendar/tasks; SymPort still probes stores and read-back before claiming writes | Original applet may be incompatible; Python for S60 2.0 / PIPS / signing dependencies are obsolete/variant-dependent |
| Bluetooth OBEX FTP | Successful actual XML folder listing | Exposed folders, regular files up to 64 MiB; staged upload, SIS/SISX/JAR transfer with SHA-256 read-back | No PIM or automatic installation | No delete, arbitrary mkdir, overwrite, streaming gallery or private/system access. Staging blocked on Z: and C:/sys, C:/private, C:/system |
| USB OBEX FTP | Explicit ObexFTP USB interface + actual listing | Same FTP wrapper | No PIM | Requires a suitable OpenOBEX/libusb build, OS access and correct USB mode; interface indices may change |
| Bluetooth OBEX OPP | Explicit paired address/channel; **configured**, not claimed connected | Confirmed push to inbox; receiver acknowledgement only | No phonebook import, listing, download or install result | Missing ObexFTP disables capability. No chosen destination folder; receiver consent required |
| Gammu OBEX profile | Explicit Gammu config and actual device/store probes | Only operations exposed by the shared Gammu adapter | Only successful probes | A Gammu OBEX connection is not interchangeable with this external ObexFTP wrapper |
| Future native E52 agent / SyncML | Extension point only | Not advertised | Not advertised | SyncML synchronization is stateful/conflict-sensitive. No working integration is claimed |

JAD through OBEX is currently blocked: separate staging cannot guarantee its paired
JAR in the same directory. Use a JAR-only package or a mounted card. Sending an SIS,
SISX or JAR never establishes installation; confirm installation on the Nokia screen.
Emulator success remains separate from physical-device results.

## Capability matrix (single source of truth)

Capabilities belong to a **connection**, not to a phone model. Every device row returned by
`discover` carries `capability_matrix`: one entry per operation (`identity.read`,
`telemetry.read`, `storage.read`, `files.list|download|upload|stage|mkdir|delete`, `media.read`,
`packages.transfer|opp-push`, `contacts.read|write|stage`, `calendar.read`, `tasks.read`,
`sms.read|send`, `apps.registry`, `install.run`) with

| Field | Meaning |
|---|---|
| `status` | `available` — a safe probe of *this* adapter succeeded; `not-tested` — nothing proved it; `unsupported` — the transport cannot do it; `error` — the probe failed (fixed reason in `evidence`) |
| `attempt` | `verified`, `unverified` (a read that was not probed; the read itself is the probe), `confirmed-only` (a write, never probed, runs only after an explicit confirmation) or `blocked` |
| `source`, `evidence`, `checked_at` | where the answer comes from (e.g. `gammu-native:GetMemoryStatus`, `obex-ftp:folder-listing`, `mounted-volume:listdir`, `observed-operation`) and when |

The flat `capabilities` list and `capability_status` are **derived** from the matrix for older
clients and contain only verified operations and confirmed-only writes. `capability_fingerprint`
(connection id, transport, profile, model, RM, firmware — no IMEI) identifies the connection;
it changes when another phone, link or firmware answers.

Rules enforced by the adapters and `DeviceManager`:

- `gammu identify` proves **identity only**. Contacts/calendar/tasks become `available` only
  after the native store-status call (`GetMemoryStatus`, `GetCalendarStatus`, `GetToDoStatus`,
  `GetSMSStatus`) succeeds; `ERR_NOTSUPPORTED/NOTIMPLEMENTED` is `unsupported`, any other error
  is `error` with the Gammu code. Without python-gammu the CLI export path stays
  `not-tested`/`unverified` and the verified React workflows are disabled with that reason.
- Mass Storage: only `files.list`, `storage.read` (and `files.download`/`media.read` after a
  one-byte read of an existing file) are probed. No identity, battery, PIM, application registry
  or installation. Read-only per OS flags → write operations `unsupported`.
- OBEX FTP: a successful folder listing is the only probe. No delete/mkdir/direct write/gallery.
  OBEX OPP: `packages.opp-push` is configured, not discovered; the receiver acknowledgement is
  not a file browser, not a listing and never an installation.
- Writes are **never probed** (no test writes, no SMS). A write operation turns `available`
  only after a confirmed, verified operation of that kind on the same connection fingerprint
  (`observed-operation`, kept in memory). The proof is dropped on disconnect or when the
  fingerprint changes; failed or unverified results (`submitted-to-network`,
  `received-by-opp-not-installed`, partial) prove nothing. Reading never implies writing.
- `install.run` and `apps.registry` are `unsupported` for every transport: SymPort never installs
  and copying a package is not an installation.
- A peer (older Bridge) that sends no matrix is **not trusted**: every operation is `not-tested`
  and blocked until the Bridge is updated. Matrices from a Bridge are validated (unknown
  operations/statuses dropped, attempts re-derived).
- `{"action":"capabilities","device":"<id>"}` re-probes one connection (reads only) and returns
  the fresh row; the React *Connection* page exposes it as “Recheck (read-only)”.

React (`useCapabilityGuard`) removes cached files/personal/media/diagnostics data of a connection
as soon as its fingerprint changes, it disconnects or discovery fails, so “available” from the
previous phone is never shown for the next one. Buttons of impossible actions are disabled with
the reason (`CapabilityHint`). The dashboard shows storage counters only from the selected
connection; a mounted volume is shown for a phone only after the user links it explicitly (the
link is bound to the phone's fingerprint).

All of the above is verified with mocks and fake transports only; **physical Nokia E52 results
are not tested**.

## First connection diagnostics

The React *Connection* page contains the first-connection wizard (see
[FIRST_CONNECTION_E52.md](FIRST_CONNECTION_E52.md)). Its states come from: `GET /api/connection`
(mode, relay heartbeat), the Bridge probe, `connection-host` (COM, drives, Bluetooth, USB
VID/PID without serials, environment), `discover` rows (`failure.reason`, matrix) and the
capability probes above. Modes are told apart by what the connection reports: PC Suite (Gammu
USB), Mass Storage (memory card files only), Bluetooth (Gammu/S60 Remote/OBEX FTP), OBEX FTP
over USB, OBEX OPP (send only) and unsupported (not a Nokia S60 3rd/5th Edition model).
Not verified on a physical E52.

## Configure connections

Keep the legacy `SYMPORT_GAMMU_CONFIG` and `SYMPORT_DEVICE_ROOTS` settings if already
working. Additional profiles are read from an operator-owned absolute path in
`SYMPORT_CONNECTIONS_FILE` on Linux, or selected in Windows tray settings. JSON schema
1 accepts at most 24 unique Nokia/S60 3rd/5th profiles. HTTP cannot enroll filesystem
roots or arbitrary Gammu config paths. Invalid additional configuration leaves legacy
Gammu/volumes available and produces a diagnostic.

Copy [examples/connections.json](examples/connections.json), **remove unused profiles**,
replace absolute paths, paired MAC addresses and SDP channels. Example channel numbers
are not E52 defaults. Linux configuration paths use `/home/you/...` instead of Windows
paths. An explicit USB OBEX profile uses `"transport":"usb","interface":0` and no
Bluetooth address/channel; discover its current interface with ObexFTP before use.

USB Gammu configuration:

```ini
[gammu]
device = COM7
connection = at
```

On Linux use the actual `/dev/serial/by-id/...` or `/dev/ttyACM...`, appropriate dialout
permissions and a real Nokia connectivity driver. Never blindly change drivers or
claim AT gives PIM access. Identify first with `gammu --config /path/gammurc identify`.

Optional S60 Remote:

```ini
[gammu]
device = AA:BB:CC:DD:EE:FF
connection = blues60
```

The user separately chooses to install the Gammu-compatible S60 applet and its
compatible runtime. Inspect source/download provenance and signatures; SymPort does
not download or install historical unsigned binaries automatically and does not
request jailbreak. Start the applet on the phone, allow its Bluetooth connection,
then run identification and read-only store probes. `bluerfs60`/proxys60 support
must be checked against the installed Gammu build/documentation. Do not replace a
working driver merely because a profile is labelled `gammu-s60`.

For OBEX on Linux install distribution `obexftp`, BlueZ tools and permissions.
Read-only `bluetoothctl devices Paired` and `sdptool browse <paired-address>` show
paired candidates/services. Select **File Transfer (0x1106)** for FTP or **Object
Push (0x1105)** for inbox transfer; use the SDP-reported RFCOMM channel. This wrapper
never selects Siemens/Sharp/SE modes and only uses FBS or explicit OPP UUID-none.
Windows Gammu uses its available MS Bluetooth stack support; native ObexFTP requires
a separately installed compatible Windows build. Missing binaries/services stay
unavailable; the agent does not silently substitute another transport.

## Safety and verification details

- Gammu workers disable debug logs and isolate timeouts. The frozen windowless EXE
  exchanges private IPC files instead of relying on absent stdin/stdout. Private
  snapshots/backups are owner-local; ordinary operation journal records action/status.
- PIM writes keep the existing preview, before-state backup, fingerprint, confirmation,
  single-connection batch and repeat-read checks. SMS additionally requires an
  operator-verified phone/connection profile and exact recipient/text confirmation.
- FTP writes create a fresh random public folder, verify it is empty and perform
  **one PUT with the complete remote destination**. A chained chdir/put can continue
  after failed chdir in upstream CLI; this implementation avoids that failure mode.
- Upstream ObexFTP may return **255 on success** (`exit(-ret)`); distro variants may
  normalize to zero. Exit code alone never proves FTP success: XML, byte count and
  SHA-256 read-back are checked. OPP reports only receiver acknowledgement.
- No transfer resumes automatically after uncertainty. Partial staged folders can
  remain after failure; inspect them on the phone. Folder names/results identify
  the destination. No cleanup is attempted on an uncertain or protected remote path.
- Gallery/streaming are not advertised by FTP/OPP. File Manager provides download
  for FTP instead. Backend Catalog/Lab use the same transport contract and cannot
  pretend a file is installed.

## Manual Nokia E52 test protocol

1. Record OS/build/driver/Gammu versions, Nokia model/RM/firmware and selected USB
   mode privately. Do not put full IMEI, phonebook or SMS in public reports.
2. Start with no writes. Check USB enumeration/reconnect; unknown/S40/non-Nokia
   candidates must not become supported S60 devices. Pair Bluetooth in the OS and
   record the actual FTP/OPP/S60 services/channels.
3. Read identity and each personal store separately. Compare counts and one test
   record on the phone. An empty supported store must be distinguished from an
   unsupported/failed query. Export vCard, SMS JSON/CSV and calendar/task iCalendar.
4. Back up accessible original data. For a disposable file: list, download, compare
   SHA-256, stage upload, verify destination and repeat-read. FTP must not offer
   delete/gallery/PIM; OPP must not claim connected/listing/read-back/installation.
5. Send a trusted small SIS/JAR. Check checksum and phone inbox/folder; install only
   with consent on the phone. Keep package transfer, installation and launch results
   separate. Check JAR-only flow; JAD via OBEX must explain the restriction.
6. On a disposable contact/calendar record, inspect dry-run and backup, approve locally,
   apply once and reread. Test a stale snapshot/conflict and disconnected phone; it
   must stop rather than overwrite or retry. Test SMS only with an explicit verified
   profile, own test recipient and awareness of network charges.
7. Disconnect/reconnect cable/Bluetooth; switch USB modes. Replacing a Windows drive
   letter with another disk must block writes until the actual Nokia is re-enrolled.
8. Revoke web access, expire lease, restart bridge and try an untrusted Origin/Host/key.
   Confirm no operation repeats after a lost response and no private content enters logs.
9. Save only sanitized capability/error results plus test package hashes. Mark every
   unperformed hardware row **не проверено на устройстве**; never infer success from mocks.

Further work depends on real E52 traces: tested modern Nokia driver combinations,
per-service Bluetooth discovery/auto-selection, shared-directory OBEX batch staging,
verified SyncML conflict handling and an optional native Symbian agent. These are
not exposed as working capabilities today.

## N95 / N95 8GB profiles

Both use documented S60 3rd FP1 / Symbian 9.2 profiles. The shared registry resolves regional
suffix/RM evidence; a bare `N95` remains variant-unknown. It does not change any transport
protocol or capability decision. Original microSD and 8GB mass memory need actual discovery
and explicit volume enrollment; model storage capacity never authorizes a host path. Windows
Bridge ships the same registry and exercises it in the frozen executable self-test.
**USB/Bluetooth/S60 applet, PIM writes and SIS/theme installation are not tested on N95 hardware.**
See [model/RM sources and manual test plan](NOKIA_N95.md).

## Nokia N97 mini / S60 5th

Mini uses the existing Gammu USB/Bluetooth/S60 and OBEX adapters; it has no new protocol.
Specific model-name normalization precedes `N97`. Host names remain candidates, and no RM-only
mapping is shipped without a verified source. Windows USB/CIM discovery includes fixed as well as
removable Nokia USB volumes, with system drives excluded. Native PIM stores still require separate
read-only status probes. Config/USB-mode/BT-destination/mounted-root changes invalidate connection
fingerprints; native PIM previews and observed write proofs cannot follow a changed connection.
Both the internal mass memory and microSD must be observed/enrolled separately; neither exposes
phone identity, `C:` or PIM automatically. **Mini hardware: not-tested.**
[Connection matrix, limitations and physical test checklist](NOKIA_N97_MINI.md).

## Nokia N8 / E7: Symbian^3 family

Shared registry/Bridge 0.3.2 recognizes N8-00 / RM-596 and E7-00 / RM-626 without confusing E7/E72.
The `symbian3` enrollment edition reuses existing Gammu/OBEX adapters; it grants no capabilities.
OS release is unknown until separately sourced. Model identity never implies Anna/Belle.

The baseline path is an actual Nokia USB Mass Storage volume: N8 internal memory and optional
microSD are separately observed; E7 internal memory is not described as a card. Suite mode needs
Nokia drivers and an available endpoint; a busy Suite port or unsupported native store remains an
error/reason. AT identity is not PIM access. Bluetooth OPP/FTP requires actual service evidence.
No independently verified N8/E7 protocol/driver trace was available; no new protocol was invented.

The normal confirmations, read-back, no-overwrite, scoped fingerprints and protected paths apply.
Writes to system/private/resource folders are blocked on enrolled volumes as well as OBEX staging.
**N8/E7 physical devices: not-tested.** See [connection steps and test matrix](NOKIA_N8_E7.md).

## Nokia 7610: S60 2nd Edition

The original Nokia 7610 (Symbian OS 7.0s, not the Series 40 "7610 Supernova") reuses the existing adapters: the
enrollment edition `2nd` is accepted next to `3rd`, `5th` and `symbian3`, and **grants no capability**. Model identity
comes from the registry (`documented-model-profile`, never measured); everything else comes from the connection.

* Mounted RS-MMC / USB volume: files only. The Pop-Port cable does not guarantee a volume; without one, file functions
  stay unavailable.
* Bluetooth OBEX FTP: listing; download and writing stay unverified until confirmed. OBEX OPP: push only (no listing,
  download or store reads).
* Gammu: an identity read is not PIM access. Contacts, SMS and calendar are enabled one store at a time after a
  successful read; Gnapplet (a Gammu applet for Series 60) is a possible dependency of PIM access and is reported as a
  capability status, never assumed. Gnapplet on the 7610 itself is not verified here.
* Host candidate ≠ phone identity ≠ supported transport.

Physical 7610: **not-tested**. Details, limits and the hardware checklist: [NOKIA_7610.md](NOKIA_7610.md).
