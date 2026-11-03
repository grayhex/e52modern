# SymPort Bridge for Windows

A portable Python-based Windows x64 tray agent. Device operations use the same
DeviceManager, Gammu, file, contact and backup implementations as Linux SymPort.
No Electron, firmware flashing, ROM, Nokia drivers or applet binaries are included.

## Install and connect

1. Download **SymPortBridge-Windows-x64** from a successful [Windows Bridge build](https://github.com/grayhex/e52modern/actions/workflows/windows-bridge.yml).
2. Extract the entire bundle to a permanent user folder. Run `SymPortBridge.exe`.
   Builds are currently unsigned. Check `SHA256SUMS.txt`; do not disable Windows protection globally.
3. Connect the Nokia USB cable, select **PC Suite** and install a trusted Nokia
   connectivity driver separately if no COM port appears. Close Nokia Suite when
   it holds that same COM port. Mass Storage only exposes an accessible card.
4. Open **Connection** in SymPort → **Request access**. Allow local-network access
   in the browser and approve the exact SymPort origin in the Windows dialog.
5. **Find phone** → select the connection. All phone screens continue to use
   their existing UI. An outbound HTTPS relay also serves Catalog, Inspector,
   Emulator Lab transfer and authenticated media downloads through the backend.

Use a current Chromium browser for local-network permission prompts. If browser
policy blocks loopback access, use the existing authenticated SSH PC Bridge route
in [DEVICE_MANAGER.md](DEVICE_MANAGER.md). The Workbench must be reachable by the
Windows PC. HTTP is allowed only for localhost; remote Workbench requires HTTPS.
Keep the remote deployment behind authentication; the default Docker port stays
bound to host loopback. Set `SYMPORT_PUBLIC_ORIGIN=https://your-symport.example`
only when using a trusted authenticated HTTPS reverse proxy.

Access lasts two hours, is kept in memory and is revoked by **Disconnect Bridge**,
**Revoke web access** in the tray, or exit. Restarting the agent requires pairing
again. The relay never retries a claimed phone operation automatically. If a
connection fails during a write, read the phone before repeating the operation.

## Tray and configuration

Tray **Settings**: automatic Nokia USB discovery (default on), optional current-user
Windows sign-in autostart (default off), Gammu configuration and connection-profile
JSON. **Diagnostics** shows state/candidate counts. Operation logs contain action,
time and status only. Settings/private backups live in `%LOCALAPPDATA%\SymPortBridge`.
Full-volume backup jobs in the development tools still operate on volumes enrolled
on the server. For Bridge use the existing selected-folder backup and PIM backups;
Mass Storage never provides SMS or phonebook access.

The long-term SSH bridge key is protected with current-user Windows DPAPI and is
copied only by the explicit **Copy Bridge key** action.

Automatic serial discovery filters Nokia VID `0421`/Nokia host descriptions, then
requires a real Gammu manufacturer/model response matching a documented S60 model.
S40 and unknown models are not promoted to supported phones. S60 edition is a
model reference, not an OS version measured over AT. Memory-card discovery requires
Windows CIM associations back to a Nokia USB disk; writes recheck physical identity.
Unsupported counters remain absent. Disconnects are polled; no pairing/driver changes
or SMS are performed automatically.

Bluetooth must be paired in Windows first. Use an operator-enrolled profile for
Gammu Bluetooth/S60 Remote or ObexFTP; see [TRANSPORTS.md](TRANSPORTS.md). ObexFTP
is an external optional dependency and is **not** bundled in the Windows build.
An absent executable produces a connection diagnostic, not a supported capability.
The Gammu wheel's supported transports depend on its actual build/driver and must
be tested on the host; no universal Windows USB/Bluetooth compatibility is promised.

## API and security

HTTP binds `127.0.0.1:24652` only. Existing `/api/bridge` RPC requires the long-term
key, strict Host and enrolled Origin. Browser pairing requires JSON, a valid HTTPS
Origin (or local HTTP), exact origin matching and native default-No operator approval;
it returns no long-term key. Pairing is bounded and rate limited. Outbound relay
credentials are separate, expire, use TLS and reject redirects. The Workbench's
normal authenticated session alone can create/revoke a lease. Phone payloads are
transient memory, never relay logs or URLs. Delete, restore, PIM writes and SMS need
frontend confirmation plus independent local approval. Headless mode denies them.

Optional `"websocket": true` in settings enables authenticated status events at
`ws://127.0.0.1:24654/api/bridge/events`; first frame is `{"token":"..."}`.
Host/Origin are checked; only status counts, never phone data, are emitted. HTTP RPC
remains authoritative. The old Linux PC Bridge and SSH route remain supported.

## Build and licensing

GitHub Actions builds Windows x64 with Python 3.12 / PyInstaller, executes the real
frozen `.exe` against DPAPI, HTTP authentication, Origin/DNS-rebinding checks and the
bundled Gammu worker, then includes sources, dependency notices and executable hash.
Version comes from `symport.bridge.VERSION`. The PE has version resources and can
be Authenticode signed by a future release workflow; no signing key is shipped.

SymPort source remains MIT. Gammu/python-gammu are GPL-2.0-or-later; the combined
Windows binary is distributed under GPL-3.0-or-later with corresponding sources.
pystray is LGPL-3.0, PyInstaller includes a bootloader distribution exception.
No upstream GPL protocol code is copied into SymPort source. Do not redistribute a
modified binary without satisfying the bundled dependency licenses/source requirements.

Hardware USB/Bluetooth tests: **не проверено на устройстве**. Build, mock and local
HTTP checks do not establish compatibility with a physical E52. Use the manual
procedure in TRANSPORTS.md before relying on personal-data writes.

OBEX staging creates a new folder per transfer. JAD transfer is blocked through
this adapter because it cannot preserve the accompanying JAR in that same folder;
choose a JAR-only package or a mounted card. The catalog uses the same restriction.

The agent uses port **24652**, distinct from the Workbench default 8765. For the
legacy SSH route with this packaged agent, set
`SYMPORT_BRIDGE_AGENT_PORT=24652` in the Compose environment: the SSH sidecar forwards
to Windows 24652 and the backend pins that same Host port; the existing Linux bridge keeps
its default 8765. No port change is needed for browser pairing/outbound access.

Tray exit waits for an already confirmed write to finish. Revocation stops new
operations and private result delivery; it cannot undo bytes already written.
