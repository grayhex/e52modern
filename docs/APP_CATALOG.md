# App Catalog

Каталог находится в боковом меню SymPort Phone Workspace. Это локальная подборка,
а не публичный маркетплейс. Аккаунтов, платежей и автоматической установки нет.

## Данные и проверка источников

На 3 ноября 2026 каталог содержит **30 карточек: 18 с автоматической загрузкой и
12 с ручной загрузкой у автора**. Дистрибутивы исследовались по оригинальным
репозиториям, релизам и архивам разработчиков. Проверены реальные файлы, размер,
локальный SHA-256 и поддерживаемые анализатором структуры. Публичный SHA-256
разработчика/релиза, когда он доступен, хранится отдельно от вычисленного нами.

Проверка файла не является проверкой запуска. **Ни одно приложение не объявлено
проверенным на физическом E52.** `verified-on-s60` означает сообщение автора о
других S60 устройствах, с источником в карточке. `likely-compatible` означает лишь
соответствие объявленному S60 или MIDP/CLDC профилю E52. Для неизвестной даты релиза
показывается «Не опубликована»; время исходного коммита не выдаётся за дату релиза.
Дата старого ScummVM отражает timestamp артефакта в официальном архиве.

Полезность 2026 года оценивается отдельно от активности разработки: офлайн-читалка,
реверси или IP-калькулятор не требуют действующего облачного сервиса. У онлайн-
клиентов явно указаны внешние API, собственные backend, TLS и доверие к прокси.
Работоспособность логина, токенов и публичных серверов не проверялась. AIKON требует
своего сервера и API-ключей; BlueWAP — второго устройства с серверным приложением;
MeshCore — Companion Radio/моста. SymPort их автоматически не разворачивает.

## Дополнительные поля записи (2026-11-04)

Схема допускает необязательные поля, которые показывает окно «Подробнее»:

* `runtime_requirements` — требуемые среды выполнения (например `Qt ≥ 4.7.3`, статус `unverified`): не блокирует загрузку и
  передачу, но SymPort не поставляет runtime и не видит его на телефоне;
* `guide` — шаги установки и настройки (`title`, `steps`, `docs`), например серверный companion;
* `conflicts_with` — записи с общей идентичностью (EN/RU Jellyfin): выбор обеих даёт ошибку плана.

Источник может быть не только GitHub: для X-plore одобрен `www.lonelycatgames.com` (страница автора, пакет закреплён по SHA-256).
Новые записи: [X-plore](XPLORE.md), [Jellyfin for S60](JELLYFIN_S60.md) — **установка и запуск на E52 не проверялись**.

## Пользовательский маршрут

1. Выберите категорию, профиль E52, сеть, формат или готовую подборку.
2. Отметьте приложения; сохраните набор под своим именем, если планируете повторять.
3. Нажмите **«Проверить зависимости»**. Программные зависимости разворачиваются в
   нужном порядке; внешние ресурсы и ограничения показаны отдельно.
4. **«Скачать и проверить»** запускает очередь с исходными одобренными URL. Для
   каждой программы видны этапы и ошибка, если источник/проверка недоступны.
5. Скачайте проверенный ZIP на ПК либо выберите телефон и существующую папку,
   подтвердите пакетную передачу. Проверяются свободное место и SHA-256 чтением обратно.
6. На Nokia откройте SIS/JAR (или локальный JAD со связанным JAR), завершите установку
   и проверьте запуск. Только после этого нажмите **«Я установил на телефоне»**.

Статусы: `downloaded` → `validated` → `transferred` → `awaiting-installation` →
`user-confirmed-installed`. Последний статус — ручное наблюдение пользователя,
а не доказательство удалённой установки. При частичной ошибке неудачные элементы
можно выбрать для повтора; уже переданные идентичные файлы не перезаписываются.
Другой файл с тем же именем вызывает ошибку. Прерванная задача после перезапуска
получает `interrupted`; автоматического возобновления записи на телефон нет.

### Ручной режим

Карточки с ограничениями лицензии, упаковки, подписи или источника имеют кнопку
**«Скачать вручную»** и ссылку **«Передать свой пакет»**. Они не попадают в автоматическую
очередь. Получите пакет непосредственно у автора, извлеките SIS/JAR из ZIP, если
нужно, и воспользуйтесь существующим разделом «Приложения телефона». Никакой платный
софт не превращается в freeware из-за наличия ссылки. Неизвестная лицензия означает
отказ от автоматического кэширования, а не разрешение на распространение.

В частности, MPGram доступен с оригинального сайта, MapNav и ScummVM — в официальных
ZIP, PyS60 — в исходном архиве Nokia. Системные патчи не включены в массовые подборки.
Отдельная категория `high-risk` скрыта по умолчанию и блокируется планировщиком.

JAD с неправильным размером/именем или иной идентичностью не переписывается ради
успешной проверки. Для IP Calculator, PassGen и Celeste выбран валидный JAR без
некорректного необязательного JAD; VK4ME также используется как JAR без дескриптора,
который указывает на внешний HTTP URL. Все изменения выбора отражены в карточках.

## Архитектура и хранение

