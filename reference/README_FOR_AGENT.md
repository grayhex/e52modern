# E52 / CLEAR | Real S60 Theme Handoff

**Target:** Nokia E52, 240 × 320 portrait, S60 3rd Edition Feature Pack 2, Symbian 9.3.

## What's changed vs the previous concept
This version **uses the supplied original 240×320 screenshot as a pixel-locked geometry reference**. All labels, menu rows, icon positions, navigation and status areas, clock, softkeys, indicators are derived from the original. No widgets have been added. The new colors, highlights and wallpapers are design targets, **not yet a built `.sis` theme**.

The presentation compares `00_original_user_240x320.png` with `01_Standby_Light_240x320.png` and `01_Standby_Dark_240x320.png`. All three are exactly 240×320; 03_Compare_REAL_Layouts.png enlarges without interpolating the UI.

## Required scope, without pretending to mod the phone shell
1. In Carbide.ui Theme Edition for **S60v3 FP2** initialize a project and choose 240×320 portrait. Verify platform plugin version.
2. Set the real **Background** and **Areas** resources for main pane, status pane, control pane and active standby. Avoid introducing any new sections or redrawing menus as applications.
3. Configure **Highlights** for list focus/selected row, in shades of restrained blue. Theme supports focus graphics, not focus logic or selected-row layout.
4. Configure available **Colours** (dark on light or light on dark), across text, indicator glyphs and menu items. Check that each subsystem honors each color group on physical E52.
5. Configure **Pop-up windows**, list areas, sliders, input field backgrounds only where present in FP2 theme editor. Test all modes physically.
6. Optionally replace matching application icons using theme's icons mapping. These previews intentionally **keep the actual original shortcut and list icons**, not invented assets. If a real app icon is not mapped/supportable, the system icon persists. Maintain consistent fallback.
7. Package a project `.tdf` or editor-supported source format and theme `.sis` using Carbide/appropriate Symbian SDK tooling. **Do not invent precompiled `.skn` or `.mif` files.**

## What is impossible in a standard theme
- Move status panel, rename labels, change screen layout, reposition clock, change number of hotkeys, place big widgets, alter button positions
- Create new home screen cards or substitute a launcher without a separate installed application
- Change system font family/size by theme alone with guaranteed support across applications

## Real firmware-based references
- Official *Nokia E52 User Guide* (Issue 5.1), p.24: menu **3 columns × 4 rows**, not our previous fictional 3×3. Option `Change Menu view` switches grid/list. https://device.report/m/a36e38a350b98d9cb276d0b2b8dee79b5f38d6225c59743b076eee64765848b7.pdf
- Official E52 user guide p.31-32: separate `General`, `Menu view`, `Standby`, `Wallpaper`, etc. https://nokia-e52.helpdoc.net/en/nokia-e52-user-guide/personalisation/change-the-display-theme/
- **Verified original Nokia 2009 SkinCompiler `.pkg` source**: https://github.com/SymbianSource/oss.FCL.sftools.depl.swconfigmdw/blob/d2feb88baf0e94da760738fc3b436c3d5d1ff35f/configurationengine/source/plugins/symbian/ConeThemePlugin/themeplugin/tests/e75/test_pkg/themepackage.pkg — declares S60v3 compatibility via `[0x101f7961]`, scalable skins support `0x10207113`, and installs `.mbm`, `.mif`, `.skn` (with conditional `\resource\skins` / `\private\10207114\import` locations). Real checked **packaging source**, not an extracted working E52 binary.
- Original Nokia S60 Theme Studio Artist's Guide (documented TDF, TPF and SIS workflows and theme sections: Background, Areas, Icons, Highlights, Pop-ups, Colours). https://www.scribd.com/document/1052881516/S60-Theme-Studio-Artist-s-Guide-3-0
- Actual public documentation of installed S60 theme resource directory: `\private\10207114\import` and `\resource\skins`, with `.skn`, `.mbm`, `.mif` commonly used in a package. https://www.s40s60.dp.ua/docs/symbian-themes
- Carbide.ui v3.4/v4.3 and S60v3 FP2 plugin archive index: https://github.com/mrRosset/Symbian-Archive/blob/master/Themes.md
- A community full-workflow tutorial of Carbide UI 3.2.1 and categories: https://www.planete-smartphones.fr/forum/topic/20-tutorialcarbideui-s60-theme-edition-321/

## Important verification status
We inspected an actual original 2009 Nokia `themepackage.pkg` text file from the SymbianSource codebase, actual screen references, the official device/manual UI and documentation of the theme file format. **A genuine compiled E52 `.sis` was not downloaded/decompiled in this session**. Do not claim these designs have already been compiled, or that resource mapping to E52 firmware was validated. Before delivery, compare against an unpacked working third-party `.sis` and test the resulting theme on device. Do not assume that application-level icons, popups, or color groups are uniformly skinnable.

## Visual direction
LIGHT: off-white #F7F8F7, text #212B35, accent #4384CC, lines #CCD6E2.
DARK: graphite #171B23, text #DAE4ED, accent #2161A0, lines #505E6F.
Geometry and content never change. Wallpaper is intentionally quiet because active standby covers most of it.

## Acceptance criteria
- Compare 240×320 test screenshots exactly to original for fixed UI geometry.
- Validate text contrast, softkeys, selected row, battery/signal indicators, calendar rows, inbox, Options pop-up, Settings list and 3×4 grid menu on real E52.
- After theme activation, verify selected icons with every menu navigation direction, call notifications, and readability in daylight.
- Deliver editable project, exported icon/area assets, and installable package only after successful device test.
