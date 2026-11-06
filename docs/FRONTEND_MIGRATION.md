# React frontend

SymPort's 20 sections now run in React 19 with strict TypeScript and Vite. The
Python API, CLI, transport implementations and Bridge contracts are unchanged.
There are no legacy controllers, DOM-built views, global application variables or
iframes in the React entry. Nimbus CSS, graphics, E52/E72 profiles, RU/EN and
light/dark/system preferences are reused.

## Entry points and phased rollout

The work was split into foundation/dashboard/files/connection, phone data and
media, then catalog/security/development/emulation, followed by compatibility
checks. Docker builds the complete static client and opens it at `/`.
`/next/` is an equivalent explicit entry. `/classic` retains the previous UI as a
rollback while parallel feature branches move to React. `SYMPORT_FRONTEND=classic`
selects it at `/` too; no API, transport or data migration is involved. An editable
Python checkout without a frontend build falls back to the classic entry.

The old controllers are isolated to that rollback entry. They are deliberately
retained for comparison and regression tests; new features belong in `frontend/`.

## Nokia Classic, навигация и новые библиотеки (2026-11-04)

* **Тема и навигация.** Интерфейс переведён на Nokia Classic ([UI_DESIGN.md](UI_DESIGN.md)), боковое меню — пять групп с
  редиректами старых URL ([NAVIGATION.md](NAVIGATION.md)). Идентификаторы секций — `page-<группа>-<страница>`.
* **Файловый браузер.** `@harryy/react-file-browser` 1.5.1 (MIT) с адаптером Device Manager (`api/phoneFiles.ts`).
  Библиотека не поставляет CSS и использует утилиты Tailwind v4: подключены только `theme` и `utilities` (без preflight,
  `@tailwindcss/vite` — в devDependencies) в слое выше прежних стилей, токены `--fb-*` привязаны к Nokia. Предпросмотр и
  скачивание идут через `GET /api/device/file` (cookie сессии, Fetch Metadata: встраивание — inline, навигация — attachment,
  `CSP: sandbox`, SVG/SIS/неизвестное — только вложение). Хранилище передач отключено (`storage: null`), имена файлов не пишутся
  в `localStorage`. Возможны только list/delete/upload/mkdir; rename/move/copy в API нет и в интерфейсе скрыты. Подписи библиотеки — английские.
* **Дашборд.** MUI 7 + `@mui/x-charts` 8 с темой на токенах Nokia, кэш Emotion с nonce (CSP `style-src` не ослаблена); показаны
  только данные транспорта.
* **Иконки** — `lucide-react`. Уведомления о лицензиях (`THIRD_PARTY_NOTICES.txt`) формируются из `package-lock.json` для всех
  production-зависимостей.
* Новые страницы: Firmware & ROM Explorer, Зависимости и совместимость, Комплекты приложений, Установочные пакеты, заготовки «В разработке».
* Node: файловая библиотека объявляет `engines.node >=24`; клиент, Docker и CI используют Node 26 LTS.

## Architecture

- `src/features/`: lazy route components for every existing section. React Activity
  preserves visited editor drafts in RAM and suspends effects while hidden; a new
  explicit package/gallery intent resets only its destination view.
- `src/components/`: Nimbus cards, accessible labels, device selectors, package
  pickers, native dialogs, error boundaries and declarative downloads.
- `src/hooks/`: shared queries and one-shot confirmed operations.
- `src/api/`: typed client and Zod runtime response contracts. Requests preserve
  token headers, same-origin cookies, cancellation and existing JSON payloads.
- `src/state/`: Context for preferences, selected connection and a RAM-only contact
  name index scoped to a device fingerprint. Only language/theme are persisted.
- `src/utils/`: bounded file encoding and package navigation helpers.

TanStack Query owns discovery, directory/media reads, jobs, library/catalog,
connection/Lab state and mutations. Writes never automatically retry. Personal
snapshots/plans are RAM-only, expire on the backend, and plans are consumed before
writing; personal query caches are removed when their view is hidden or unmounted.
Editor drafts stay in RAM until cleared, their device changes or the tab closes. Changing the
connection clears the contact-name index. IMEI reveal expires after 30 seconds or
window blur. No contact/message/IMEI values are added to ordinary logs.

WaveSurfer is confined to a lifecycle-managed component; React refs synchronize
its external media surface, focus, pointer capture and native dialogs. Ordinary
view rendering never uses `innerHTML`, selectors or manual node insertion.

