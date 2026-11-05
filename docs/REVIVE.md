# SymPort Revive

**Tools → SymPort Revive** is one recovery centre: *inspect the device → see a plan → prepare safely →
verify the result*. It reads the connection through the existing `DeviceManager` (Windows Bridge,
Gammu, OBEX, mounted drive). There is no second transport and no new write path. API:
`POST /api/revive` (`symport/revive/`).

## What is shown, and from where

Every fact carries its source:

| Source | Meaning |
|---|---|
| `observed` | read from the connection: model, RM, product code, firmware, transport, free space, capability matrix |
| `documented` | the model registry (`symport/phone/device_models.json`): S60 edition / Symbian. A model profile, **not** a measured firmware version |
| `manual` | typed by you (identity fields, installation rights, patches, results of on-phone steps) |
| `unknown` | not available over this connection |

Manual input is stored and displayed separately and never overrides a device report; a contradiction
is shown as a conflict. Installation rights and ROMPatcher patches cannot be read through a file
transport, so they are always your recorded observation (scope `none` / `memory-card` / `device`),
bound to the connection fingerprint, and "memory card only" is `needs-action` for system-level work.

## Statuses

`ready` · `needs-action` · `unknown` · `unsupported`. "Not tested" is `unknown`, never a failure.
Writes are never probed: a write capability that may be attempted after confirmation shows as ready
with that caveat in its reason.

Identity rules: an RM that disagrees with the model, an unrecognised RM, plain "N95" (variant
unknown) and manual-only identity are `needs-action`; a documented Nokia model without a Revive
profile and a model outside a wizard's targets are `unsupported`; no model is `unknown`. N97 mini
needs an explicit variant confirmation.

## Wizards

| Profile | Targets | Operations |
|---|---|---|
| Network and certificates | E52, E72, N95 family, N97 mini* | identity, clock check (manual), certificate review |
| Application kit | same | space check, copy a verified kit, install **on the phone** (manual) |
| Reborn preparation for N95 | N95, N95 8GB | identity, space, rights record |
| Diagnostics after installation | same | re-read, compare with baseline, manual observations |

\* only after variant confirmation.

Each operation lists risk, prerequisites (checks), source, version/SHA-256 (empty until a pinned
artifact exists), restore point, execution method (`read-only`, `bridge-transfer`,
`manual-on-phone`) and the actual result. SymPort never installs: copying a file is not
installation, and installation results are only what you recorded.

## Verify

*Save baseline* stores observable facts (no IMEI). *Re-read and compare* re-probes the connection
read-only and lists differences (identity, firmware, free space, capability changes). Differences
are observations, not proof of installation.

## Limits

No protection bypass, no system-partition writes, no automatic jailbreak or flashing. Hardware
verification is separate (see [DEVICE_TEST.md](DEVICE_TEST.md)); tests use synthetic transports.
Related: [NOKIA_N95.md](NOKIA_N95.md), [JAILBREAK_MANAGER.md](JAILBREAK_MANAGER.md),
[TRANSPORTS.md](TRANSPORTS.md), [DEVICE_MODELS.md](DEVICE_MODELS.md).

## Symbian TLS / CA revival (#34)

