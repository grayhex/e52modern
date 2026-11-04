# Проверенные источники App Catalog

Проверка источников и дистрибутивов: **2026-11-03** (X-plore и Jellyfin for S60 — **2026-11-04**). Это не проверка на телефоне.

| Приложение | Версия | Получение | Источник |
|---|---|---|---|
| AIKON | 0.18.4 | Автоматически | [Источник](https://github.com/emir/AIKON/releases/tag/v0.18.4) |
| BlueWAP | 1.5.0 | Автоматически | [Источник](https://github.com/gtrxAC/BlueWAP/releases/tag/v1.5) |
| Brainfuck Editor | 0.3.1 | Вручную у автора | [Источник](https://github.com/shinovon/BrainfuckJ2ME/releases/tag/0.3.2) |
| Celeste Classic J2ME | 1.0 | Автоматически | [Источник](https://github.com/r58Playz/celeste-j2me/releases/tag/v1.0) |
| ExportRMS | 1.0.0 | Вручную у автора | [Источник](https://github.com/shinovon/ExportRMS/releases/tag/v2.1.0) |
| FPlay J2ME | 1.0.64 | Автоматически | [Источник](https://github.com/carlosrafaelgn/FPlayJ2ME) |
| 2048 J2ME | 1.1 | Вручную у автора | [Источник](https://github.com/turbanoff/j2me-2048/releases/tag/1.0) |
| GitHub J2ME | 0.9.9 | Автоматически | [Источник](https://github.com/shinovon/GitHub-j2me/releases/tag/v0.9.9) |
| S60 GPS Tracker | 1.4.0 | Автоматически | [Источник](https://github.com/artem78/s60-gps-tracker/releases/tag/v1.4.0) |
| GPSTest | 1.0.1 | Вручную у автора | [Источник](https://github.com/shinovon/GPSTest/releases/tag/v1.0.1) |
| Hotpants OTP | 2.0 | Автоматически | [Источник](https://github.com/baumschubser/hotpants/releases/tag/2.0) |
| J2ME HTTP Server | 1.0.2 | Автоматически | [Источник](https://github.com/shinovon/j2me-http-server/releases/tag/v1.0.2) |
| IP Calculator | 1.0 | Автоматически | [Источник](https://github.com/developer-kaczmarek/J2ME-IpCalculator/releases/tag/v1.0.0-t9) |
| jtReversi | 0.87.00 | Автоматически | [Источник](https://github.com/asalamon74/jtreversi) |
| MahoLichki | 1.1.5 | Вручную у автора | [Источник](https://github.com/shinovon/MahoLichki/releases/tag/v1.1.5) |
| MahoMaps | 1.2.4 | Автоматически | [Источник](https://github.com/mahomaps/mm-v1/releases/tag/1.2.4) |
| MahoRasp | 1.1.1 | Вручную у автора | [Источник](https://github.com/shinovon/MahoRasp/releases/tag/v1.1.1) |
| MapNav | 4.8.18 | Вручную у автора | [Источник](https://github.com/magdel/MapNav/releases/tag/4.8.18) |
| MD5 Benchmark | 2.0.0 | Вручную у автора | [Источник](https://github.com/shinovon/MD5BenchmarkJ2ME/releases/tag/2.0.0) |
| MDReader | 0.2.0 | Автоматически | [Источник](https://github.com/Hinduc0der/mdreader-j2me) |
| MeshCore J2ME | 1.0 | Автоматически | [Источник](https://github.com/dobrishinov/MeshCore-J2ME/releases/tag/v1.0.0) |
| Jellyfin for S60 (English / Русский) | 0.3.22 | Автоматически | [Источник](https://github.com/Hinduc0der/jellyfin-s60v3/releases/tag/v0.3.22) |
| MPGram | 1.6.6 | Вручную у автора | [Источник](https://nnproject.cc/mp) |
| nmania | 2.7.0 | Автоматически | [Источник](https://github.com/Feodor0090/nmania/releases/tag/2.7.0) |
| PassGen | 1.0.0 | Автоматически | [Источник](https://github.com/scadl/PassGen-J2ME/releases/tag/1.0) |
| Python for S60 | 1.4.5 | Вручную у автора | [Источник](https://sourceforge.net/projects/pys60/files/pys60/1.4.5/PythonForS60_1_4_5_3rdEd.sis/download) |
| PuTTY for Symbian | 1.6.1 | Автоматически | [Источник](https://github.com/shinovon/s2putty/releases/tag/v1.6.1) |
| S60Maps | 1.26 | Вручную у автора | [Источник](https://github.com/artem78/s60-maps/releases/tag/v1.26) |
| ScummVM S60v3 | 1.7.0 | Вручную у автора | [Источник](https://downloads.scummvm.org/frs/scummvm/1.7.0/scummvm-1.7.0-s60v3.zip) |
| VK4ME | 3.3.4 | Автоматически | [Источник](https://github.com/VK4ME/client/releases/tag/3.3.4) |
| X-plore (S60 3rd) | 1.64 | Автоматически | [Источник](https://www.lonelycatgames.com/apps/xplore-symbian) |
| W4ME Station | 1.1.0 | Автоматически | [Источник](https://github.com/mulfyx/w4me-station/releases/tag/v1.1.0) |

21 автоматическая (Jellyfin — два языковых варианта) и 12 ручных позиций. Все артефакты имеют измеренные размер и SHA-256 в `sources.json`.
Скрипт `python tools/verify_app_catalog.py --download` повторяет безопасную проверку автоматической части и кэша.
Для ручных ZIP MapNav/ScummVM проверены вложенные пакеты; PyS60 и MPGram также проверены локально, но не включены в автоматическую выдачу.

Неподтверждённые/отклонённые кандидаты: `research.json`. Формат записи: `schema.json`.
Условия, подробности проверки и ограничения: [APP_CATALOG.md](../docs/APP_CATALOG.md).
