# Упаковка и подпись SIS (S60 3rd FP2)

```bash
symport theme package --variant light                       # auto: официальный makesis, иначе «unsupported»
symport theme package --variant light --backend makesis --cert c.pem --key k.pem   # makesis + signsis
symport theme package --variant light --backend native     # экспериментальный неподписанный писатель
```

Результат — `build/symport/theme/<variant>/<имя>.sis` (`.sisx` после подписи), отчёт JSON, SHA-256.
Перед упаковкой выполняется `theme inspect`; после — независимое чтение SIS собственным читателем и сверка
с `.pkg` (файлы, пути, SHA-1 содержимого).

## Backend'ы

| Backend | Файлы | Зависимости пакета | Подпись | Статус |
|---|---|---|---|---|
| `makesis` (+`signsis`) | любые, полный синтаксис `.pkg` | да | через `signsis` | официальный; **в среде разработки не запускался** (нет инструмента) — проверен на поддельном |
| `native` | любые | **нет** (платформенные и пакетные зависимости не кодируются; предупреждения в отчёте) | **нет** | **экспериментальный**; формат по эталонной реализации symbian-platform; не принят MakeSIS и телефоном |
| `modern-sdk` | только E32-исполняемые | нет | приложения | **не может упаковать тему** — команда сообщает `unsupported` |

`auto` выбирает `makesis`, если он найден; иначе завершается кодом 3 с инструкцией. Он **никогда** не переключается
молча на `native`.

## Подключение официальных инструментов

```bash
export SYMPORT_MAKESIS=/path/to/makesis            # или 'wine /path/to/makesis.exe'
export SYMPORT_SIGNSIS=/path/to/signsis
export SYMPORT_SIGN_PASSPHRASE=...                 # если ключ зашифрован; в отчётах и логах не печатается
```

## Проверка `.pkg` темы

Генерируется Nokia Skin Compiler. Платформа: `[0x101f7961]` (Series60v3.0, нужна для E52), `[0x1028315F]`
(S60 5.x, безвредна); зависимости `(0xA00000EB)` Series60SkinsSupport и `(0x10207113)` ScalableSkinsSupport;
установка: `.mbm`, `.mif` → `!:\resource\skins\<uid>\`, `.skn` → `!:\private\10207114\import\<uid>\`.

## UID

UID тем — из тестового диапазона `0xE0E52C01/02`: общий для всех экспериментов диапазон, годится для
собственных проверок и self-signed установки, **не для публикации**. Защищённый диапазон (`0x0…`–`0x7…`)
требует выдачи UID через Symbian Signed. Для публикации выберите случайный UID и поменяйте его в
`tools/gen_skin.py` (`VARIANTS`).

## Подпись и её пределы

* Подпись не даёт пакету доверия телефона и не выдаёт capabilities. Политика установки неподписанных/self-signed
  пакетов на конкретном E52 **не проверена** (в профиле: `packaging.signing_policy = unknown`).
* `symbian signing sign` из symbian-platform подписывает только пакеты своего профиля (приложения) — не тему.
* SymPort не проверяет криптографическую корректность подписи; он только фиксирует наличие цепочки.
* Ключи и сертификаты держите вне репозитория. В CI приватные ключи не используются.
