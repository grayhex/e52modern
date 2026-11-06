import { ChevronRight, Code2, Menu } from 'lucide-react';
import { usePreferences } from '../state/app';
import { findGroup, findItem } from './routes';

export default function Topbar({
  route,
  mobile,
  menuOpen,
  onMenu,
}: {
  route: string;
  mobile: boolean;
  menuOpen: boolean;
  onMenu: () => void;
}) {
  const { t, mode } = usePreferences();
  const item = findItem(route);
  const group = findGroup(route);
  const first = group?.items[0];
  return (
    <header className="topbar">
      {mobile && (
        <button
          type="button"
          className="icon-button"
          aria-controls="sidebar"
          aria-expanded={menuOpen}
          aria-label={t('Open menu', 'Открыть меню')}
          onClick={onMenu}
        >
          <Menu size={20} aria-hidden="true" />
        </button>
      )}
      <nav className="breadcrumbs" aria-label={t('Breadcrumbs', 'Путь по разделам')}>
        <ol>
          <li>
            <a href="#phone/overview">SymPort</a>
          </li>
          {group && (
            <li>
              <ChevronRight size={14} aria-hidden="true" />
              {first ? <a href={`#${first.id}`}>{t(group.en, group.ru)}</a> : t(group.en, group.ru)}
            </li>
          )}
          {item && (
            <li aria-current="page">
              <ChevronRight size={14} aria-hidden="true" />
              <span>{t(item.en, item.ru)}</span>
            </li>
          )}
        </ol>
      </nav>
      {mode === 'developer' && (
        <span className="mode-badge" data-testid="mode-badge">
          <Code2 size={13} aria-hidden="true" /> {t('Developer mode', 'Режим разработчика')}
        </span>
      )}
    </header>
  );
}
