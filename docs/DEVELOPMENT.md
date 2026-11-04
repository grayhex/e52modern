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
npm test --prefix frontend
node tools/check_react_workspace.cjs
pytest
ruff check .
node --check symport/web_assets/device-workspace.js
node tools/check_device_workspace.cjs
node tools/check_security_workspace.cjs
```

Browser checks require Playwright/Chromium and an editable Python install. Optional
`SYMPORT_PYTHON` and `SYMPORT_BROWSER_EXECUTABLE` select the interpreter/browser. Test
fixtures are temporary and deliberately identified as mock transports; they are not production
sample devices. Screenshot artifacts from the media check use real JPEG/WAV files on a local
enrolled directory. Unknown phone identity is not filled in to make a screenshot.

CI checks Python 3.11–3.13, lint, JavaScript syntax, Compose configuration, Docker startup,
python-gammu API availability, phone/media browser workflows, theme toolchain/reproducibility,
real SDK packages and the existing MGO/EKA2L1 integration without proprietary ROM. A passing
mock run demonstrates API orchestration, privacy and safety checks, not physical E52 compatibility.
The current transport matrix and hardware-validation boundary are in DEVICE_WORKSPACE.md.

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
