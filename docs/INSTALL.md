# Установка (Linux и WSL2)

Основная среда — Linux или WSL2 (Ubuntu 22.04+). Windows/macOS: тема и анализ работают где есть Python 3.11+
и `g++`; инструменты `symbian-platform` — macOS 15+/Linux glibc ≥ 2.28.

```bash
sudo apt install -y python3 python3-venv g++ git
git clone https://github.com/grayhex/e52modern && cd e52modern
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'          # symport + pillow, pytest, ruff
tools/s60/build.sh               # собрать skc и bmconv из вендорных исходников
symport doctor                   # что найдено, чего не хватает
```

Без установки: `python3 -m symport doctor` из корня репозитория (нужен Python ≥ 3.11).

## Что нужно для чего

| Операция | Обязательное | Необязательное |
|---|---|---|
| `theme inspect`, `sis inspect`, `app analyze`, `profile` | Python ≥ 3.11 | — |
| `theme build` | Pillow, `g++` (один раз, для `skc`/`bmconv`) | — |
| `theme package --backend native` | — | — |
| `theme package` (официально) | MakeSIS (+ SignSIS для подписи) | Wine на Linux |
| `app init/build/package`, `device *` | `symbian-platform` + нативный SDK | `openssl` |
| `emulator test` | EKA2L1 + собственные ROM/прошивка | — |

## WSL2

* Тема, анализ и упаковка выполняются целиком в WSL2.
* Запуск Windows-инструментов `makesis.exe`/`signsis.exe` из WSL2: `export SYMPORT_MAKESIS=/mnt/c/.../makesis.exe`
  (интероп WSL2 запускает `.exe` напрямую) — на практике не проверялось.
* Доступ к телефону по USB из WSL2 требует проброса USB (например, usbipd-win) — не проверялось;
  альтернатива — скопировать `.sis` на карту памяти/через PC Suite вручную.

## symbian-platform (для приложений)

```bash
python3 -m venv ~/.venvs/symbian && . ~/.venvs/symbian/bin/activate
pip install symbian-platform && symbian doctor
symbian sdk install ~/dev/symbian-sdk --archive <native SDK archive>    # glibc >= 2.39
export SYMPORT_SYMBIAN=$(which symbian)      # если он не в PATH SymPort
```

`pip install symbian-platform` и `symbian doctor` в среде разработки SymPort выполнены (версия 0.3.0). Нативный SDK-архив
и `symbian sdk install` — нет (в релизах не найдено доступных артефактов, API GitHub закрыт областью сессии).
Проверка связки одной командой: `tools/sdk/verify-real-sdk.sh` (нужны `clang++` с ARM-таргетом, `ld.lld`, `cmake`).

> `symbian app build` требует Ninja ≥ 1.12 и ищет его рядом с компилятором — см. раздел о Ninja в `docs/APPLICATIONS.md`.
