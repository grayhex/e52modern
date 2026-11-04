import { Activity, lazy, Suspense, useEffect, useState } from 'react';
import { usePreferences } from './state/app';
import { NavIcon } from './components/NavIcon';
const Dashboard = lazy(() => import('./features/Dashboard'));
const Files = lazy(() => import('./features/Files'));
const Connection = lazy(() => import('./features/Connection'));
const Personal = lazy(() => import('./features/Personal'));
const Media = lazy(() => import('./features/Media'));
const Ringtone = lazy(() => import('./features/Ringtone'));
const Catalog = lazy(() => import('./features/Catalog'));
const Installed = lazy(() => import('./features/Installed'));
const Backups = lazy(() => import('./features/Backups'));
const Workbench = lazy(() => import('./features/Workbench'));
const Updates = lazy(() =>
  import('./features/Workbench').then((module) => ({ default: module.Updates })),
);
const Inspector = lazy(() => import('./features/Inspector'));
const Jailbreak = lazy(() => import('./features/Jailbreak'));
const Lab = lazy(() => import('./features/Lab'));
const routes = [
  ['manager', 'Dashboard', 'Обзор телефона'],
  ['files', 'Files', 'Файлы'],
  ['connection', 'Connection', 'Подключение'],
] as const;
const moreRoutes = [
  ['ringtone', 'Ringtone Studio', 'Мастер рингтонов'],
  ['contacts', 'Contacts', 'Контакты'],
  ['calendar', 'Calendar', 'Календарь'],
  ['messages', 'Messages', 'Сообщения'],
  ['media', 'Media', 'Медиа'],
  ['backups', 'Backups', 'Копии'],
  ['catalog', 'App Catalog', 'Каталог'],
  ['installed', 'Applications', 'Приложения'],
  ['updates', 'Updates', 'Обновления'],
  ['inspector', 'Certificate Inspector', 'Сертификаты'],
  ['jailbreak', 'Jailbreak Manager', 'Разблокировка'],
  ['themes', 'Themes', 'Темы'],
  ['lab', 'Emulator Lab', 'Эмулятор'],
  ['apps', 'Development', 'Разработка'],
  ['device', 'Device testing', 'Проверка телефона'],
  ['overview', 'Environment', 'Среда'],
  ['activity', 'Activity', 'Операции'],
] as const;
export default function App() {
  const { language, theme, setLanguage, setTheme, t } = usePreferences();
  const [hash, setRoute] = useState(location.hash.slice(1) || 'manager');
  const route = hash.split('?')[0] ?? 'manager';
  const [visited, setVisited] = useState<Record<string, string>>(() => ({ [route]: hash }));
  useEffect(() => {
    const change = () => {
      const next = location.hash.slice(1) || 'manager';
      setRoute(next);
      setVisited((previous) => ({
        ...previous,
        [next.split('?')[0] ?? 'manager']: next.includes('?') ? next : (previous[next] ?? next),
      }));
    };
    addEventListener('hashchange', change);
    return () => removeEventListener('hashchange', change);
  }, []);
  const allRoutes = [...routes, ...moreRoutes];
  const active = allRoutes.find((item) => item[0] === route);
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-panel">
          <a className="brand" href="#manager">
            <img
              className="brand-lockup"
              src={`${import.meta.env.BASE_URL}brand/nokia-symport-horizontal.svg`}
              alt="Nokia / SymPort"
            />
          </a>
          <div className="sidebar-menu">
            <nav aria-label={t('Phone', 'Телефон')}>
              {routes.map(([id, en, ru]) => (
                <a
                  className={`nav-link ${route === id ? 'active' : ''}`}
                  key={id}
                  href={`#${id}`}
                  aria-current={route === id ? 'page' : undefined}
                >
                  <NavIcon name={id} />
                  {t(en, ru)}
                </a>
              ))}
            </nav>
            <p className="nav-label">{t('Workspace', 'Рабочая среда')}</p>
            <nav aria-label={t('Workspace', 'Рабочая среда')}>
              {moreRoutes.map(([id, en, ru]) => (
                <a
                  className={`nav-link ${route === id ? 'active' : ''}`}
                  aria-current={route === id ? 'page' : undefined}
                  key={id}
                  href={`#${id}`}
                >
                  <NavIcon name={id} />
                  {t(en, ru)}
                </a>
              ))}
            </nav>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <span>SymPort / {active ? t(active[1], active[2]) : 'React'}</span>
          <div className="form-row">
            <label className="sr-only" htmlFor="language">
              Language
            </label>
            <select
              id="language"
              value={language}
              onChange={(event) => setLanguage(event.target.value === 'en' ? 'en' : 'ru')}
            >
              <option value="ru">Русский</option>
              <option value="en">English</option>
            </select>
            <label className="sr-only" htmlFor="theme">
              Theme
            </label>
            <select
              id="theme"
              value={theme}
              onChange={(event) =>
                setTheme(
                  event.target.value === 'dark'
                    ? 'dark'
                    : event.target.value === 'light'
                      ? 'light'
                      : 'system',
                )
              }
            >
              <option value="system">{t('System', 'Системная')}</option>
              <option value="light">{t('Light', 'Светлая')}</option>
              <option value="dark">{t('Dark', 'Тёмная')}</option>
            </select>
          </div>
        </header>
        <div className="content">
          {Object.entries(visited).map(([name, intent]) => (
            <Activity key={name} mode={name === route ? 'visible' : 'hidden'}>
              <Suspense fallback={<p role="status">{t('Loading…', 'Загрузка…')}</p>}>
                <section className="react-page" id={name} key={intent}>
                  <RouteView route={name} />
                </section>
              </Suspense>
            </Activity>
          ))}
        </div>
      </main>
    </div>
  );
}

function RouteView({ route }: { route: string }) {
  return route === 'files' ? (
    <Files />
  ) : route === 'connection' ? (
    <Connection />
  ) : route === 'contacts' ? (
    <Personal domain="contacts" />
  ) : route === 'messages' ? (
    <Personal domain="sms" />
  ) : route === 'calendar' ? (
    <Personal domain="calendar" />
  ) : route === 'media' ? (
    <Media />
  ) : route === 'ringtone' ? (
    <Ringtone />
  ) : route === 'catalog' ? (
    <Catalog />
  ) : route === 'installed' ? (
    <Installed />
  ) : route === 'backups' ? (
    <Backups />
  ) : route === 'updates' ? (
    <Updates />
  ) : route === 'inspector' ? (
    <Inspector />
  ) : route === 'jailbreak' ? (
    <Jailbreak />
  ) : route === 'lab' ? (
    <Lab />
  ) : route === 'themes' ||
    route === 'apps' ||
    route === 'device' ||
    route === 'overview' ||
    route === 'activity' ? (
    <Workbench page={route} />
  ) : (
    <Dashboard />
  );
}
