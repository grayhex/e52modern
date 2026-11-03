# Windows Bridge validation

2026-11-03. All fixtures are isolated temporary folders or explicit mock transports.
No physical Nokia is connected to this cloud environment.

- Linux regression suite: **299 passed, 1 skipped**. The optional WebSocket test is
  skipped without its extra; it runs with real websockets on the Windows CI job.
- Windows x64 CI: actual PyInstaller windowless executable, Gammu 1.45.1 / binding
  3.5, private frozen-worker IPC, Windows DPAPI, HTTP authorization, Origin/Host
  checks and dependency loading. No serial/Bluetooth hardware result is inferred.
- Chromium: owner pairing → loopback JSON consent endpoint → outbound relay →
  actual enrolled-folder byte read/write, JPEG thumbnail, authenticated private ZIP,
  revoke. The test injects the local approval callback explicitly; production uses
  a native default-No Windows dialog. RU/EN, dark/light and mobile layout checked.
- Existing browser suites: contacts/files/media/software/library, App Catalog,
  Emulator Lab contract, Inspector/Jailbreak privacy and device workspace passed.
- Docker image builds with existing Skin Compiler/bmconv and transport dependencies.
  Actual Gammu vCard/iCalendar codecs, ObexFTP 0.24, authenticated HTTP, JPEG,
  range 206, private-media rejection 403, verified ZIP and logical-only journal passed.
  Smoke containers had no published ports or user volumes and were removed afterward.
- Physical USB, Bluetooth, S60 Remote, OBEX FTP/OPP and PIM on E52:
  **не проверено на устройстве**. Follow TRANSPORTS.md for the manual protocol.

Screenshots `windows-bridge-dark-en.png` and `windows-bridge-light-ru.png` show an
explicitly enrolled temporary folder through the real relay, not a discovered phone.
The native confirmation and real Windows tray appearance need an operator UI review;
CI loads native UI dependencies but does not pretend to be a human desktop test.

Executable, source/license bundle, checksum and self-test JSON are generated as the
`SymPortBridge-Windows-x64` artifact by `.github/workflows/windows-bridge.yml`.
