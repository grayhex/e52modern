# Эмулятор (EKA2L1)

```bash
symport emulator list
symport emulator test build/symport/theme/light/e52clearlight.sis --target nokia-e52
```

EKA2L1 — отдельная программа (GPL-3.0, не входит в репозиторий). Её README не описывает автоматизируемый CLI,
поэтому SymPort **не предполагает флагов**: команда запуска задаётся пользователем в `symport.toml`
(`[emulator] command = [...]`, плейсхолдеры `{sis}`, `{workdir}`, `{log}`; см. `docs/ARCHITECTURE.md`).
ROM/прошивка — ваши собственные, при необходимости копируются в одноразовый каталог (`data_root`).

Что делает `emulator test`: проверяет SIS читателем; копирует его в одноразовый каталог; запускает команду
с таймаутом; сохраняет `stdout/stderr` в `build/symport/emulator/*.log`; фиксирует код возврата и таймаут;
проверяет пользовательский `success_marker`; сохраняет скриншот, **только если** команда его создала (`screenshot`).

Что она **не** утверждает: нулевой код возврата или маркер в логе — это не «SIS установлен» и не «приложение
запущено». Эти проверки (`emulator.install`, `emulator.app_start`) всегда `unknown`, а
`verification.emulator` принимает значения `launched-unconfirmed` / `failed`. Физическое устройство —
`not-tested`.

Статус: адаптер реализован и проверен на поддельном эмуляторе; реальный EKA2L1 в этой среде не запускался.
