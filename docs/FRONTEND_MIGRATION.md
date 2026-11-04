# React migration — current checkpoint

This branch starts an incremental migration. It is **not a completed replacement**
of the existing 20-page application. The default `/` remains the existing UI;
`/next/` serves a separately built React client. No legacy controller is loaded,
wrapped in an iframe or executed inside the React tree. Unmigrated sections are
explicit links to the existing full application, not mock React implementations.

## Implemented

- React 19, TypeScript strict, exact optional properties and unchecked-index checks.
- Vite static build with copied fonts/brand/phone assets and lazy feature chunks.
- Existing Python POST contracts, token headers, same-origin cookies, Origin/Host
  policy and Windows Bridge pairing flow; no protocol/business-logic rewrite.
- TanStack Query owns device discovery, history, directory reads and mutations.
  Local preferences/selected phone use Context; no second server-state store.
- Nimbus shell, top-left navigation, RU/EN and persisted light/dark/system preference.
- React dashboard, connection selection/pairing, files list/download, confirmed
  mkdir/delete/upload/package transfer and table/grid presentation.
- ESLint, Prettier, runtime response decoding, component/API tests and a real Python
  filesystem E2E. Confirmation starts on Cancel; writes never auto-retry.

## Outstanding migration (must precede default switch)

- Gallery/streaming/bulk ZIP and complete Ringtone Studio.
- Contacts: import/export/edit/dedup, previews/backups/read-back sync.
- SMS conversations/export/backup and verified confirmed sending.
- Calendar/tasks/iCalendar/conflicts and sync previews.
- Full backups/restore and installed package inventory.
- Catalog, local themes/builds, developer tools and activity reports.
- Inspector, experimental Jailbreak wizard, Emulator Lab and Updates.
- Phone capability diagnosis/host enumeration/private IMEI control parity.

Every feature must retain backend validation, privacy, consent and existing E2E
coverage before replacing its classic link. Delete old controllers only after all
routes pass parity. The classic entry remains the rollback during parallel work.

## Develop/build/test

Node 22+, Python environment from DEVELOPMENT.md. Start Python on localhost:8765,
then `npm ci --prefix frontend && npm run dev --prefix frontend`. Vite's dev-only
session proxy obtains the existing HTML session token without a new auth contract.
Never expose the dev server publicly.

`npm run build --prefix frontend` creates `symport/react_assets/` (ignored in Git).
Python serves the result at `/next/` and injects its existing session token. A
separate web server can mount the static artifact at `/next/` on the same origin,
proxy `/api/` to Python and inject the session-token meta tag using its authenticated
server integration. Do not hard-code tokens in a public static artifact or URLs.

`npm run typecheck`, `npm run lint`, `npm run format:check`, `npm test` (all with
`--prefix frontend`). E2E: `node tools/check_react_ui.cjs` with Playwright installed.
Docker builds Node assets in a separate stage; Node is absent from the runtime.
Frontend CI publishes the static artifact separately from the Python image.

Native `<dialog>` supplies modal semantics/focus containment/Escape. Radix/React
Aria are not added without a concrete missing interaction. TanStack Table can be
introduced behind the typed file-row/action contracts for sorting/selection;
Zustand is reserved for local cross-feature editor state if Context proves insufficient.
