# SymPort Device Manager

Open **Телефон и файлы** in the existing Workbench (`python -m symport.web`). The CLI,
CLEAR build UI, manual handset test report and Compose entry point remain available.

The main product is a Symbian phone workspace; development tools and CLEAR themes are secondary sections. Phone domain code is in `symport/phone/`, local theme publication in `symport/library.py`.

## Local theme library

In **Темы и библиотека**, import a SIS/SISX (up to 8 MiB) or select a generated CLEAR package. Import verifies SIS structure/checksums and creates a draft. Explicit confirmation publishes it locally; only published packages appear as downloadable library entries. Publishing does not certify theme content, install it or expose a public marketplace. Transfer from the library uses the currently selected phone and folder. Packages retain a SHA-256 integrity check. Library storage is under `build/symport/library`, retained by the existing Compose build volume. Imported files are private to the OS account; secure that account and its storage.

## Implemented scope

* Operator-enrolled mounted volume: directory listing, available/total disk space,
  download/upload (8 MiB), directory creation, confirmed file/empty directory deletion.
* SIS/SISX transfer validates checksums and structure first. Completion means **file
  transferred**, not application installed. Finish installation on the handset and
  record observations in the existing **Телефон и тесты** checklist.
* File backup: ZIP of regular files in the selected directory, excluding subdirectories;
  8 MiB / 500 files maximum. Restore previews exact filenames, sizes and conflicts,
  requires confirmation for that archive and never overwrites existing files.
* Persistent operation journal, excluding payloads, phone paths, IMEI and exception text.
* Optional Gammu adapter: identification plus phonebook export and confirmed append with read-back verification; reports observed model/firmware/RM when returned;
  missing data remains unknown. Configuration chooses USB/Bluetooth; auto-pairing is outside this adapter. See [contact import](CONTACTS.md).
* PC Bridge uses the same Device Manager API through an authenticated loopback SSH
  tunnel. Transport selection is server configuration, never an HTTP parameter.

No physical Nokia E52 has been tested. Filesystem and HTTP tests exercise real temporary
files and mock transports; they do not establish USB, Bluetooth or firmware compatibility.
Installed application inventory and SMS remain unavailable with a reason. Contacts support file imports, vCard staging and optional Gammu phonebook access; handset compatibility is unverified.
File backup is not a complete handset backup. Battery and internal phone memory are
unknown on mounted-volume connections; disk space is only the enrolled volume's space.

## Linux / E52 USB mass storage

Back up important data independently first. Select mass storage mode on the E52, mount
its memory card using the OS, and explicitly enroll that **volume**, for example:

```bash
export SYMPORT_DEVICE_ROOTS='{"e52-card":"/media/user/E52"}'
python -m symport.web --host 127.0.0.1 --port 8765
```

A directory existing is not proof that a phone is connected. Enrollment is an operator
assertion: verify the mount and unplug behaviour with your OS. Model/firmware remain
unknown until an identifying transport returns them. Never enroll `/`, a home folder,
or an untrusted directory. Do not let other processes change symlinks or replace the
volume while an operation runs. Symlink paths and traversal are rejected, but the adapter
does not provide an OS-wide lock against another process changing filesystem topology.
Uploads never replace existing files; deletion is not recursive. Use the path field to
navigate back to the root (empty string). Only the user-selected drive is visible.

For Gammu, install the official Gammu package and configure `gammu --config <file> identify`
using Gammu's device-specific documentation. Then set `SYMPORT_GAMMU_CONFIG` to that
operator-owned file. E52 support varies by connection and firmware. A working `identify`
does not establish filesystem, contact or SMS support. Gammu/OBEX/SyncML are separate
capabilities, not interchangeable protocols. OBEX Object Push can transfer objects but
is not a general file manager; OBEX FTP requires the handset to expose that service.
No untested OBEX or SyncML command is labelled working here. Existing symbian-platform
list/info/stage operations remain in **Телефон и тесты**.

## Windows PC Bridge and remote Linux Docker

The remote Linux server cannot discover USB/Bluetooth devices attached to Windows.
Run Workbench on that PC with Python >=3.11, `pip install -e '.[dev]'`, and a checkout of this branch:

```powershell
$env:SYMPORT_DEVICE_ROOTS='{"e52-card":"E:/"}'
# Generate a private key once; do not put it in Git, logs or URLs.
$env:SYMPORT_BRIDGE_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
python -m symport.web --host 127.0.0.1 --port 8765
```

Keep that process running. In another terminal establish an authenticated SSH reverse
forward from the PC to the Linux host:

```text
ssh -N -R 127.0.0.1:18765:127.0.0.1:8765 user@linux-server
```

On the Linux Workbench process, set `SYMPORT_BRIDGE_URL=http://127.0.0.1:18765`
and securely supply the same `SYMPORT_BRIDGE_KEY` (at least 32 characters).
Only the bridge endpoint accepts this key; the normal browser uses the existing
session token. Run the bridge on port 8765; the forwarded request pins that Host header.
The bridge key grants file-management access: protect both endpoints and rotate it by
restarting both processes. Requests use the loopback tunnel, without Internet proxying.

A container's `127.0.0.1` is not the host's loopback. For remote Docker, establish the
SSH tunnel in the Workbench network namespace (or run a dedicated SSH tunnel sidecar
sharing that namespace). Do not point it at the public host interface to work around
this. The provided Compose does not automatically create SSH tunnels or enroll devices.
For a directly attached mounted volume, add an explicit narrow bind mount and set
`SYMPORT_DEVICE_ROOTS` to the **container** path. No privileged container is required.
Gammu, obexftp and BlueZ executables are included in Docker; D-Bus/hardware access is
not implicitly granted. Never expose ports to the Internet; use loopback and SSH.

## Media and software

The Music & Video page transfers supported audio extensions and MP4/3GP up to 64 MiB per file. It does not transcode or set the active ringtone. The Games & Applications page validates and stages SIS/SISX or Java JAR/JAD up to 8 MiB, without claiming installation. Select an existing destination directory. Existing files are never replaced. Contact file parsing is limited to 4 MiB and 2000 entries.

## Validation

```bash
pytest -ra
ruff check .
node --check symport/web_assets/manager.js
```

CI runs device-manager tests in the existing Python 3.11–3.13 job, without a phone.
Hardware validation must cover mount/unplug/reconnect, destination paths, interrupted
transfers, available services, permissions and actual handset installation. Preserve
unknown and unsupported outcomes in the existing device test report.

## Командная строка и новые действия

Полная файловая копия карты, восстановление без перезаписи, инвентарь SIS, передача SIS и чтение календаря через Gammu — в CLI
(`symport phone …`, см. [PHONE_BACKUP.md](PHONE_BACKUP.md)). Через API Device Manager добавлены `apps-inventory` (тома) и
`calendar-read` (устройство `gammu`). Планы — в [ROADMAP.md](ROADMAP.md).
