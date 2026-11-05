import { describe, expect, it } from 'vitest';
import { localizeText, observeLocalization } from '../components/fileBrowserLocale';

describe('file browser localisation', () => {
  it('translates library labels and patterns', () => {
    expect(localizeText('Search this folder', true)).toBe('Поиск в этой папке');
    expect(localizeText('card ready. 4 items. 1 selected.')).toBe(
      'card: готово. Элементов: 4. Выбрано: 1.',
    );
    expect(localizeText('· 3 selected')).toBe('· выбрано: 3');
    expect(localizeText('Select a.txt', true)).toBe('Выбрать a.txt');
  });
  it('keeps unknown text and file-name-shaped text untouched', () => {
    expect(localizeText('Quarterly report.xlsx')).toBe('Quarterly report.xlsx');
    expect(localizeText('Select a.txt')).toBe('Select a.txt'); // visible text: could be a file name
    expect(localizeText('Open the pod bay doors')).toBe('Open the pod bay doors');
  });
  it('never translates names inside item rows, only the kind column', async () => {
    const root = document.createElement('div');
    root.innerHTML =
      '<table><tr data-fb-path="/Files"><td><button>Files</button></td><td>Folder</td></tr></table><button>Upload</button>';
    document.body.append(root);
    const stop = observeLocalization(root);
    const cells = [...root.querySelectorAll('td')].map((c) => c.textContent);
    expect(cells).toEqual(['Files', 'Папка']);
    expect(root.lastElementChild?.textContent).toBe('Загрузить');
    // later re-renders are translated too
    const added = document.createElement('span');
    added.textContent = 'Select all';
    root.append(added);
    await Promise.resolve();
    expect(added.textContent).toBe('Выбрать все');
    stop();
    root.remove();
  });
});
