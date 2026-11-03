# E52Modern

**SymPort** — веб-среда для работы с телефонами Symbian S60. Подключите телефон,
управляйте доступными файлами, передавайте пакеты, сохраняйте резервные копии и
работайте с локальной библиотекой тем. Первый целевой телефон — **Nokia E52**
(Symbian 9.3 / S60 3rd Edition FP2).

Основной интерфейс — **SymPort Phone Workspace**. CLI, SDK и инструменты разработки
остаются частью проекта: они помогают создавать, проверять и упаковывать темы и приложения.
E52 CLEAR — встроенный проект темы Light/Dark, а не единственное назначение среды.

| Раздел | Сейчас |
|---|---|
| Телефон и файлы | Явно подключённые накопители, просмотр, загрузка, скачивание, каталоги, удаление с подтверждением |
| Подключение | Локальный накопитель, необязательный Gammu identify, PC Bridge через SSH |
| Контакты и SMS | Отдельные разделы; недоступны до появления проверенного транспорта |
| Приложения телефона | Передача SIS/SISX; реестр установленных приложений недоступен |
| Резервные копии | Файлы выбранного каталога, ZIP и восстановление с предпросмотром, без перезаписи |
| Темы | Загрузка SIS, отдельная публикация в локальной библиотеке, скачивание и передача |
| Разработка | Сборка E52 CLEAR, создание приложений, анализ SIS/E32, протокол испытаний |

**Аппаратная совместимость не подтверждена:** нет тестов на физическом E52 или в эмуляторе.
Передача SIS не означает установку; наличие файла не означает наличие приложения.
[Подключение телефона и PC Bridge](docs/DEVICE_MANAGER.md) · [Архитектура](docs/ARCHITECTURE.md).

## Быстрый старт

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
python -m symport.web             # основной веб-интерфейс, только localhost / SSH
# Дополнительные средства разработки:
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

## Device Manager

Workbench включает файловый Device Manager: зарегистрированные накопители, Gammu identify, передача SIS, журнал и файловый ZIP backup/restore с предпросмотром. Для удалённого ПК предусмотрен PC Bridge через SSH. См. [подключение и ограничения](docs/DEVICE_MANAGER.md). Аппаратная совместимость с E52 не подтверждена.

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
