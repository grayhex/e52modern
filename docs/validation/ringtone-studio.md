# Ringtone Studio / E72 / Docker validation

2026-11-03. Existing phone transports and CLI remain shared; no firmware flasher added.

- Local suite: 317 passed, one optional WebSocket check skipped without its extra.
- Actual FFmpeg: WAV/M4A/MP4/FLAC decode, mono/resampling/LUFS/fades/MP3,
  repeat-read through DeviceManager, invalid input/filter values, playlist rejection,
  private HTTP cookie/Range, expiry and failed-input cleanup.
- Chromium: actual locally vendored WaveSurfer Regions, gallery import, numeric trim,
  preset, zoom/play, processed MP3 metadata/download, confirmed byte-identical transfer,
  source deletion, RU/EN, light/dark/mobile and no external HTTP requests.
- E72 uses a documented 320×240/QWERTY model profile inferred from the actual adapter
  model response. Browser demonstration supplies an explicit E72 identity fixture.
  Artwork body ratio is checked separately; CSS preserves its intrinsic ratio.
- Docker image built locally with FFmpeg 7.1.5. A separate container with no network,
  published ports or user volumes encoded normalized mono MP3 at 22.05 kHz, verified
  its transfer bytes and deleted its temporary source. Compose validates; old SSH and
  phone overlays remain available. Windows installer syntax is checked by Windows CI.
- Existing contact/SMS/calendar, backup, Catalog, Inspector and Emulator Lab browser
  checks remain in CI. No hardware compatibility or physical flashing is inferred.

Screenshots use generated audio and temporary mounted folders. The E72 illustration
is an original decorative asset; it is not a photo or an emulator button-coordinate map.

Compact layout regression: at 1366×768 with advanced options collapsed, the editor
and processed result fit inside the viewport. The logo stays within the top 32 px.
Long Inspector pages are also scrolled at 1440×600/1100 to check top-left anchoring
and independent menu scrolling. On narrow mobile screens the editor stacks normally.
