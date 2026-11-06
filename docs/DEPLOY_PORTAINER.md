# Установка одним Compose-файлом (Portainer, UGREEN, Docker Compose)

Клонировать репозиторий и собирать образ не нужно: [`compose.deploy.yaml`](../compose.deploy.yaml) использует готовый образ
**`ghcr.io/grayhex/s60modern`** и не содержит `build:` и путей к файлам репозитория.

## 1. Что публикуется

Workflow [`publish-image.yml`](../.github/workflows/publish-image.yml) собирает и публикует образ:

| Событие | Теги |
|---|---|
| push в `main` | `latest`, `main`, `sha-<коммит>` |
| тег `vX.Y.Z` | `X.Y.Z`, `X.Y` (`latest` следует за `main`, а не за тегом) |

**Архитектуры.** Каждая собирается на своём «родном» раннере и **публикуется только после smoke-теста запущенного контейнера**
(HTTP API, главная страница, пользователь 10001, контракт Gammu, сборка темы): `linux/amd64` обязательна, `linux/arm64`
(`ubuntu-24.04-arm`) публикуется, только если сборка и тот же тест прошли. Манифест перечисляет ровно то, что прошло; проверить:
`docker buildx imagetools inspect ghcr.io/grayhex/s60modern:latest`. Эмулятор (профиль `emulator`) — только amd64.

> Публикация идёт при каждом push в `main`. Если пакет в GHCR оказался приватным, откройте *Packages → s60modern →
> Package settings → Change visibility → Public*, иначе Portainer/UGREEN потребуют реквизиты реестра (логин GitHub
> и PAT с `read:packages`). Установка на Proxmox: [DEPLOY_PROXMOX.md](DEPLOY_PROXMOX.md).

## 2. Установка

**Portainer.** Stacks → *Add stack* → имя `symport` → *Web editor* → вставьте содержимое
`https://raw.githubusercontent.com/grayhex/s60modern/main/compose.deploy.yaml` → при необходимости задайте переменные
(*Environment variables*) → *Deploy the stack*.

**UGREEN (Docker → Проект → Создать).** Имя `symport`, вставьте тот же YAML в редактор Compose (или загрузите файл) → запустить.
Переменные окружения задаются в разделе переменных проекта (или заменой значений `${…:-…}` прямо в файле).

**Командная строка:**

```bash
curl -fsSLO https://raw.githubusercontent.com/grayhex/s60modern/main/compose.deploy.yaml
docker compose -f compose.deploy.yaml up -d
docker compose -f compose.deploy.yaml ps        # healthy через ~20 с
```

Данные (копии телефона, отчёты, загрузки) лежат в именованных томах `symport-build` и `symport-workspace`.

## 3. Как открыть интерфейс

Порт по умолчанию привязан к **loopback хоста** (`127.0.0.1:8765`), а сервер принимает только Host `127.0.0.1:<порт>` /
`localhost:<порт>` либо точный HTTPS-адрес из `SYMPORT_PUBLIC_ORIGIN`. Поэтому `http://IP-NAS:8765` в браузере **отклоняется
(403, Host not allowed)** — это защита, а не ошибка:

* **SSH-туннель (проще всего):** `ssh -L 8765:127.0.0.1:8765 user@nas`, затем `http://127.0.0.1:8765` на своём компьютере.
* **HTTPS-прокси** (встроенный в NAS или отдельный) с **обязательной аутентификацией**: задайте
  `SYMPORT_PUBLIC_ORIGIN=https://symport.example` (точный адрес) и проксируйте на `127.0.0.1:8765` (при необходимости
  `SYMPORT_BIND=0.0.0.0` только для докер-сети прокси, а не для LAN). Требования к прокси — в
  [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md#windows-phone-connection). Публичная переменная не заменяет аутентификацию.

Открытие в локальной сети без HTTPS/аутентификации сознательно не добавлено: интерфейс управляет файлами телефона.

## 4. Настройки (переменные)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `SYMPORT_IMAGE` | `ghcr.io/grayhex/s60modern:latest` | образ или тег (например `…:0.1.0`; лучше закрепить версию) |
| `SYMPORT_HTTP_PORT` | `8765` | порт (меняется вместе с проброшенным портом и healthcheck) |
| `SYMPORT_BIND` | `127.0.0.1` | адрес привязки порта на хосте |
| `SYMPORT_PUBLIC_ORIGIN` | пусто | точный HTTPS-адрес прокси |
| `SYMPORT_DEVICE_ROOTS` | `{}` | явно подключённые папки телефона/карты, например `{"phone":"/phone"}` |
| `SYMPORT_PULL_POLICY` | `missing` | `always` — тянуть образ при каждом запуске |
| `SYMPORT_UI_MODE` | пусто (`user`) | `developer` — свежий браузер стартует в режиме разработчика (выбор пользователя важнее) |
| `SYMPORT_GAMMU_CONFIG`, `SYMPORT_BRIDGE_*` | пусто | Gammu и PC Bridge ([DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)) |

Папка карты телефона: раскомментируйте в файле строку тома `- /volume1/phone:/phone:ro` (укажите свой путь, не корень хоста) и
задайте `SYMPORT_DEVICE_ROOTS='{"phone":"/phone"}'`. Запись на телефон при `:ro` невозможна — уберите `:ro`, если нужна запись.

## 5. Обновление и откат

* Portainer: Stacks → `symport` → *Pull and redeploy* (или *Re-pull image*); CLI: `docker compose -f compose.deploy.yaml pull && … up -d`.
* Откат: задайте `SYMPORT_IMAGE=ghcr.io/grayhex/s60modern:X.Y.Z` (предыдущий тег) и перезапустите стек. Тома сохраняются.
* `docker compose down -v` удалит данные — не используйте без копии.

## 6. Ограничения

Физический E52/E72 не использовался для проверки образа. USB-телефон, подключённый к другому компьютеру, виден только через
Windows Bridge ([WINDOWS_BRIDGE.md](WINDOWS_BRIDGE.md)); контейнер на NAS не получает USB автоматически.
