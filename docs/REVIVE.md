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