- `catalog/apps/*.json` — метаданные карточек; `schema.json` — формат записи.
- `catalog/sources.json` — отдельные заранее одобренные URL и контрольные значения.
- `catalog/research.json` — исключённые/неподтверждённые кандидаты и причины.
- `symport/catalog/model.py` — runtime-проверка схемы и планирование зависимостей.
- `symport/catalog/packages.py` — общий валидатор SIS/JAR/JAD, используемый также Device Manager.
- `symport/catalog/download.py` — downloader с HTTPS, проверкой DNS/редиректов, лимитов и SHA.
- `symport/catalog/service.py` — очередь, кэш, наборы, история и пакетная передача.

Кэш: `build/symport/app-catalog/cache/<sha256>/<filename>`; наборы: `sets.json`;
задачи и этапы: `jobs/*.json` в том же каталоге. Всё сохраняется существующим Compose
volume `symport-build`. Метаданные и source pins входят в Git, бинарники — нет.
ZIP набора включает manifest с источниками и лицензиями; условия программ сохраняются.

API не принимает произвольные URL: только ID каталога. Разрешены заранее заданные
HTTPS-хосты GitHub и его CDN/raw-доменов, только публичные DNS-адреса, максимум пять
редиректов. Проверяется каждый переход, размер, время, целостность и структура.
Обновление бинарника по старому URL не принимается, если SHA не совпал. Проверенный
кэш используется повторно и без DNS-соединения; при повторе SHA проверяется заново.
Файлы не запускаются ни downloader, ни валидатором.

Лимиты: 32 МиБ на пакет, 128 МиБ на набор; до 50 выбранных приложений и 30 сохранённых
наборов. Общий файловый upload остаётся 8 МиБ; программные пакеты допускают 32 МиБ,
медиа — 64 МиБ. Локальный/Bridge read-back поддерживает файлы до 64 МиБ. Для JAR
ограничены количество entries и распакованный размер; для SIS — размер полей и
суммарных распакованных данных. JAD проверяется со связанным JAR до передачи.

## Docker / Windows

Каталог и downloader работают на Linux-сервере, телефон может находиться на Windows.
Выбор устройства использует существующий Device Manager / PC Bridge через SSH-туннель.
Телефон подключать непосредственно к Linux не требуется. Обновляйте обе стороны
Bridge до одинаковой версии, особенно для программ больше 8 МиБ.
См. [подключение](DEVICE_MANAGER.md). Публичный API управления телефоном не открывается.

## Проверки

```bash
python tools/verify_app_catalog.py                 # схема/метаданные, без сети
python tools/verify_app_catalog.py --download      # все автоматические источники + pins/пакеты
pytest -ra
node --check symport/web_assets/catalog.js
# Playwright установлен отдельно; используются тестовые том/пакеты, не реальный телефон:
SYMPORT_PYTHON=python SYMPORT_BROWSER_EXECUTABLE=/usr/bin/chromium node tools/check_app_catalog.cjs
```

Backend-тесты покрывают схему, фильтры, зависимости, повреждённые пакеты, SSRF,
редиректы, хеши, кэш, пакетную передачу, read-back, повторы и ручное подтверждение.
CI использует локальные фикстуры; живые источники проверяются отдельной явной командой.
Chromium проверяет реальные карточки, ручной режим, наборы и пакет из 10 тестовых
приложений. Дополнительно локально проверен набор 10 реальных дистрибутивов с передачей
на временный тестовый том и SHA-256 read-back. Это не тест аппаратной совместимости.

При проверке реальных SIS обнаружены и исправлены два дефекта анализатора:
`Length` — сжатый размер, `UncompressedLength` — размер данных для hash-проверки;
`EOpNull` не содержит payload и не должен извлекать файл с индексом 0. Основание —
[официальный sisfiledescription.h](https://github.com/SymbianSource/oss.FCL.sf.mw.appinstall/blob/master/secureswitools/swisistools/source/sisxlibrary/sisfiledescription.h).
Оба случая покрыты регрессионными тестами; проверки хешей и CRC не отключались.

## Verified Essentials (#40)

*Applications → Application kits → Verified Essentials* offers six profiles — **Communication,
Internet, Offline, Media, Files and tools, N95 Classic / FP1** — defined in
`catalog/essentials.json` as lists of *existing* catalog cards (no duplicated cards or API).
For the chosen model (E52, E72, N95, N95 8GB) every card is either **eligible** or **not offered**
with its reasons:

* eligible = a pinned, validated distribution exists (`delivery: automatic`) and the catalog plan
  finds no problem for that model; the item shows licence, author link, network need and the
  evidence levels `declared / model / hardware / installation`;
* not offered = manual-only or unavailable distribution (for example Opera Mini, FShell, PyS60),
  a model the card excludes, a profile that does not target the model (the N95 Classic profile is
  refused for E52/E72), or a catalog problem.

Eligibility is **static compatibility**: nothing is claimed as hardware-verified (`hardware:
not-tested`) or installed. The profile returns the dependency-aware copy/install order from the
catalog plan and can be saved as an ordinary collection, so the existing recovery transfer and its
guards are used unchanged (a transfer copies files; you install on the phone). A short "how to use it
in 2026" guide covers TLS, companion servers, services that no longer exist and the offline profile.
Documented verifiable profiles: FP1 (N95 Classic: X-plore, GPS Tracker, S2PuTTY) and FP2 (E52/E72
Files and tools: X-plore, IP calculator, password generator).