Native tables and dialogs cover current interactions without extra UI frameworks.
File views have typed rows/actions, independent table/grid presentation and query
keys for future selection, drag/drop, menus and batching. TanStack Table, React
Aria or Radix can be added behind these interfaces when a concrete interaction
requires them. Context is sufficient for current local shared state; adding
Zustand would duplicate no necessary state.

## Feature compatibility

| Area | React workflow |
|---|---|
| Dashboard / Updates | Real adapter values, unknown badges, firmware reference, E52/E72 art, lifetime where supplied; physical flashing disabled |
| Connection | Discovery, capabilities, host candidates, diagnosis, private IMEI, Windows pairing/revoke |
| Files | Browse/download/upload, directory creation, confirmed deletion and SIS transfer; folder ZIP backup and restore preview |
| Gallery / audio | Search/type/sort/select, bounded thumbnails, Range preview, ZIP, upload; WaveSurfer regions/presets/zoom/loop, FFmpeg export and confirmed exact-file transfer |
| Contacts | Google CSV/Apple vCard import/edit/select/export, phone reads, duplicates, safe sync preview, backup/read-back |
| SMS / calendar / tasks | Reads/search/thread/filter/export/backup, verified confirmed SMS; editing and iCalendar import with conflict preview |
| Catalog / apps | Search/filter/collections/sets, dependency plans, background queues/receipts/ZIP/manual links, user installation confirmation; package inventory and batch transfer |
| Backups | Server file-copy jobs, verification, restore dry-run and confirmed add-only restore; Bridge folder backups in Files |
| Themes / development | Build/inspect/package/projects, local explicit publication/download/transfer, diagnostics and manual device protocol |
| Inspector / experimental wizard | Real signatures/certificates/compatibility/JSON, diagnosis and Lab/phone handoff; archive exclusions, dry-run/backup/staging/manual confirmations and scoped rollback |
| Emulator Lab | Existing MGO firmware upload/select/install, E52 controls and keyboard, frames, SIS/theme tests, manual theme application, screenshots/logs/reports and verified-byte transfer |

Capability limits still come from the selected adapter. Transfer is not
installation; Mass Storage does not expose personal databases. KEmulator is not
Symbian Java ME. Mock phone/MGO runs validate frontend contracts, not hardware or
successful boot of user firmware.

## Develop, build and deploy

Node 24+ (CI и Docker — Node 26 LTS), Python setup from [DEVELOPMENT.md](DEVELOPMENT.md):

```bash
npm ci --prefix frontend
python -m symport.web                  # localhost:8765
npm run dev --prefix frontend          # separate terminal; localhost:5173/next/
npm run build --prefix frontend
```

The dev-only proxy obtains the existing HTML session token and forwards `/api/`
to local Python. Do not expose Vite publicly. Build output is
`symport/react_assets/`, ignored by Git and included in Docker by a Node build
stage; Node/npm are absent from the Python runtime. CI also publishes this as an
independent static artifact. Wheels include a previously generated build. The artifact carries
`THIRD_PARTY_NOTICES.txt` with the bundled libraries’ license texts.

For a separate static server, mount the artifact at `/next/` on the same origin,
proxy `/api/` to authenticated Python, and inject its per-process token into the
session-token meta tag at the authenticated HTML entry. Preserve the existing
private session cookie and CSP. Do not hard-code a token in publicly cached HTML,
URLs or build variables. This does not turn the phone API into a public service.

## Verification

```bash
npm run typecheck --prefix frontend
npm run lint --prefix frontend
npm run format:check --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
node tools/check_react_ui.cjs
node tools/check_react_workspace.cjs
node tools/check_p0_ui.cjs
tools/s60/build.sh
node tools/check_p1_ui.cjs
```

Browser checks need Playwright/Chromium, Python's development extras and FFmpeg.
`SYMPORT_PYTHON` / `SYMPORT_BROWSER_EXECUTABLE` select local executables. Component
tests include nullable API metadata, accessible labels, confirmation focus and
consumed plans after uncertain writes. Browser parity exercises all 20 routes,
actual private files/Range/ZIP/FFmpeg, Google import, contact/calendar backup and
read-back, SMS CSV/privacy, genuine SDK certificate inspection, library publication
and controlled rollback. Stateful phone and MGO doubles are explicitly test-only.

`check_react_runtime_ui.cjs` separately exercises the pinned real MGO/EKA2L1 service
without ROM: disabled no-firmware controls, VPL/FPSX upload, genuine installer
failure and durable evidence without a fabricated screen. It refuses to run on an
instance with user firmware. CI keeps existing Python/CLI/Bridge/classic regression
checks and publishes React screenshots and the independent static artifact.
