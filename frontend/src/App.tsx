import { lazy, Suspense, useEffect, useState } from 'react';
import { usePreferences } from './state/app';
const Dashboard = lazy(() => import('./features/Dashboard'));
const Files = lazy(() => import('./features/Files'));
const Connection = lazy(() => import('./features/Connection'));
const routes = [
  ['manager', 'Dashboard', 'Обзор телефона'],
  ['files', 'Files', 'Файлы'],
  ['connection', 'Connection', 'Подключение'],
] as const;
const classic = [
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
  const [route, setRoute] = useState(location.hash.slice(1) || 'manager');
  useEffect(() => {
    const change = () => setRoute(location.hash.slice(1) || 'manager');
    addEventListener('hashchange', change);
    return () => removeEventListener('hashchange', change);
  }, []);
  const active = routes.find((item) => item[0] === route);
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
                  {t(en, ru)}
                </a>
              ))}
            </nav>
            <p className="nav-label">{t('Existing workspace', 'Текущее рабочее пространство')}</p>
            <nav aria-label={t('Existing workspace', 'Текущее рабочее пространство')}>
              {classic.map(([id, en, ru]) => (
                <a className="nav-link" key={id} href={`/#${id}`}>
                  {t(en, ru)} ↗
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
          <Suspense fallback={<p role="status">{t('Loading…', 'Загрузка…')}</p>}>
            {route === 'files' ? (
              <Files />
            ) : route === 'connection' ? (
              <Connection />
            ) : (
              <Dashboard />
            )}
          </Suspense>
        </div>
      </main>
    </div>
  );
}
