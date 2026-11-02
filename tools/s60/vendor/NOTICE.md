# Vendored third-party sources

Оригинальные исходники Nokia/Symbian Foundation под **Eclipse Public License v1.0**
(заголовки лицензии сохранены в каждом файле). Файлы не изменялись; все правки
под Linux применяются при сборке скриптом `tools/s60/build.sh`.

| Каталог | Источник | Коммит |
|---|---|---|
| `nokia-skin-compiler/sdcsrc`, `sdcinc` | https://github.com/SymbianSource/oss.FCL.sf.mw.uiresources `skins/AknSkins/sdcsrc`, `sdcinc` (Nokia Skin Data Compiler, `AknSkinDescCompiler`) | `b78660bec78835802edd6575b96897d4aba58376` |
| `nokia-skin-compiler/include/aknsconstants.hrh` | то же, `uiresources_pub/skins_api/inc/AknsConstants.hrh` (копия в нижнем регистре: так её подключает исходник) | `b78660bec78835802edd6575b96897d4aba58376` |
| `bmconv/` | https://github.com/SymbianSource/oss.FCL.sf.os.graphics `graphicstools/gdi_tools/bmconv` (Symbian `bmconv`, .mbm) | `ff133bc50e6158bfb08cc093b0f0055321dcde99` |

Текст лицензии: https://www.eclipse.org/legal/epl-v10.html
