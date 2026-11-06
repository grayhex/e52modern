# Phone workspace: media, dashboard and personal data

SymPort uses its existing Device Manager transport contract (`devices()` / `execute()`),
PC Bridge authentication and operation journal. Media and personal-data commands use the
same path on Windows and Linux. The remote server cannot discover a phone attached to your PC.

## Choose the connection

| Connection | What it exposes | What it does not imply |
|---|---|---|
| Enrolled filesystem / USB Mass Storage | Files, recursive media gallery, thumbnails, ranged preview, ZIP downloads, transfers | Phone identity, internal `C:/`, contacts, SMS and calendar access |
| Gammu serial/USB AT | Whatever the selected driver actually returns; each personal store is probed separately | Complete E52 phonebook/calendar or SMS support just because `identify` succeeds |
| Gammu `blues60` | Gammu's extended S60 Remote applet over Bluetooth; store status/read calls determine availability | Compatibility with the original Series60 Remote applet or a USB S60 Remote connection |
| PC Bridge | Forwards these same capabilities over an authenticated SSH tunnel | Additional capabilities that the PC's drivers do not provide |
| SyncML / native E52 Agent | Extension point in the existing transport contract | An implemented or automatically enabled service |

The dashboard shows only returned values. Missing RM/firmware, battery, signal, USB mode
and capacity remain unknown in the API; the dashboard renders them as neutral “No data” badges with icons and captions. Filesystem free space is explicitly labelled as the enrolled
filesystem: a host directory is not evidence of internal phone-memory capacity.
The lifetime counter is displayed only if a transport reports it; Gammu currently has no mapped life-timer API. It is never calculated from connection uptime. Nokia call-time counters and powered-on time are different measurements.

IMEI is masked. Revealing it requires confirmation; it disappears after 30 seconds or
window blur. Discovery and ordinary operation logs never contain the full identifier.

## Windows PC Bridge

Use 64-bit Python 3.11–3.13 and install the existing project with its optional adapters:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[phone,media]"
$env:SYMPORT_GAMMU_CONFIG = "C:\SymPort-private\gammurc"
$env:SYMPORT_DEVICE_ROOTS = '{"memory-card":"E:/"}'
$env:SYMPORT_BRIDGE_KEY = .\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
.\.venv\Scripts\python -m symport.web --host 127.0.0.1 --port 8765
```

`python-gammu` publishes official Windows amd64 wheels, including CPython 3.11, 3.12
and 3.13. Use the Python interpreter that installed the wheel to run the bridge.
The Gammu executable is optional for the native adapter; it remains useful for configuration
and the legacy vCard/iCalendar read fallback. Install the appropriate Nokia cable/COM driver
separately. SymPort does not distribute it.

For USB serial/AT, select the phone's **PC Suite** mode and the COM port provided by the
installed driver. Configure Gammu according to its documentation; do not use the memory-card
letter as a serial device. A successful AT connection does not guarantee access to all
Symbian application databases. Mass Storage is used separately for file/media access.

For Bluetooth, pair on the PC first and choose a Gammu connection supported by the
installed build. `blues60` specifically requires Gammu's **extended** S60 Remote applet,
Python for S60 and a running applet on the phone. Gammu documents this protocol as
**Bluetooth only**. Do not substitute the original applet or select this driver for USB.
These historical applets may have certificate/runtime requirements; SymPort neither installs
them nor changes installer/security settings automatically.

Use [the existing SSH tunnel instructions](DEVICE_MANAGER.md#windows-pc-bridge-and-remote-linux-docker)
or [the Compose SSH sidecar](DOCKER_DEPLOYMENT.md). Keep both APIs on loopback.
The bridge key must be the same at both ends and at least 32 characters. Updating the bridge
is necessary before using the new commands; an older bridge returns an unsupported-operation
error, not an empty or simulated result.

## Local Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[phone,media]'
export SYMPORT_GAMMU_CONFIG=/absolute/private/gammurc
export SYMPORT_DEVICE_ROOTS='{"memory-card":"/media/your-user/PHONE"}'
.venv/bin/python -m symport.web --host 127.0.0.1 --port 8765
```

The current official Linux wheels bundle the native dependency. Source builds require
Gammu development headers, a C compiler and pkg-config. Give the local user access only
to the selected serial device/Bluetooth connection. Run the same PC Bridge outside Docker
when the container is remote or when host Bluetooth access is needed; no privileged
container or broad host `/dev`/D-Bus mount is required. `compose.phone.yaml` remains the
optional way to expose a specific mounted card to a local Docker Workbench.

## Media Gallery

Select a connected volume and folder in **Music and video**, then **Read media**.
The gallery searches photos (JPEG/PNG/GIF/WebP/BMP), video (MP4/3GP/MOV/AVI/M4V)
and audio (MP3/AAC/M4A/WAV/MIDI/AMR/WMA). Search, kind filters and sorting apply to
all returned items; the grid is paginated. Choose visible items or individual checkboxes,
then download a ZIP. Upload and original-file download remain available independently
of browser codec support.

