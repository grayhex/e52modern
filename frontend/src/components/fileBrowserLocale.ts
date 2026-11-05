/**
 * @harryy/react-file-browser ships English-only labels and has no locale option. Until it has one, the
 * Russian interface localises exactly what the library renders: whole strings from a dictionary plus a few
 * patterns. Unknown text is left untouched (never guessed), and file/folder names are never translated:
 * only strings that match an entry exactly are replaced.
 */
const exact: Record<string, string> = {
  'All kinds': 'Все типы',
  Folders: 'Папки',
  Files: 'Файлы',
  Name: 'Имя',
  Modified: 'Изменён',
  Size: 'Размер',
  'New folder': 'Новая папка',
  Upload: 'Загрузить',
  selected: 'выбрано',
  'Select all': 'Выбрать все',
  'Select none': 'Снять выбор',
  Actions: 'Действия',
  Folder: 'Папка',
  items: 'элементов',
  item: 'элемент',
  Download: 'Скачать',
  Delete: 'Удалить',
  Cancel: 'Отмена',
  Close: 'Закрыть',
  Open: 'Открыть',
  Preview: 'Просмотр',
  Rename: 'Переименовать',
  Copy: 'Копировать',
  Move: 'Переместить',
  Replace: 'Заменить',
  Skip: 'Пропустить',
  'Keep both': 'Оставить оба',
  'Apply to all conflicts': 'Применить ко всем конфликтам',
  'File conflict': 'Конфликт файлов',
  'Create folder': 'Создать папку',
  'Folder name': 'Имя папки',
  'Delete selected items': 'Удалить выбранные элементы',
  'Delete selected': 'Удалить выбранное',
  'This removes the selected entries from storage.': 'Выбранные записи будут удалены с накопителя.',
  'Open prepared download': 'Открыть подготовленную загрузку',
  'Download ready': 'Загрузка готова',
  'Download failed': 'Не удалось скачать',
  'Download it to open it on your device.': 'Скачайте файл, чтобы открыть его на устройстве.',
  'Drop files to upload': 'Перетащите файлы для загрузки',
  'Back to folder': 'Назад в папку',
  'Parent folder': 'Родительская папка',
  'Current folder': 'Текущая папка',
  'Could not load this folder': 'Не удалось загрузить эту папку',
  'Create a folder or upload files to start.': 'Создайте папку или загрузите файлы.',
  'No preview for this file': 'Для этого файла нет просмотра',
  'Dismiss download': 'Скрыть загрузку',
  'Dismiss upload rejection': 'Скрыть отказ загрузки',
  'Search this folder': 'Поиск в этой папке',
  'Upload files': 'Загрузить файлы',
  Breadcrumb: 'Путь',
  'Search files': 'Поиск файлов',
  'Filter files': 'Фильтр файлов',
  'Sort files': 'Сортировка',
  'Toggle sort direction': 'Направление сортировки',
  View: 'Вид',
  'List view': 'Список',
  'Grid view': 'Плитки',
  'Selection actions': 'Действия с выбранным',
  'Select all items': 'Выбрать все элементы',
  'Folder actions': 'Действия с папкой',
  'Copy path': 'Копировать путь',
};
type Pattern = [RegExp, (m: RegExpExecArray) => string, boolean?];
// The optional third flag marks patterns that embed a file name: attributes only, never visible text.
const patterns: Pattern[] = [
  [/^· (\d+) selected$/, (m) => `· выбрано: ${m[1]}`],
  [/^Select (.+)$/, (m) => `Выбрать ${m[1]}`, true],
  [/^More actions for (.+)$/, (m) => `Действия для ${m[1]}`, true],
  [/^Open (.+)$/, (m) => `Открыть ${m[1]}`, true],
  [
    /^(.+) ready\. (\d+) items?\. (\d+) selected\.$/,
    (m) => `${m[1]}: готово. Элементов: ${m[2]}. Выбрано: ${m[3]}.`,
  ],
];

export function localizeText(value: string, attribute = false): string {
  const trimmed = value.trim();
  if (!trimmed) return value;
  const found = exact[trimmed];
  if (found) return value.replace(trimmed, found);
  for (const [pattern, make, attributeOnly] of patterns) {
    if (attributeOnly && !attribute) continue;
    const match = pattern.exec(trimmed);
    if (match) return value.replace(trimmed, make(match));
  }
  return value;
}

const ATTRIBUTES = ['aria-label', 'placeholder', 'title'] as const;
function translate(root: Node) {
  if (root.nodeType === Node.TEXT_NODE) {
    // Names of files and folders are data: inside an item only the kind column (not the name cell) is UI.
    const item = root.parentElement?.closest('[data-fb-path]');
    if (item) {
      const cell = root.parentElement?.closest('td');
      if (!cell || cell === cell.parentElement?.firstElementChild) return;
    }
    const next = localizeText(root.nodeValue ?? '');
    if (next !== root.nodeValue) root.nodeValue = next;
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  const element = root as Element;
  for (const name of ATTRIBUTES) {
    const value = element.getAttribute(name);
    if (value) {
      const next = localizeText(value, true);
      if (next !== value) element.setAttribute(name, next);
    }
  }
  element.childNodes.forEach(translate);
}

/** Translates `root` now and whenever the library re-renders inside it. Returns a disposer. */
export function observeLocalization(root: HTMLElement): () => void {
  translate(root);
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === 'characterData') translate(record.target);
      else if (record.type === 'attributes') translate(record.target);
      else record.addedNodes.forEach(translate);
    }
  });
  observer.observe(root, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: [...ATTRIBUTES],
  });
  return () => observer.disconnect();
}
