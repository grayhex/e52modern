# SymPort Device Agent (S60v3) — status, protocol and permission model

**Status: protocol and host side only.** No phone-side binary (native S60v3 SIS or PyS60) has been built,
signed or run in this change: building one needs the S60 3rd Edition SDK and a device, neither of
which is available to CI. The host module (`symport/agent/`), the versioned protocol, the permission
model and a mock agent exist and are tested; the agent is `not-installed` in every build and every
existing function works without it. Reference tools for the eventual agent: FShell, Series60-Remote.
**Not** the "Backup & Restore for Symbian³" SIS from the author's page: that is a different platform.

## Levels (kept apart everywhere)

`agent-connected` (an authenticated reply arrived) → `operation-completed` (the agent says it did it) →
`device-verified` (evidence the host checked itself: a read-back SHA-256 for a copied file, a payload
SHA-256 for an export). Opening an installer proves no installation: `device-verified` stays false.

## Protocol `symport.agent/1`

JSON envelopes authenticated with HMAC-SHA256 under a key derived (PBKDF2) from a one-time pairing code
that the host shows once and you type on the phone; messages carry an id and a strictly increasing
sequence number, replies must match both, tampered or replayed replies are refused. Everything lives in
memory: after a restart you pair again and every permission is gone. Disconnect and revoke are explicit and
immediate. The Windows Bridge would be the transport; nothing is opened to the internet.

| Operation | Tier | Permission | Consent on the phone | Evidence |
|---|---|---|---|---|
| `hello`, `capabilities`, `ping` | read | – | no | authenticated reply / round trip |
| `sys.memory`, `sys.battery`, `sys.signal`, `sys.runtime` | read | `diagnostics.read` | no | API reading |
| `sys.processes` (permitted list only) | read | `processes.read` | no | API reading |
| `sys.packages` | read | `packages.read` | no | registry reading |
| `sys.patches` | read | `patches.read` | no | API reading |
| `net.test` (a host name you enter) | read | `network.test` | no | phone-side result |
| `log.tail` | read | `log.read` | no | agent log |
| `export.contacts` (fields you choose) | read | `export.contacts` | yes | payload hash |
| `file.echo-test` (≤ 64 KiB, `SymPort-*` folder) | confirmed | `files.test` | yes | read-back hash |
| `file.send` (≤ 64 KiB, `SymPort-*` folder) | confirmed | `files.send` | yes | read-back hash |
| `install.open` (file in a `SymPort-*` folder; opens the normal installer) | confirmed | `installer.open` | yes | none |

Each permission is granted individually and expires (at most one hour). Read replies are minimised to a
fixed allow-list of keys (an agent volunteering an IMEI or a token has it dropped). **Forbidden by design,
and unreachable by any message:** `shell`, `exec`, `system.write`, `jailbreak`, `flash`, `patch.apply`,
`file.delete-system`. The journal records an action name and a status only, never a path or a payload.

## Allowed read APIs for settings and databases (design matrix, not verified on a device)

Nothing is read from protected directories by a universal system bypass. A store is exportable only if a
documented API exists *and* the agent holds the capability that API requires; otherwise it is
`unsupported`, never replaced by copying a system database.

| Store | Documented API family | Capability the platform documents | Status |
|---|---|---|---|
| Contacts | Contacts Model / Phonebook engine | `ReadUserData` | design only; `export.contacts` defined and mock-tested |
| Calendar, tasks | Agenda Model | `ReadUserData` | design only; operation not defined yet |
| Messages | Messaging (MTM) session | `ReadUserData` (private) | design only; not defined (private data) |
| Profiles | Profile engine API | not established | `unsupported` until an API and its capability are confirmed |
| Application settings | Central Repository (per-repository policy) | per key | `unsupported` generally; individual keys only if their policy is documented |
| System databases | none permitted | – | `unsupported`: no blind copies |

Restore operations need preview, conflicts and read-back per component through a permitted API; where none
exists the answer is `unsupported`. Handing an agent export to the Recovery Safety Net / the settings backup is
not wired yet (it needs the settings backup level): the export is hash-verified on the host first.

## Hardware test checklist (manual, separate from CI)

See `agent/s60v3/CHECKLIST.md`. Models: E52 (FP2) and N95 (FP1). Until it is run, nothing here is claimed on a device.
