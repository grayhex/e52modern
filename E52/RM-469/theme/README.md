# E52 / CLEAR — тема для Nokia E52 (S60 3rd Ed. FP2, 240×320)

## Статус — читать первым

Теперь в репозитории есть **собранные файлы скина** (`theme/dist/<light|dark>/`: `.skn`, `.mbm`, `.mif`, `.pkg`).
Они получены настоящим компилятором Nokia (Skin Data Compiler) и `bmconv` из открытых исходников,
а структура проверена независимым скриптом. Но:

* **на реальном E52 ничего не проверялось** — работоспособность темы не подтверждена;
* **`.sis` не собран**: нет открытых `makesis`/`signsis` для SIS 9.x. Пакет собирается из готового
  `.pkg` инструментами Symbian SDK (см. «Сборка `.sis`»);
* тема переопределяет только фон, рамки (подсветка списка и меню, popup, поле ввода) и цветовые таблицы.
  Остальное (иконки, вкладки, статус-панель, шкалы) берётся из системной темы телефона, поэтому
  в приложениях с «бумажным» фоном (Заметки, Калькулятор) и в тёмном варианте возможны
  нестыковки цветов — их надо смотреть на устройстве.

Геометрия и содержимое экрана не меняются (тема не двигает виджеты, не меняет шрифт и раскладку).

## Что внутри

| Путь | Назначение |
|---|---|
| `theme/dist/<variant>/` | готовые `.skn/.mbm/.mif/.pkg` для `makesis` |
| `theme/src/<variant>/` | исходник скина: `skin.txt` и `gfx/*.bmp` (генерируется) |
| `theme/assets/<variant>/` | PNG-ресурсы (фон, рамки, popup и т.д.) |
| `theme/manifest.json`, `theme/colours.json` | размеры/поля 9-slice, палитры и контраст WCAG |
| `theme/preview/` | схематичные превью (не скриншоты телефона) |
| `tools/build_assets.py` → `tools/gen_skin.py` → `tools/build_theme.py` | цепочка сборки |
| `tools/s60/` | инструменты Symbian под Linux, см. `tools/s60/README.md` |
| `reference/` | исходный скриншот, макеты и задание из архива |

## Что именно задаёт тема

| Ресурс | Элемент скина | Источник |
|---|---|---|
| фон 240×320 | `QsnBgScreen`, `QsnBgScreenIdle` | `background.png` |
| подсветка списка | `QsnFrList` | `list_highlight.png` |
| подсветка меню 3×4 | `QsnFrGrid` | `grid_highlight.png` |
| popup / подменю | `QsnFrPopup`, `QsnFrPopupSub` | `popup.png` |
| поле ввода | `QsnFrInput` | `input_field.png` |
| цвета | `QsnTextColors`, `QsnIconColors`, `QsnLineColors`, `QsnOtherColors`, `QsnHighlightColors`, `QsnComponentColors` | `gen_skin.py` (роли по `AknsConstants.h`) |

Не используются (остаются системными): `statuspane`, `controlpane`, `list_item_bg`, `tab_*`,
`shortcut_button`, `scroll_*` — их PNG лежат в `assets/` для дальнейшей работы.

## Пересборка

```bash
tools/s60/build.sh            # один раз: собрать skc и bmconv (нужен g++)
python3 tools/build_theme.py  # обе темы; результат — theme/dist/
# то же через SymPort, с проверками:
symport theme build && symport theme inspect
```

Подробнее: [`docs/THEME.md`](../docs/THEME.md), [`docs/PACKAGING.md`](../docs/PACKAGING.md), чек-лист проверки на телефоне — [`docs/DEVICE_TEST.md`](../docs/DEVICE_TEST.md).

## Сборка `.sis`

Через SymPort: `symport theme package --variant light` (официальный `makesis`/`signsis`; без них команда честно сообщает
«unsupported») или `--backend native` — экспериментальный неподписанный писатель без зависимостей, не проверенный
MakeSIS и телефоном. Подробности — [`docs/PACKAGING.md`](../docs/PACKAGING.md). Ручной вариант:

Из каталога `theme/dist/<variant>/` на машине с Symbian SDK / Carbide:

```
makesis e52clearlight.pkg
signsis e52clearlight.sis e52clearlight.sisx cert.cer key.key
```

Подпись нужна E52 (self-signed или Open Signed). UID тем — из тестового диапазона `0xE0E52C01/02`.
Перед установкой убедитесь, что знаете, как вернуть стандартную тему (Меню → Параметры → Оформление/Темы).

## Проверка на телефоне (чек-лист)

* Тема появляется в списке и применяется; после перезагрузки телефон стартует нормально.
* Фон, подсветка списка, меню 3×4, popup «Параметры», поле ввода, софт-клавиши, индикаторы.
* Читаемость текста в Заметках, Календаре, Калькуляторе, Сообщениях (особенно тёмный вариант).
* Входящий вызов, поворот навигации во все стороны, читаемость на солнце.
* Удаление темы возвращает стандартную.

Результаты проверки (что работает, что нет) — в issues/PR: от них зависит следующая итерация.
