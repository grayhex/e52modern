# Experimental Jailbreak Manager

This is an integrated preparation and manual-operation recorder for an owned Symbian
phone. It implements ZIP inspection, exclusions, dry-run planning, accessible-data backup,
confirmed isolated file staging, manual observations, a non-executable test SIS and
hash-checked rollback of SymPort-created files. It does not claim an automated jailbreak.

## Research and supplied archives

Source: [Legacy Portable Computing Wiki, Jailbreaking S60 devices, revision 71013](https://lpcwiki.miraheze.org/wiki/Jailbreaking_S60_devices?oldid=71013),
retrieved 2026-11-03. The guide was last edited 2026-06-13; its content is CC BY-SA 4.0.
Instructions in SymPort are adapted summaries with attribution, not proof of E52 firmware
compatibility. The guide covers Trend Micro, Symantec/Norton and CProfDriver/HelloCarbide;
it describes ROMPatcher+ and notes method/device exceptions, date and SIM requirements.
UMU Nokia is present in the uploaded archives but is not the Norton/Trend Micro payload
linked by this guide. It remains an archive-only, unverified manual candidate.

Both user archives were inspected **without executing their files**:

- `Nokia symbian_1.zip`: SHA-256 `fe6421c94fdb425c7f62731e348ed95727671abbfa247bd68bb5dd6ef4c2de33`.
- `Nokia symbian_2.zip`: SHA-256 `5e5035a7c7b1cf01e317e22bed04a9453b86b40b67be5ac5b2dffbb36bde9cae`.

[Inventory and hashes](research/supplied-s60-archives.json) ·
[Read-only SIS findings](research/archive-sis-analysis.json).
The archives contain variant InstallServer binaries and patches for other models;
Norton, ROMPatcher Plus 3.1, UMU Nokia/SE; and a shared certificate/private key.
The private key was not retained in imported data, used to sign or copied into Git/image.
Only metadata and hashes of non-key files are committed. Executables are runtime
user uploads under private persistent storage, never bundled into Docker.

The checked packages have different mathematical signature outcomes: Norton and
ROMPatcher have valid SIS signatures with unknown phone trust. UMU Nokia's signature
fails verification; UMU SE is for another target. Such choices are blocked for staging.
This does not constitute a malware scan or validation of E52 hardware compatibility.
Norton/UMU have optional CRC fields omitted and conditional controllers; these limits
are retained in the analysis. A generic `FP2 9.3` name is never an exact-firmware match.

## Controlled workflow

1. Import your ZIP. Paths, symlinks, duplicate entries, file count/expansion sizes are
   checked. Private keys are excluded before reading/caching their contents. Review
   SIS signature outcomes and file fingerprints. Wrong-model patches are not selectable.
2. Select the phone-connected volume/Bridge and record model, RM, exact firmware and
   Symbian. Gammu exposes available identity; a memory card does not identify a phone.
   Manual values are labelled as observations. Read firmware on the handset (`*#0000#`).
3. Select a method and files, record original clock, installer settings and active patches.
   **Create dry-run plan** persists facts, limits and manual steps but changes no phone data.
4. Confirm backup of an accessible folder. This uses the existing file transport: regular
   files only, up to 8 MiB/500 files, no recursive directories, system/ROM/settings/contacts
   or application-registry guarantee. The original snapshot is immutable for the workflow;
   export it as ZIP. Use full [memory-card Backup](PHONE_BACKUP.md) separately if required.
5. Confirm risk and transfer. Files go into a new `SymPort-Unlock-<workflow-id>` folder,
   with generated names and original-name/hash mapping in the report. Existing files are
   not overwritten. Files are **transferred-not-installed**. Interrupted/failed transfers
   are recorded as partial; inspect them before retrying in a new plan.
6. On the handset, follow the source guide only after establishing suitability. Record
   each system-affecting action with its own confirmation: package installation,
   quarantine restore, patch application/disable, uninstall or restoration of settings.
   These are user observations, not transport-confirmed operations. SymPort does not
   fabricate installation or a green patch status. Avoid Auto patches during an unverified trial.
7. Download the safe installation probe: unsigned SIS with a text file under
   `!:\data\SymPort\installation-probe.txt`; no executable, driver or capability. Install
   manually and record the result. Success is not proof of AllFiles access or a jailbreak.

## Automation gates

No combination of E52 exact firmware, privileged system-write adapter and tested recovery
procedure has been validated in this project. Therefore `install`, `patch`, `system-write`
and `restore-system` are blocked **server-side**, even if the client supplies confirmation.
A filename, certificate result or user-entered version cannot lift this gate. The UI
provides the manual scenario and explains the missing evidence. There are no hidden
Catalog side effects, ROM flashing commands or generic privileged-file endpoints.

A future native adapter must add an exact artifact/firmware policy and tested restore
procedure before automation is implemented. Existing USB volumes and PC Bridge remain
file/contacts transports and are not represented as installation tools.

## Rollback

**Preview rollback** lists each staged file and all manual restoration tasks. After explicit
confirmation, SymPort re-downloads each owned file and deletes it only if its SHA-256 is
unchanged. Changed/missing/inaccessible files become conflicts; unrelated or pre-existing
files are never deleted. The staging directory may remain; no recursive delete is used.

This is **partial rollback**. SymPort cannot undo manual quarantine restores, remove an
installed application, toggle a running patch, restore an unknown original system binary,
or reset phone date/settings over these transports. Disable only newly enabled patches
and Auto entries on the phone; uninstall newly added packages; restore recorded settings
manually. A manually replaced system binary needs its original exact-version backup and
a separately verified recovery path. No full-restore claim is made.

Reports and logs (`symport.jailbreak/1`) persist in `build/symport/jailbreak`, scoped 0700.
Reports export explicitly; no archive key or contact/SMS payload is put in operation logs.
Tests cover path/ZIP exclusions, key non-retention, wrong targets, server gates, immutable
backup, confirmed staging, manual observations and rollback conflict protection. Browser
E2E uses synthetic benign fixtures and a temporary volume, not a physical E52 jailbreak.
