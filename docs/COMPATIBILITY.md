# Проверка бинарной совместимости

```bash
symport app analyze ./hello.exe --target nokia-e52 [--firmware-profile my-e52-fw.json]
symport app analyze ./hello                      # проект: конфигурация + собранный E32
symport sis inspect ./hello.sis --target nokia-e52
```

Разбираются: тип файла (E32 / SIS / ELF), UID и контрольные суммы, CRC заголовка, ядро (EKA1/EKA2), CPU
(ARMv4/5/6), ABI, формат заголовка и импортов, секции, secure ID, capabilities, **импортируемые DLL и ординалы**
(для несжатых образов), UID-диапазон. В SIS — файлы, SHA-1, подпись (наличие), число зависимостей, встроенные E32.

## Вердикты

| Статус | Когда |
|---|---|
| `incompatible` | факт противоречит профилю: ядро EKA1, CPU новее ABI профиля, повреждён заголовок, импорт отсутствует в пользовательском firmware-профиле |
| `compatible` | **только** при firmware-профиле, где нашлись все импортируемые DLL (и ординалы, если таблицы заданы) и сошлись статические факты; `runtime: not-tested` |
| `unknown` | не хватает данных (чаще всего: нет firmware-профиля, сжатый образ) |
| `not-tested` | нечего оценивать (проект не собран, ресурсный пакет вроде темы) |

Отсутствие данных не превращается в совместимость. `capabilities`, не выдаваемые пользователем при установке
(например `AllFiles`), выводятся предупреждением: им нужен сертификат, которому доверяет телефон.

## Firmware-профиль

SymPort не содержит ROM/прошивок. Для проверки импортов нужен профиль, составленный из **вашего** дампа
прошивки (формат — `docs/firmware-profile.md`). Без него требования к ROM-данным не обходятся.

## Независимая сверка (`--cross-check`)

```bash
symport app inspect ./hello.exe --cross-check      # если установлен symbian-platform
```

Сравнивает 14–15 полей разбора E32 (UID, флаги, ядро, архитектура, размеры, CRC заголовка, capabilities, число DLL импорта)
с `symbian inspect --format e32` — независимой нативной реализацией. Расхождение — ошибка (код 1); если инспектор SDK не
поддерживает профиль образа, результат `unknown`, не «совпало». Совпадение подтверждает чтение заголовка, а не принятие
образа прошивкой.

## Ограничения

Сжатые образы (deflate/bytepair) — только заголовки; импорты, ресурсы приложения (`.rsc`), зависимости
от версии ОС и доступность API/DLL не определяются без firmware-профиля; формат EKA1 распознаётся и
отклоняется для E52, но не разбирается. Парсинг проверен на синтетических образах; сопоставление
с образцами реальных прошивок и сборок SDK не выполнялось.

## Nokia N95 / N95 8GB (FP1)

Обе модели — Symbian 9.2 / S60 3rd FP1, 240×320. Inspector различает FP1 UID
`0x102032BE` и FP2 `0x102752AE`: FP2-only блокируется на N95. Неизвестный product UID,
неизвестный ABI и непривязанные к прошивке версии product-пакетов остаются неизвестными.
Прошивочный профиль должен совпасть с моделью и точной версией. Каталог хранит отдельные
результаты по моделям и платформам, сохраняя старые E52-поля. Проверка пакета и передача
не подтверждают установку. Подробнее: [N95, источники и аппаратный чек-лист](NOKIA_N95.md).

## N97 mini / S60 5th

Цель `nokia-n97-mini`: Symbian 9.4, UID `0x1028315F`, 360×640 / 640×360.
Она не принимает S60 3rd/FP1/FP2-only prerequisites автоматически. Неизвестные версии product
UID, DLL/ординалы без точного пользовательского firmware-профиля остаются неизвестными.
Результаты E52/E72/N95 не переносятся на mini. `N97` и RM без верифицированной карты не
выбирают mini. Темы S60 5th блокируются в Theme Studio/backend/worker; общий анализ
пользовательского SIS остаётся доступен. [Подробности и ограничения](NOKIA_N97_MINI.md).

## N8 / E7: ОС определяется отдельно

Семейство Symbian^3 (`0x20022E6D`) не означает установленную Belle. При неизвестной ОС Belle-only
UID `0x2003A678` получает `unknown`; при явной Belle/Belle Refresh — статическое совпадение;
Anna не принимается за Belle. S60v3/5th-only требования не одобряются автоматически. Qt и DLL
требуют отдельного подтверждения, E52/N95 evidence не наследуется. ARMv6 остаётся непроверенным
ABI вместо общего отказа S60v3. [Источники, ограничения и проверка](NOKIA_N8_E7.md).

## Nokia 7610: S60 2nd Edition is assessed separately

`nokia-7610` is a target of compatibility, Inspector and dependency analysis, but its platform (S60 2nd Edition,
Symbian OS 7.0s, a legacy SIS format and probably EKA1) is **not assessed**: no S60 2nd Edition platform UID or
binary rule is shipped, and the S60 3rd/5th and Symbian 9.x rules are not applied to it. Consequently the catalog
reports `not-tested` (or `unsupported` where a declared minimum OS excludes it), package analysis reports at best
`unresolved` (issue `legacy-platform-not-assessed`; packages that declare S60 3rd/5th remain a known mismatch), and
the Inspector result stays `unknown`. EKA1 or ARMv6 binaries are neither accepted nor rejected on this target
(`binary-abi-unknown`). A result is never `compatible` or `satisfied`. See [NOKIA_7610.md](NOKIA_7610.md).
