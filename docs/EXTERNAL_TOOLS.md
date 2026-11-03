# Внешние инструменты: аудит (2026-11-03)

Что проверено чтением исходников/документации. Инструменты **установлены и запущены** только там,
где это указано явно; остальное — результат чтения кода и README.

## symbian-platform — https://github.com/hpnkv/symbian-platform
* Версия **0.3.0** (PyPI, 2026-10-08), лицензия **Apache-2.0** (сторонние части и интеграция
  эмулятора — GPL/EPL по месту). Python 3.11–3.14, Linux glibc ≥ 2.28 / macOS 15+; нативные
  SDK-архивы для Linux требуют glibc ≥ 2.39.
* Есть: Clang/LLD ARMv5T/ARMv6, конвертация ELF→E32, пакет C++ runtime, CMake/Ninja, `symbian inspect
  --format {elf32,e32,sis}`, `symbian build/package/signing`, `symbian device list/info/install --package`,
  `symbian emulator ...` (диспоузные сессии), USB/MTP.
* **Ограничения SIS-писателя** (из `doc/docs/guides/packaging.md` и `cpp/symbian/sis/sis.cc`): только
  EKA2-исполняемые файлы (`!:\sys\bin\*.exe`, до 16 MiB) и вспомогательные ресурсы приложения;
  **DLL как основной payload, произвольные установочные скрипты, зависимости, встроенные пакеты, обновления
  и EKA1 SIS не поддерживаются**; UID пакета — только 0xE0000000..0xEFFFFFFF. Следовательно, `symbian package`
  **не может** упаковать `.skn/.mbm/.mif/.pkg` темы.
* В документации **нет** упоминания «E52», «S60 3rd FP2», «Legacy EKA2»: описаны ARMv5T/ARMv6, «ARMv5T older EKA2»
  (проверенные образцы прошивок: E71/RM-346 и 6120c/RM-243 — это другие телефоны), отдельный EKA1-профиль.
  Совместимость с E52 этим проектом не заявлена. Установка `symbian-platform` и его нативного SDK
  **в среде разработки этого репозитория не выполнялась**; интеграция проверена только на поддельном `symbian`.
* Подпись: `symbian signing create/sign` — RSA/X.509, только для пакетов его собственного профиля.
  Подпись не даёт доверия телефона.

## EKA2L1 — https://github.com/EKA2L1/EKA2L1
* Лицензия **GPL-3.0**. Сборки для Windows/macOS/Linux/Android через GitHub Actions, релиз «continous».
  Заявленный охват: «S60v1 … Symbian Belle», «ограниченное подмножество приложений».
* README **не описывает** автоматизируемый CLI, поэтому SymPort не предполагает флагов: команда запуска
  задаётся в `symport.toml`. Загрузка прошивки/ROM — на стороне пользователя.
* Не запускался.

## SymbianSource — https://github.com/SymbianSource
* Исходники Nokia/Symbian Foundation под EPL-1.0. Используются (вендорены без изменений в `tools/s60/vendor`):
  Skin Data Compiler (`oss.FCL.sf.mw.uiresources`), `bmconv` (`oss.FCL.sf.os.graphics`).
* В открытых репозиториях **не найдены** исходники `makesis`/`signsis`/`createsis` (в `oss.FCL.sf.os.buildtools`
  есть только `sisutils` для `sis2iby`). `elf2e32` и `petran` присутствуют в `oss.FCL.sf.os.buildtools` (`toolsandutils/e32tools`);
  `rcomp` там не найден. Не интегрировались и не собирались — для сборки приложений используется `symbian-platform`.
* Формат MIF-индекса восстановлен по ридеру `uigraphics/AknIcon` (см. `tools/s60/README.md`).

## Symbian-Archive — https://github.com/mrRosset/Symbian-Archive
* Индекс ссылок (MEGA) на Carbide.ui Theme Edition 3.4/4.3, плагины платформ, формат MBM
  (http://fileformats.archiveteam.org/wiki/EPOC_MBM). **Формата SKN/MIF/SIS и открытого компилятора там нет.**

## Альтернативные упаковщики SIS
| Инструмент | Результат проверки |
|---|---|
| Официальный MakeSIS/SignSIS/CreateSIS (Symbian SDK, Carbide) | Единственный полноценный путь для `.pkg` тем; Windows-инструменты (под Linux — Wine). Адаптер реализован, в этой среде **недоступен**. |
| Ensymble 0.29 (Python 2, GPL; `simplesis`, `signsis`) | Существует (Debian/Ubuntu), Python 3-портов не найдено; семантика размещения произвольных файлов не проверена, не интегрирован. |
| gnupoc-makesis | Линуксовый makesis для старых форматов SIS (до 9.x); для E52 непригоден. |
| libsis (C++) | Только парсер SIS 9; не запускался. |
| Собственный `symport.sis.writer` | Экспериментальный; формат — по эталонной реализации symbian-platform. Не проверен MakeSIS и телефоном. |

## Другие инструменты
`elf2e32`, `rcomp`, `mifconv`: оригиналы — часть Symbian SDK (Windows). Для `mifconv` в открытом виде
найден только ридер MIF; SVG-T энкодера нет, поэтому `mifbuild.py` поддерживает только растры.
