# tools/s60 — сборка скинов (тем) S60 3rd Ed. под Linux

Набор инструментов для сборки тем S60 без Carbide.ui/Windows. Собран из
**открытых исходников Nokia/Symbian Foundation (EPL-1.0)** плюс два небольших
собственных скрипта. Используется конвейером `tools/build_theme.py`, но каждый
инструмент можно применять отдельно — для других тем и для разбора чужих файлов.

| Файл | Что делает | Происхождение |
|---|---|---|
| `build.sh` | собирает `bin/skc` и `bin/bmconv` (нужен только `g++`) | наш |
| `vendor/nokia-skin-compiler/` | **skc** — Nokia Skin Data Compiler: `skin.txt` → `.skn`, `.pkg`, список иконок | Nokia, без изменений |
| `vendor/bmconv/` | **bmconv**: BMP → `.mbm` (Symbian multi-bitmap) | Symbian Foundation, без изменений |
| `mifbuild.py` | замена `mifconv` для растровых скинов: список от `skc` → `.mif` + `.mbm` | наш, формат восстановлен по исходникам ридера Nokia |
| `s60inspect.py` | независимая проверка `.skn/.mbm/.mif` | наш |
| `vendor/NOTICE.md` | источники и коммиты вендорных файлов | — |

## Быстрый старт

```bash
tools/s60/build.sh                 # один раз: собрать skc и bmconv
python3 tools/build_theme.py       # PNG -> skin.txt -> .skn/.mbm/.mif/.pkg -> проверка
python3 tools/s60/s60inspect.py theme/dist/light/e52clearlight
```

## Отдельные шаги вручную

```bash
cd my_skin/                                    # skin.txt + gfx/*.bmp (BITMAPPATH gfx/)
mkdir out
../tools/s60/bin/skc -mout/ -tout/ skin.txt myskin     # -> out/myskin.skn, out/myskin.pkg, out/myskin_MIFList.txt
python3 ../tools/s60/mifbuild.py out/myskin_MIFList.txt out/myskin --srcdir .   # -> out/myskin.mif, out/myskin.mbm
python3 ../tools/s60/s60inspect.py out/myskin
```

Синтаксис `skin.txt` — см. примеры Nokia (`haze.txt`, `jing.txt`,
`scalableseries60skin.txt` в `SymbianSource/oss.FCL.sf.mw.uiresources`,
каталог `skins/AknSkinContent/srcdata`) и сгенерированный `theme/src/*/skin.txt`.
Идентификаторы (`QsnBgScreen`, `QsnFrList`, …) и индексы цветов описаны в
`vendor/nokia-skin-compiler/include/aknsconstants.hrh` (в оригинале
`AknsConstants.h/.hrh`).

## Как устроены файлы

* **`.skn`** — бинарное описание скина (цепочка блоков `длина/тип/версия`), пишет `skc`.
  Иконки адресуются идентификаторами от **16384**: элемент `2k` — растр, `2k+1` — маска.
* **`.mbm`** — набор растров (UID `0x10000037/0x10000042`), пишет `bmconv`.
  Цвет `c16` (RGB565) + 8-битная маска «soft».
* **`.mif`** (v2) — 16-байтный заголовок `{0x34232342, 2, 16, N}` и таблица `N × {offset, length}`.
  `offset ≤ 0` ⇒ иконка лежит в `.mbm` под индексом `-offset`; `offset > 0` ⇒ SVG-T внутри самого `.mif`.
  Формат восстановлен по `AknIconLoader.cpp`, `AknIconLocationInfo.cpp`, `MifHandler.h`,
  `mifconvdefs.h` (там же `EIconFormatBMP = 0`, `KMifIdFirst = 16384`).
* **`.pkg`** — манифест для `makesis` (пишет `skc`).

## Что проверено, а что нет

Проверено на этой машине:
* `skc` и `bmconv` собираются из исходников и работают; `bmconv` выдаёт корректный `.mbm`
  (UID, контрольная сумма, trailer, заголовки растров).
* Независимый `s60inspect.py`: длина `.skn` равна размеру файла, имена `.mbm/.mif` внутри `.skn`,
  каждый индекс `.mif` указывает на существующий растр `.mbm`, все растры задействованы;
  все идентификаторы иконок в `.skn` попадают в диапазон `.mif`.

**Не проверено (и без телефона проверить нельзя):**
* что E52 принимает такой `.skn/.mif/.mbm` и корректно рисует тему;
* побайтовое совпадение с `mifconv` от Nokia (формат `.mif` для растров выведен из кода
  ридера; запись на стороне `mifconv` не видна);
* `.skn` из `skc` на Linux побайтово не совпадает с эталонным `haze.skn` из репозитория Nokia
  (другая сборка/PID/метки времени) — структурно сравнивался только размер заголовка.

## Ограничения

* Нет SVG: `mifbuild.py` отказывается упаковывать `.svg` (нужен SVG-T энкодер, его в открытом виде нет).
  Все графики — растровые BMP; маски — `<имя>_mask_soft.bmp`.
* **Нет `makesis`/`signsis`.** Открытой реализации для SIS 9.x найти не удалось.
  Из `.pkg` пакет собирается инструментами Symbian SDK / Carbide (Windows):
  ```
  makesis e52clearlight.pkg
  signsis e52clearlight.sis e52clearlight.sisx cert.cer key.key     # или createsis create ...
  ```
  UID тем — из тестового диапазона `0xE0000000+`. Для публикации нужен собственный UID
  (Symbian Signed), иначе возможны конфликты с чужими пакетами.

## Использование для других задач

* `bmconv` — любые `.mbm` (иконки, рисунки приложений): `bin/bmconv out.mbm -c16/abs/a.bmp -8/abs/a_mask.bmp`
  (путь после ключа — абсолютный или `./…`, иначе имя на `a` путается с `-c32a`).
* `s60inspect.py` — быстрая диагностика чужих тем, если рядом лежат `.skn/.mbm/.mif` с одним именем.
* `skc` понимает и другие типы скинов; для классических (не scalable) он в этой версии
  требует индексы < 16384 и не используется.