JPEG thumbnails are generated on the PC from bounded photo files; original EXIF/GPS is
not copied into thumbnails. Original images, video and audio use authenticated same-origin
HTTP Range. The server reads at most 256 KiB per transport request, including through
PC Bridge. Audio/video requests use `preload=metadata`; browser codecs decide whether
playback works. There is no claim of server transcoding or native browser support for
3GP/AMR/MIDI. Photo previews may require the full image; the gallery itself uses thumbnails.
Video thumbnails use an actual frame in the browser when its codec supports decoding; otherwise a type icon is shown. Audio uses a type icon.

Limits: 5,000 media entries, 25,000 examined filesystem entries, depth 12. A truncated or
inaccessible scan is reported explicitly. Thumbnails: original ≤16 MiB / 24 megapixels.
ZIP: ≤200 unique files / 1 GiB; streamed into a private server-side temporary archive,
then downloaded without buffering all originals in browser memory. A changed file invalidates
its revision and stops a download; refresh the gallery. ZIP files are private, removed after
successful download, and expired archives are pruned after an hour on the next export.
Symlinks, traversal and access outside enrolled roots are rejected.

## Read and export personal data

1. Configure Gammu on the PC connected to the phone and discover devices.
2. Open Contacts, Messages or Calendar. Each store is independent: a driver may support
   contacts and reject SMS or calendar. The dashboard's connection details show returned
   Gammu status/error codes. No SMS/contact/calendar capability is inferred from Mass Storage.
3. Read the desired store. Successful explicit zero counts produce an empty store; an
   ambiguous empty response, incomplete enumeration or stalled iterator produces an error.
4. Search/filter in the browser, export or create a private backup.

Contacts (Gammu phone memory `ME`; SIM contacts are not implicitly combined): search/edit a normalized view, inspect exact duplicate groups, import Google CSV
or Apple/Google vCard, export selected basic fields or the original phone vCard. Basic cloud
import covers names/numbers/email; the original Gammu vCard and private JSON backup preserve
additional returned fields. A vCard staged on a card must be opened and saved on the phone.

SMS: search text/number, incoming/outgoing filters, conversation selection and optional names
from contacts read from the same phone. Multipart segments retain their part numbers; SymPort
does not guess concatenation or message timestamps. Export JSON/CSV or back up the read store.
CSV guards against spreadsheet formulas. A backup contains only stores that were actually read.

Calendar/tasks: read separately, search, export JSON or iCalendar, preview imports and edit/create
basic entries. Native export combines entries into one VCALENDAR. Handset wall times remain
floating times rather than being relabelled UTC. Existing UIDs are retained when returned;
otherwise a stable store/location identifier is used. Keep exports tied to the source phone.
The legacy CLI fallback remains read-only and returns its original iCalendar export.

Snapshots/plans expire after 15 minutes and are kept in PC Bridge memory (maximum 20 each).
They are not ordinary logs. Explicit backups persist under `build/symport/personal-backups`
with owner-only files; the Docker build volume preserves them during updates. Protect and
back up this volume, or the corresponding directory on a Windows/Linux bridge. Normal operation
logs record only action, time and status, never payloads, record identifiers or exception text.

## Safe synchronization

Phone writes require the native adapter, a read snapshot and a unique phone identity.
The CLI fallback cannot write through the web API. If the driver cannot read a unique identity,
use file export/import on the phone instead.

- Select edited/imported contacts or calendar entries, then preview. The UI shows before/after
  fields, additions, updates, skipped duplicates, conflicts and zero deletions.
- Existing calendar UIDs with different data are conflicts, never implicit replacements. Repeated
  contact imports skip exact duplicates. No phone record is deleted.
- Confirm the displayed plan. Re-reading the original store detects changed records or a different
  phone before any write. A private JSON backup of the original native records is saved first.
- A batch keeps one Gammu connection open; each native write is followed by reading that location and comparing supported fields. Unknown
  entry fields and existing phone-number labels are retained during edits.
- A plan is single-use. A timeout, driver error or read-back mismatch stops the batch and reports
  a partial/unverified result. Read again before another plan; do not automatically retry.

Advanced recurrence, invitations, unsupported iCalendar fields and timezone conversion are
blocked for writes. Phone timezones cannot be inferred safely: convert imported dates to the
phone's local wall time explicitly. Edit complex entries on the handset. Backups provide the
original returned records for inspection/manual recovery; SymPort does not promise automatic
restoration of fields that the driver cannot write.

## SMS sending

Reading SMS never enables sending automatically. The PC operator must first validate sending
for the **exact phone fingerprint and Gammu connection** with a consenting recipient, then provide
an owner-controlled JSON profile through `SYMPORT_VERIFIED_SMS_PROFILE`:

