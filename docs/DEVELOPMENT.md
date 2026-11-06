# Development and validation

The existing CLI, Workbench, Docker Compose and theme toolchain remain the development entry points.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,phone,media]'
tools/s60/build.sh                  # requires g++
npm ci --prefix frontend
npm run build --prefix frontend
python -m symport.web               # localhost only; React at /
symport doctor
symport theme build
symport theme inspect
symport theme package --variant light --backend native
```

`python -m symport` and `symport` are equivalent. The native SIS backend is experimental;
use the generated validation reports and selected phone/firmware profile when evaluating a package.

| Area | CLI |
|---|---|
| Environment | `doctor`, `profile list/show` |
| Themes | `theme build`, `theme inspect`, `theme package` |
| Analysis | `sis inspect`, `sis compare`, `app inspect`, `app analyze` |
| Applications | `app init`, `app build`, `app package` |
| Phone | `phone backup create/verify/restore`, `phone apps inventory`, `phone stage`, `phone calendar read` |
| Testing | `emulator list/test`, `device list/info/stage`, `report matrix` |

Commands support JSON/report output; consult `--help` for each subcommand. Device Manager's
browser API additionally exposes the bounded media and personal-data workflows described in
[DEVICE_WORKSPACE.md](DEVICE_WORKSPACE.md). There is no shell-command HTTP endpoint.

For hot reload, start Python and run `npm run dev --prefix frontend` in another
terminal. See [FRONTEND_MIGRATION.md](FRONTEND_MIGRATION.md) for the typed API,
state ownership, static build and rollback entry.

## Checks

```bash
npm run typecheck --prefix frontend
npm run lint --prefix frontend
npm run format:check --prefix frontend
npm test --prefix frontend
pytest -n auto                       # pytest-xdist; the suite is safe to run in parallel
ruff check .
node tools/check_react_workspace.cjs # browser checks: see the list below
```

Browser checks (Playwright + Chromium, run against the real Python server on synthetic data, one script each):
`check_react_ui`, `check_react_workspace`, `check_p0_ui`, `check_connection_wizard`, `check_layout`,
`check_p1_ui`, `check_n95_ui`, `check_n97_mini_ui`, `check_revive_ui` (recovery pages), plus the older
`check_web_ui`, `check_app_catalog`, `check_emulator_lab`, `check_security_workspace`, `check_device_workspace`,
`check_ringtone_ui`, `check_bridge_ui`. Build the frontend first (`npm run build --prefix frontend`).

`node tools/capture_screenshots.cjs` regenerates `docs/screenshots/` after a visual change.

### CI layout

| Workflow | Jobs |
|---|---|
| `ci.yml` | `lint`, `tests` (Python 3.11–3.13, xdist), `theme`, `real-sdk` (main and manual runs only, non-gating), `workbench` and `device-manager-container` (Docker image with a shared layer cache), `phone-workspace-browser` |
| `frontend.yml` | `frontend` (lint, format, vitest, production build, build artifact) then `e2e` in three parallel groups (`core`, `devices`, `revive`) that reuse the build |
| `windows-bridge.yml` | portable EXE and installer on Windows; release on `bridge-v*` tags |
| `publish-image.yml` | multi-architecture image to GHCR on `main` and `vX.Y.Z` tags, after a smoke test of the running container |

Pushes run on `main` and tags; every other branch is checked through its pull request, and a newer push cancels the
older run. Python and npm caches, a cached Playwright/Chromium (`.github/actions/browser-tools`) and the Docker layer
cache keep a typical run short. `dependabot.yml` proposes monthly updates for Actions, npm, pip and the base images.

Browser checks require Playwright/Chromium and an editable Python install. Optional
`SYMPORT_PYTHON` and `SYMPORT_BROWSER_EXECUTABLE` select the interpreter/browser. Test
fixtures are temporary and deliberately identified as mock transports; they are not production
sample devices. Screenshot artifacts from the media check use real JPEG/WAV files on a local
enrolled directory. Unknown phone identity is not filled in to make a screenshot.

CI checks Python 3.11–3.13, lint, JavaScript syntax, Compose configuration, Docker startup,
python-gammu API availability, phone/media browser workflows, theme toolchain/reproducibility,
real SDK packages and the existing MGO/EKA2L1 integration without proprietary ROM. What the automatic checks
do and do not prove about a physical phone is described once, in [STATUS.md](STATUS.md).

## Further documentation

[Architecture](ARCHITECTURE.md), [theme build](THEME.md), [SIS packaging](PACKAGING.md),
[application SDK](APPLICATIONS.md), [compatibility](COMPATIBILITY.md),
[external tools](EXTERNAL_TOOLS.md), [manual handset validation](DEVICE_TEST.md).

SymPort is MIT. Vendored Nokia/Symbian Foundation sources use EPL-1.0 (see
`tools/s60/vendor/NOTICE.md`). External dependencies keep their own licenses; MGO/EKA2L1
and proprietary firmware are not copied into this repository.

Ringtone Studio regression uses real local FFmpeg, not simulated audio results:
`pytest tests/test_ringtone.py`. Browser: `node tools/check_ringtone_ui.cjs`
(with Playwright/Chromium). It checks gallery import, WaveSurfer editing, decoded
MP3 metadata/bytes, confirmed file transfer, temporary cleanup and E72 presentation.
The E72 identity is an explicit test fixture; device hardware is not emulated by it.
Vendored WaveSurfer source/version/integrity/license live under `web_assets/vendor/`.