Revive → *Network and certificates* contains the TLS section. Sources reviewed 2026-11-05:
[shinovon/symbian-tls](https://github.com/shinovon/symbian-tls) (EPL-2.0),
[shinovon/mbedtls-symbian](https://github.com/shinovon/mbedtls-symbian) (Apache-2.0) and the
author's page <https://nnproject.cc/tls/>.

**Stacks.** *System SSL (replacement)* — the `ssl.dll` patch; per the author it serves native and
J2ME apps. *MBedTLS library* — `mbedtls.dso` for apps built against it. *Java SSL* — covered by the
system patch (the separate Java patch is "not used anymore" and is not offered). *Qt SSL* — the
author states the patch does not apply to Qt; nothing is offered.

**Applicability matrix** (E52/E72 Symbian 9.3, N95/N95 8GB 9.2, N97 mini 9.4): `documented` means
"the author's README lists S60 3rd Edition and FPs (9.1–9.3) and 5th Edition (9.4)". It is always
`not-tested` here. The author states neither firmware versions nor the ROMPatcher patch version;
both are shown as not stated. The SIS is unsigned and needs the InstallServer patch; extraction
into `C:` needs Open4All.

**Pinned components** (`symport/revive/tls_components.json`): `MBedTLS.sis` v1.4.4 and `ssl.zip`
v21 with size and SHA-256 observed on 2026-11-05, licence of the source repository, author link and
release notes. Binaries are not stored in the repository. *Download* fetches from `nnproject.cc`
only and refuses any size/hash difference — the author's URL is mutable, so a new upstream build
makes the download fail until the pin is re-verified. *Import file* accepts only a file that equals
a pin and then validates it (SIS checksums and package UID; ZIP entries, no key material).
Offline, no network or a broken or different file never produces an accepted component.

**Read-only diagnostics** state where each check ran: the HTTPS probe runs **on the SymPort
server** with full certificate verification (verification is never disabled; only the leaf
certificate is exposed); the Windows Bridge has no such action (`not-available`); the phone-side
test and the phone clock are typed by you. A phone date outside the certificate's validity window
is flagged — the commonest cause of TLS failures on old phones.

**Kit.** Dependencies are ordered (`ssl-patch` needs `mbedtls-lib`). Copying to the phone is a
*safe copy plan* of the Recovery Safety Net (below): `SymPort-TLS/`, read-back verification, no
overwriting of a different file, result `transferred-awaiting-manual-install`. Installation, the retest
result and the backup of the original `ssl.dll` are recorded by you and shown as "reported by
you". The system replacement is a separate **high-risk** block: it needs device-level rights, your
confirmed backup of the original, an identified model and device-reported firmware, and even then
SymPort has no tested privileged adapter, so the extraction is yours. Restore: uninstall MBedTLS
in the application manager; copy your saved `ssl.dll` back. SymPort cannot restore system files.
See also [DEPENDENCIES.md](DEPENDENCIES.md), [CERTIFICATE_INSPECTOR.md](CERTIFICATE_INSPECTOR.md).

## Recovery Safety Net (#36)

Every Revive scenario that copies files to a phone goes through one mechanism
(`symport/revive/safety.py`, actions `safety-*`; TLS components use it now, the Reborn wizard
registers its own scenario). The old direct "copy to phone" path was removed so that nothing
bypasses it.

1. **Plan (dry run).** Files come only from SymPort's own hashed store. The plan lists each target
   path, new files / conflicts / identical pre-existing files, bytes and free space after, the risk
   level, which risks block until you acknowledge them, the manual steps on the phone and how to
   restore. SymPort never overwrites a different file: a conflict is a blocking risk.
2. **Snapshot.** Only what is readable over this connection: the tree of the target folder, hashes
   of existing files at the targets, a contacts export only when `contacts.read` was verified (kept
   locally, never in the shareable report) and a package-file listing on enrolled volumes. Kinds are
   reported separately: `card-copy: not-performed`, `firmware: not-available`,
   `complete_phone_backup: false`. A snapshot **cannot restore the phone**: an SD-card copy never
   restores firmware or phone memory.
3. **Apply.** Requires the snapshot, an explicit confirmation, no open blocking risk and the
   scenario gates (identified model, platform, transport). The plan is *bound* to the connection
   fingerprint, model, RM, exact firmware and file hashes; another phone, different firmware or a
   changed file refuses it and a new plan is required. Each file is read back and compared; an
   interrupted transfer (link drop, conflict, hash mismatch) is saved as `interrupted` and can
   resume after the binding is re-checked, without repeating finished files. A finished plan cannot
   be applied twice. The result is `transferred-awaiting-manual-install`, never "installed".
4. **Postflight.** Read-only: re-reads the connection, compares identity with the snapshot,
   re-verifies the created files by hash. Boot, connectivity, Wi-Fi, files, contacts, applications,
   HTTPS and errors are a manual checklist (source `manual`). `installation` stays `unknown`.
5. **Rollback.** Only files this plan created, one at a time, and only if their bytes still equal
   the written/expected hash; changed files are kept and reported. No recursive deletion, the
   folder stays, installed software and system files (for example a replaced `ssl.dll`) are not
   restored. Rolling back from another phone is refused. Absence of a reliable restore procedure
   for a step is shown as a blocking risk that needs your separate acknowledgement.
6. **Report.** JSON export of a de-identified allow-list (model, RM, firmware, hashes, events with
   action/status/time, checklist). No IMEI, contact data, messages, secrets or snapshot payloads.

Automated tests use fake transports (`tests/test_safety.py`): interrupted transfer, reconnect,
phone swap, firmware change, file conflicts, SHA mismatch, re-applying a plan, rollback limits,
report contents. A separate manual checklist on real hardware is not part of CI; physical
verification is not claimed.

## Reborn Hybrid CFW (N95) (#35)

Data and source review: `symport/revive/reborn.json` (author page, `v1.00 alpha`, release date and
changelog `not stated`, distribution `unconfirmed`, no pinned artifact). Flow:

1. **Preflight from the device.** Model and RM must be *read from the device*; manual input never
   unlocks the kit. Unknown or conflicting variant, no reported RM, other models and **N95 8GB**
   (RM-320 family) are blocked — N95 8GB until support evidence for that exact firmware is added to
   `support_evidence`. A known N95 is only an *unverified candidate*: the author names no RM codes
   or firmware. RM-160 (NAM) and RM-245 (China) need an extra consent. Exact firmware must be
   device-reported; S60v3 FP1 comes from the model profile; free space ≥ 2 × the file + margin.
2. **Import.** You import the SIS you obtained from the author. SymPort validates structure and
   CRCs, reports signature state, runs the dependency analysis against the identified N95, lists
   every file it would install and flags system-level components (executables, resources, system or
   private paths). It never contacts the network.
3. **Pin.** You confirm that you obtained *this exact file* from the author; its SHA-256 becomes
   your local pin (`source: user-confirmed`, the author publishes no hash). A different file is
   refused for the plan until you pin it.
4. **Backup.** Your statement that a separate copy of important data exists (SymPort cannot verify
   it). No statement → transfer blocked. The Safety Net snapshot is *not* a backup of the phone.
5. **Plan and consents.** Safety Net plan with separate acknowledgements: alpha software,
   irreversible (no uninstall), variant not stated by the author, high-risk components (when
   present), regional variant. Device-level rights (installserver patch) must be recorded by you as
   your own observation; a card-only scope is not enough. Any unmet gate refuses the copy.
6. **Copy.** Verified file copy to `SymPort-Reborn/`, result `transferred-awaiting-manual-install`.
7. **On the phone.** You install; you record *installer opened / installed / restarted / network
   works*. The outcome is `installed-reported` only when you say so; a copy is never success.
8. **Postflight and rollback.** The Safety Net postflight and checklist apply. Rollback removes only
   the copied SIS from the card; the installation and system changes are not restored.

Tests (`tests/test_reborn.py`) use synthetic packages and fake transports; hardware verification
is separate and not claimed. No proprietary binaries are stored in the repository or the image.

### Reborn addendum (#35, 06.11.2026)

* The card states that the author's "format the phone if something goes wrong" is **not a reliable
  rollback**: it erases user data and does not guarantee a working phone.
* **Described changes in the package** (SSL/CA, UAProf, connectivity check, dropped dead services,
  file-manager settings, optional N-Gage library) are listed from the file names found in the SIS.
  A name match is a lead, not proof of the behaviour; no match reads *not detected*, never *absent*.
* The package version is read from the SIS and compared with the author's `v1.00` claim
  (`matches-author-claim` / `differs-from-author-claim` / `unreadable`).
* If the package contains `ssl.dll` / `mbedtls.dll` / `mbedtls.dso`, which the separate TLS stack
  also owns, the plan requires its own consent and shows the recorded TLS component state.
* After installation you record, per item, calls/SMS, file manager, Wi-Fi, HTTPS on the phone,
  alternative links and app launch/uninstall. They are stored as `user-reported` evidence and never
  turn into an installation claim by themselves.

## Revive home and Restore services (#33 addendum, #37)

**Home.** Shortcuts to *Restore services* and *Add-ons and patches* (disabled while the feature is
not in the build), suggestions for the model identified *from the device* (network components,
service endpoints, verified application kits) and one history for the phone. Suggestions are never
actions: nothing is installed, patched or marked fixed. A Reborn-hybrid suggestion appears only when
`support_evidence` holds a record for the exact model and firmware, which today it never does. The
history keeps *what / when / result / source* — never setting values, messages or secrets.

**Services registry** (`symport/revive/services.json`, reviewed 2026-11-05). Source: the public
[symbuzzer/reborncfw](https://github.com/symbuzzer/reborncfw) repository (GPL-3.0; the two Nokia
UAProf files carry Nokia's own notice). It is a set of **meta-refresh redirects**, not the firmware's
source: `conntest`, `dummy`, `homepage`, `store`, `tts`, `y` (s60tube), `update/N8`, `update/E7`
and two UAProf XML files. The source never states the original Nokia URL (`original_url: null`);
`update/N8` and `update/E7` could not be read (HTTP 404), so they have no target; the `dummy`
redirect names a host spelled `avallibeyaz.com` (double *l*) that SymPort never contacts. The
redirects point at a third-party server whose collaborators can edit them: trust is
`third-party-unverified` and none of it is promoted to a trusted distribution source.

**Statuses per model** (E52, E72, N95, N95 8GB, N97 mini): `available` is never assigned without
evidence; `manual-setup-required` (the browser homepage is a user setting), `not-confirmed` (the
source does not state applicability) and `unsupported`. The N8/E7 update widgets and UAProf files
are `unsupported` on every S60 model: Belle endpoints are not carried over. Maps, A-GPS/SUPL, WLAN
connectivity check, browser/mail/radio are listed with no reviewed source, so `not-confirmed`.

**Diagnostics** run **on the SymPort server** with certificate verification, only against an
allow-list of hosts, with redirects not followed; they compare the live meta-refresh target with the
registry (`matches-registry` / `drifted` / `no-redirect-found` / `unreachable`). They state that
they prove nothing about what a Nokia phone can open (its clock, certificates and TLS decide).

**Your settings.** SymPort never changes a phone setting. You record the value before and after and
the result of your test on the phone; credentials/tokens in values are refused; the record is
bound to the connection and shows how to put the old value back.

**Self-hosted bridge:** not implemented (`status: not-implemented`). Any future bridge needs an
allow-list, no open proxy, authentication, SSRF protection and no credential forwarding.

## Add-ons and Patch Manager (#39)

Revive → *Add-ons and patches* (`symport/revive/addons.json`, reviewed 2026-11-05). The registry
holds, per add-on: category, risk, author link, licence status, version (and whether it is
confirmed), target models, verified firmware versions, dependencies, conflicts, install and
uninstall instructions. TLS components reference their pinned artifacts instead of duplicating
them; the Reborn kit and the browser-homepage setting reference their own wizards. **A new version
is a new entry with its own pinned artifact; nothing follows a mutable link.**

**Dry-run plan** (`addons-plan`) → `blocked` / `manual-only` / `ready-to-prepare`. Blocking codes:
`model-unidentified`, `model-not-targeted`, `rm-unknown`, `category-closed`, `firmware-unverified`
(high risk with no verified firmware) / `firmware-unconfirmed`, `licence-missing`,
`version-unconfirmed`, `dependency-missing:<id>`, `conflict:<id>`, `autostart-conflict`,
`privileges-missing` and `incomplete-backup` (high risk: your own rights observation and backup
statement). Only a pinned artifact can reach `ready-to-prepare`, and then only as a copy through the
[Safety Net](#recovery-safety-net-36). Removal plans are manual and say that SymPort cannot restore
a system DLL after its SIS is gone.

**System patches are a closed category.** You must open it explicitly (confirm + acknowledgement
that SymPort only gives instructions). Opening it removes only that one block; the others stay, so
for example `rompatcher-debloated` (source and redistribution rights not established, FP1/FP2
unknown, author-claimed `domainsrv` autostart) can never be prepared. A binary existing is not proof
that it is safe.

**Levels:** `downloaded` and `transferred` are derived from the pinned cache and Safety Net plans;
`user-confirmed-installed` is what you report; `verified-on-device` is always `not-available`
(there is no agent). A newer pinned version raises an *update available* notice only.

**Patch Manager** is an inventory *you* type in (name, source, optional original SHA-256, state
`applied/disabled/autostart/unknown`, start chain, dependencies), stamped with the device-read
model/RM/firmware. It warns about missing dependencies, two patches starting through the same
mechanism, unknown state and entries recorded for other firmware. Applying, autostart and removal
are disabled: there is no proven API or recovery. No agent reads patches from the phone.