```json
{"fingerprint":"<returned device fingerprint>","connection":"<actual Gammu Connection>","sms_send_verified":true}
```

Keep that file outside Git. Do not copy a profile to another phone/driver. Without a matching
profile, the UI disables sending and the backend refuses it. Each send still requires the recipient,
text, an explicit confirmation, a fresh read snapshot and a private backup. One Unicode SMS
(up to 70 UTF-16 code units) is accepted; there is no silent multipart billing. A submission is
not a delivery confirmation. The adapter rereads exposed stores and reports whether a sent copy
is visible; delivery stays unknown without an actual delivery report. A send attempt consumes
the snapshot, even on timeout; read SMS again before another attempt.

## Research and actual validation

Sources reviewed for this implementation:

- [Gammu StateMachine API](https://docs.gammu.org/python/gammu.html) and
  [native object formats](https://docs.gammu.org/python/objects.html).
- [Gammu connection configuration](https://docs.gammu.org/config/index.html).
- [Gammu Series60 Remote](https://docs.gammu.org/protocol/s60.html): extended applet,
  Python for S60 dependency, Bluetooth-only transport. Historical signing/download advice in
  that document is not a current signing service or a reason to turn off protection automatically.
- [GNapplet](https://docs.gammu.org/protocol/gnapplet.html): a separate historical protocol;
  its existence is not evidence of compatibility with E52/FP2.
- SyncML/OBEX synchronization requires a separate maintained client, session/pairing support,
  data mapping and conflict handling. Gammu's `blues60` is not SyncML. No SyncML capability is
  advertised until an adapter provides real read/write/read-back evidence.

Implemented: real local-file media I/O, protected streaming, ZIPs, Gammu API integration, safe
sync orchestration, Windows-compatible Bridge commands and native-library Docker dependencies.
Validated without a phone: filesystem/HTTP/browser tests, stateful mock Gammu read/write/conflicts,
real python-gammu import/method/format checks and Docker startup. Physical E52 firmware/driver
coverage still needs device testing; an API success in a mock is not hardware evidence. Public
UI shows returned service failures and useful alternatives rather than development-stage banners.

A future native E52 Agent should implement the same capability-based `Transport`, retain per-store
snapshots and native record identities, use authenticated PC Bridge enrollment, and provide explicit
read/write/verification results. It must not extend Mass Storage into protected phone access or
advertise unimplemented features. No placeholder Agent service is deployed.

## Firmware reference and Updates

The read-only `symport/phone/firmware_reference.json` contains E52/E72 model-level
reference versions and their public sources (currently 091.004). Numeric comparison
accepts padded versions such as 91.004/091.004 and distinguishes older, equal, newer
and unknown values. An unidentified model or ambiguous version is never marked outdated.
The reference is reviewed with repository updates; it is not a live Nokia update service.

Older versions are highlighted on the dashboard and link to **Updates** in the left menu.
Updates is intentionally a placeholder: it shows the current/reference version and sources,
and its install button is disabled. A regional/product-code/RM-specific firmware match,
verified recovery procedure and actual flasher are prerequisites for future installation.
No firmware images, executable downloaders or ROM modifications are part of this feature.

## Prepare for Nokia (#41)

*Phone → Media → Prepare for Nokia* converts a video, a music file or a picture for a chosen model
(E52, E72, N95, N95 8GB, N97 mini) and either exports it or copies it to the phone. It reuses the
sandboxed FFmpeg worker of Ringtone Studio (resource limits, no network protocols) and Pillow; it
does not duplicate the file manager or Ringtone Studio.

* **Inputs and limits:** ≤ 48 MiB, ≤ 10 minutes, ≤ 40 megapixels; metadata (tags, GPS) is removed;
  bad, truncated or unsupported files are refused; output ≤ 48 MiB; conversion time-out 240 s; a
  one-worker queue (two waiting) with a visible position; temporary files live one hour and can be
  discarded at once.
* **Presets** (video MP4/H.264 baseline 320×240 and 3GP/MPEG-4 176×144, audio MP3 128 kbps / 64 kbps
  mono and AAC, pictures cropped for a wallpaper or fitted inside the model's screen) are
  **theoretical**: every one reports `hardware: not-tested` and its basis. Aspect ratio is kept
  (letter-boxing). Nothing sets a wallpaper on the phone: it only copies the file.
* **Preview and estimate:** a thumbnail (picture / first video frame) and a size estimate before
  conversion; the real size and SHA-256 afterwards.
* **Three separate outcomes:** `exported` (download file + JSON report), `transferred` (copied
  through the Recovery Safety Net into `SymPort-Media/`: dry run, snapshot, read-back, no overwriting
  of an existing file, blocked when there is not enough free space or the phone is another model,
  rollback of the copied file only) and `played-on-device` (what you report after trying it).
