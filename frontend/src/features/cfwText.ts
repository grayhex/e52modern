/** Russian wording for the English metadata published with the firmware sources and advisories. */
const RU: Record<string, string> = {
  'Symbian Belle Refresh (author claim)': 'Symbian Belle Refresh (заявлено автором)',
  'N8 v20260912; E7 v20260308 (author)': 'N8 v20260912; E7 v20260308 (автор)',
  'release labels, not a stock firmware version': 'метки релизов, не номер штатной прошивки',
  'N8 release label v20260912 and E7 v20260308 were read on the author page on 2026-11-06; exact stock firmware/RM/product code is not stated.':
    'На странице автора 06.11.2026 указаны релизы N8 v20260912 и E7 v20260308; точная штатная прошивка, RM и код продукта не указаны.',
  'E7 has three separate hardware keyboard choices: Euro1GenericWorld, Turkish, Russian. UI languages vary by build; inspect the selected download manually.':
    'У E7 три отдельных варианта аппаратной клавиатуры: Euro1GenericWorld, турецкая и русская. Языки интерфейса зависят от сборки; проверьте выбранный пакет вручную.',
  'Author claims do not establish a safe update, complete rollback or compatibility with the connected device.':
    'Заявления автора не подтверждают безопасное обновление, полный откат или совместимость с подключённым устройством.',
  'Author page requires browser verification; exact release, RM, languages and keyboard variant are unknown. Obtain a package and author evidence manually.':
    'Страница автора требует проверки браузера; точные релиз, RM, языки и раскладка не подтверждены. Получите пакет и сведения автора вручную.',
  'hybrid mod kit installed on the phone (SIS); not a flash':
    'гибридный набор модификаций, устанавливается на телефон (SIS); не прошивка',
  'custom firmware for Symbian Belle devices': 'кастомная прошивка для устройств Symbian Belle',
  'not stated': 'не указано',
  'not stated by the author': 'автор не указал',
  'per model (see the advisory)': 'по моделям (см. уведомление)',
  'unconfirmed (no redistribution permission on the author’s pages)':
    'не подтверждено (на страницах автора нет разрешения на распространение)',
  "unconfirmed (no redistribution permission on the author's pages)":
    'не подтверждено (на страницах автора нет разрешения на распространение)',
  'Alpha, one author, hobby project.': 'Альфа-версия, один автор, любительский проект.',
  'Needs the installserver.exe patch beforehand.': 'Заранее нужен патч installserver.exe.',
  'No uninstall procedure; formatting the phone erases data.':
    'Процедуры удаления нет; форматирование телефона стирает данные.',
  'Belle only: not applicable to S60 3rd/5th Edition phones.':
    'Только Belle: к телефонам S60 3rd/5th Edition не относится.',
  'The Online Services Bridge repository is a set of controlled URL redirects (web configuration), not the source of the firmware.':
    'Репозиторий Online Services Bridge — набор управляемых переадресаций URL (веб-конфигурация), а не источник прошивки.',
  'A published advisory describes a startup-script mechanism: see CVE-2025-65885.':
    'Опубликовано уведомление о механизме стартовых скриптов: см. CVE-2025-65885.',
  'Only the author’s published metadata. SymPort ships, downloads and redistributes none of these files; import what you obtained from the author yourself. Fields the source does not state say so.':
    'Только опубликованные автором сведения. SymPort не поставляет, не скачивает и не распространяет эти файлы: импортируйте то, что вы получили у автора сами. Если источник чего-то не указывает, это так и отмечено.',
  "Only the author's published metadata. SymPort ships, downloads and redistributes none of these files; import what you obtained from the author yourself. Fields the source does not state say so.":
    'Только опубликованные автором сведения. SymPort не поставляет, не скачивает и не распространяет эти файлы: импортируйте то, что вы получили у автора сами. Если источник чего-то не указывает, это так и отмечено.',
  'Symbian Belle custom firmware. Not S60 3rd Edition: this does not describe the E52, E72 or N95.':
    'Кастомная прошивка Symbian Belle. Не S60 3rd Edition: к E52, E72 и N95 это не относится.',
  'Delight CFW: startup scripts injected through a text file in the Data directory':
    'Delight CFW: стартовые скрипты через текстовый файл в каталоге Data',
  'The researcher’s write-up calls it critical; that wording is the author’s, not the scored severity.':
    'В разборе исследователя уязвимость названа критической; это оценка автора, а не рассчитанная серьёзность.',
  "The researcher's write-up calls it critical; that wording is the author's, not the scored severity.":
    'В разборе исследователя уязвимость названа критической; это оценка автора, а не рассчитанная серьёзность.',
  'CVE JSON record (MITRE)': 'Запись CVE в JSON (MITRE)',
  'CVE.org record': 'Запись на CVE.org',
  'Researcher write-up (author’s claims, not verified by SymPort)':
    'Разбор исследователя (утверждения автора, SymPort их не проверял)',
  "Researcher write-up (author's claims, not verified by SymPort)":
    'Разбор исследователя (утверждения автора, SymPort их не проверял)',
  supported: 'поддерживается',
  'supported (read-only, v1)': 'поддерживается (только чтение, v1)',
  'experimental core ROM reader': 'экспериментальное чтение core ROM',
  'not decoded: no verified specification or sample; never assumed compatible':
    'не декодируется: нет проверенной спецификации или образца; совместимость не предполагается',
};
const LINKS: Record<string, [string, string]> = {
  author: ['author', 'автор'],
  index: ['index', 'каталог автора'],
  services_bridge: ['services bridge', 'мост сервисов'],
};
export const translate = (lang: string, text: string) =>
  lang === 'ru' ? (RU[text] ?? text) : text;
export const linkLabel = (lang: string, key: string) =>
  (LINKS[key] ?? [key, key])[lang === 'ru' ? 1 : 0];
