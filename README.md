# E52Modern

Воспроизводимая среда разработки для Symbian S60 с целевым устройством **Nokia E52** (Symbian 9.3 / S60 3rd Ed. FP2,
240×320, аппаратные клавиши). Состоит из двух частей:

1. **E52 CLEAR** — действующий подпроект: тема для E52 (Light/Dark). Файлы `.skn/.mbm/.mif/.pkg` собираются
   оригинальным компилятором Nokia; см. [`theme/README.md`](theme/README.md), [`tools/s60/README.md`](tools/s60/README.md).
2. **SymPort** — Python-инструментарий (`symport/`), который объединяет сборку и проверку тем, упаковку SIS,
   анализ бинарной совместимости, профили устройств и обвязку SDK/эмулятора/устройства. Принцип: *reuse first* —
   существующие инструменты вызываются как backend'ы, а не переписываются.

> **Статус честно:** тема и приложения **не проверялись на физическом Nokia E52** и в эмуляторе. Автоматически проверена
> статическая корректность файлов; разбор E32/SIS сверен с реальным SDK `symbian-platform` (`tools/sdk/verify-real-sdk.sh`). См. [`docs/STATUS.md`](docs/STATUS.md) и [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## Быстрый старт

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
tools/s60/build.sh                 # собрать skc и bmconv из вендорных исходников (нужен g++)
symport doctor                     # окружение и backend'ы
symport theme build                # обе темы (то же, что python3 tools/build_theme.py)
symport theme inspect              # структура SKN/MBM/MIF, PKG, UID, палитра, манифест
symport theme package --variant light --backend native    # экспериментальный неподписанный SIS
```

Старые команды работают без изменений: `tools/s60/build.sh`, `python3 tools/build_theme.py`.
`python -m symport` и команда `symport` эквивалентны.

## Браузерная панель (Docker / Linux / WSL2)

В SymPort Workbench можно собирать тему, получать SIS, проверять окружение, управлять проектами и вести ручной протокол Nokia E52 без работы в консоли после запуска сервиса.

```bash
# Linux-сервер; слушает только loopback
 docker compose up -d --build
# На Windows: ssh -L 8765:127.0.0.1:8765 user@your-server
# Открыть: http://127.0.0.1:8765
```

Без Docker: `python -m symport.web --open` (после установки зависимостей и компиляторов).

См. [документацию Workbench](docs/WEB_UI.md). Сборка в Docker не содержит официальный MakeSIS или native GUI SDK по умолчанию; экспериментальный SIS не проверен на E52. USB на Windows не виден удалённому серверу автоматически.

## Команды

| Группа | Команды |
|---|---|
| Окружение | `doctor`, `profile list/show` |
| Тема (P0) | `theme build`, `theme inspect [--reproducible]`, `theme package [--backend auto\|makesis\|native\|modern-sdk]` |
| Анализ | `sis inspect`, `sis compare`, `app inspect`, `app analyze [--firmware-profile] [--cross-check]` |
| Приложения (P1) | `app init`, `app build [--mode app\|toolchain]`, `app package` (через `symbian-platform`) |
| Тестирование (P2) | `emulator list/test`, `device list/info/stage`, `report matrix` |

Каждая команда поддерживает `--json` и `--report FILE`. Коды возврата: 0 успех, 1 ошибка проверки, 2 ошибка использования,
3 операция недоступна (нет инструмента).

## Документация

[Архитектура](docs/ARCHITECTURE.md) · [Установка Linux/WSL2](docs/INSTALL.md) · [Внешние инструменты (аудит)](docs/EXTERNAL_TOOLS.md) ·
[Сборка темы](docs/THEME.md) · [Упаковка и подпись SIS](docs/PACKAGING.md) · [Первое приложение](docs/APPLICATIONS.md) ·
[Бинарная совместимость](docs/COMPATIBILITY.md) · [Эмулятор](docs/EMULATOR.md) · [Тест на E52](docs/DEVICE_TEST.md) ·
[Статусы](docs/STATUS.md) · [Ограничения](docs/LIMITATIONS.md)

## Тесты и CI

```bash
pytest            # без телефона и без проприетарного SDK
ruff check .
```

CI (`.github/workflows/ci.yml`): стиль, тесты на Python 3.11–3.13, сборка `skc`/`bmconv`, пересборка обеих тем,
проверка выходных файлов, воспроизводимость, JSON-отчёты и экспериментальный SIS как артефакты. Чужие ROM, прошивки,
закрытые SDK и приватные ключи в CI не используются.

## Лицензии

Код SymPort — MIT (см. `pyproject.toml`). Вендорные исходники Nokia/Symbian Foundation — EPL-1.0
(`tools/s60/vendor/NOTICE.md`). Внешние программы (symbian-platform — Apache-2.0, EKA2L1 — GPL-3.0) не входят в репозиторий.
