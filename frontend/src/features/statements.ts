/** Russian wording for the fixed explanations that the server sends in English only. */
const RU: Record<string, string> = {
  'A snapshot holds only what SymPort could read over this connection. It cannot restore the phone: an SD-card copy never restores firmware or phone memory, and system firmware cannot be backed up by SymPort.':
    'Снимок содержит только то, что SymPort смог прочитать по этому подключению. Он не восстанавливает телефон: копия карты памяти не возвращает прошивку и память телефона, а системную прошивку SymPort сохранить не может.',
  'Not a backup of the phone: only the stores listed as exported, as read through the driver (completeness is not verified). It cannot restore firmware, applications or system databases and promises nothing after a CFW installation.':
    'Это не резервная копия телефона: только перечисленные хранилища, как их прочитал драйвер (полнота не проверяется). Копия не восстановит прошивку, приложения и системные базы и ничего не обещает после установки CFW.',
  'Preview only: nothing was written. A restore writes one store at a time and is verified by reading it back.':
    'Только предпросмотр: ничего не записано. Восстановление пишет по одному хранилищу и проверяется чтением.',
  'Restored and read back.': 'Восстановлено и проверено чтением.',
  'The write could not be verified by reading back; read the phone again before another attempt.':
    'Запись не удалось проверить чтением; перечитайте телефон перед новой попыткой.',
  'SymPort cannot remove an add-on or restore a system DLL after its SIS is gone.':
    'SymPort не может удалить дополнение или вернуть системную DLL после удаления её SIS.',
  'Applicability is the author’s documentation, not a test on your phone. Installed means what you reported.':
    'Применимость взята из документации автора. «Установлено» — то, что вы сообщили сами.',
  "Applicability is the author's documentation, not a test on your phone. Installed means what you reported.":
    'Применимость взята из документации автора. «Установлено» — то, что вы сообщили сами.',
  'Preparation only. Copying files is not installation, and nothing is marked fixed until you retest.':
    'Только подготовка. Копирование файлов не установка; пока вы не перепроверите, ничего не считается исправленным.',
  'Checked from the SymPort server with certificate verification. This says nothing about the phone: its clock, certificates and TLS support decide what a Nokia can open.':
    'Проверено с сервера SymPort с проверкой сертификата. Это ничего не говорит о телефоне: что откроет Nokia, зависит от его часов, сертификатов и поддержки TLS.',
  'SymPort never installs this kit. Success is only an installation you confirm on the phone.':
    'SymPort не устанавливает этот набор. Успех — только установка, которую вы подтвердили на телефоне.',
  'Static analysis only. The author publishes no hash; confirm the file source yourself, then pin it.':
    'Только статический анализ. Автор не публикует хеш: сами убедитесь в источнике файла и закрепите его.',
  'Optional and opt-in. No generic system write, shell or automatic jailbreak exists. Without the agent every other function works as before.':
    'Необязательный компонент, включается по желанию. Общей записи в систему, оболочки и автоматического джейлбрейка нет. Без агента все остальные функции работают как раньше.',
  'Leads for review only. Absent data is unknown; nothing is declared working, safe or applied to a phone.':
    'Только подсказки для изучения. Отсутствующие данные считаются неизвестными; ничто не объявляется рабочим, безопасным или применённым к телефону.',
  'A pattern match is a lead, not a verdict on behaviour. No match is not proof of safety. Nothing was run, installed or exploited, and no file left this server.':
    'Совпадение с шаблоном — подсказка, а не вывод о поведении. Отсутствие совпадений не доказывает безопасность. Ничего не запускалось, не устанавливалось и не эксплуатировалось, файлы не покидали сервер.',
  'The phone is not connected; nothing was verified.': 'Телефон не подключён; ничего не проверено.',
  'Automated checks cover what SymPort can read. Boot, Wi-Fi, apps and HTTPS are what you report in the checklist; nothing here proves an installation or its success.':
    'Автоматические проверки охватывают то, что SymPort может прочитать. Загрузку, Wi-Fi, приложения и HTTPS вы отмечаете в чек-листе; ничто здесь не доказывает установку или её успех.',
  'Exported is not transferred and not played on a device.':
    'Экспорт — не передача и не воспроизведение на телефоне.',
  'Compatibility is checked against the model and the pinned file. Copying is not installation: finish it on the phone.':
    'Совместимость проверена по модели и закреплённому файлу. Копирование — не установка: завершите её на телефоне.',
  'Presets follow the model screen and generic S60 limits; check the result on the phone.':
    'Предустановки учитывают экран модели и общие ограничения S60; проверьте результат на телефоне.',
  'Registry of old system endpoints. Nothing here is applied by SymPort: settings are changed by you on the phone. Belle (N8/E7) endpoints are never carried over to S60v3/S60v5 phones. A reachable URL from the server proves nothing about a Nokia phone.':
    'Реестр старых системных адресов. SymPort ничего не применяет: настройки вы меняете на телефоне сами. Адреса Belle (N8/E7) никогда не переносятся на телефоны S60v3/S60v5. Доступность URL с сервера ничего не доказывает про телефон Nokia.',
  'SymPort never installs add-ons or patches. Entries without a pinned artifact are manual-only: author link, licence status and an instruction. A new version is a new entry with its own pinned artifact, never a mutable link.':
    'SymPort не устанавливает дополнения и патчи. Записи без закреплённого файла — только вручную: ссылка автора, статус лицензии и инструкция. Новая версия — отдельная запись со своим закреплённым файлом, а не изменяемая ссылка.',
};
Object.assign(RU, {
  'Model profile, not a measured firmware version':
    'Профиль модели, а не измеренная версия прошивки',
  'Your observation; not readable through a file transport':
    'Ваше наблюдение; через файловое подключение не читается',
});
export function st(language: string, text: string | undefined | null) {
  if (!text) return '';
  if (language !== 'ru') return text;
  if (RU[text]) return RU[text];
  const ops = /^(\d+) operations in the matrix$/.exec(text);
  if (ops) return `Операций в матрице возможностей: ${ops[1]}`;
  // "Preparation only: SymPort never installs or patches. <how to continue>"
  const prep = 'Preparation only: SymPort never installs or patches. ';
  if (text.startsWith(prep)) {
    const rest = text.slice(prep.length);
    return (
      'Только подготовка: SymPort ничего не устанавливает и не патчит. ' +
      (rest.startsWith('The file can')
        ? 'Файл можно скопировать через страховку восстановления.'
        : 'Следуйте инструкциям автора.')
    );
  }
  return text;
}
