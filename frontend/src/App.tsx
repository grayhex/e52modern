import { Activity, lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { usePreferences } from './state/app';
import Sidebar from './nav/Sidebar';
import Topbar from './nav/Topbar';
import Planned from './nav/Planned';
import { plannedSpecs } from './features/PlannedPages';
import { resolveHash } from './nav/routes';
import { isBoolean, isStringArray, useStored } from './nav/storage';
import { useMedia } from './nav/useMedia';
const Dashboard = lazy(() => import('./features/Dashboard'));
const Files = lazy(() => import('./features/Files'));
const Connection = lazy(() => import('./features/Connection'));
const Personal = lazy(() => import('./features/Personal'));
const Media = lazy(() => import('./features/Media'));
const Ringtone = lazy(() => import('./features/Ringtone'));
const Catalog = lazy(() => import('./features/Catalog'));
const Installed = lazy(() => import('./features/Installed'));
const Packages = lazy(() => import('./features/Packages'));
const Dependencies = lazy(() => import('./features/Dependencies'));
const ThemeStudio = lazy(() => import('./features/ThemeStudio'));
const Kits = lazy(() => import('./features/Kits'));
const Backups = lazy(() => import('./features/Backups'));
const Workbench = lazy(() => import('./features/Workbench'));
const Diagnostics = lazy(() => import('./features/Diagnostics'));
const Sdk = lazy(() => import('./features/Sdk'));
const Inspector = lazy(() => import('./features/Inspector'));
const Firmware = lazy(() => import('./features/Firmware'));
const Jailbreak = lazy(() => import('./features/Jailbreak'));
const Lab = lazy(() => import('./features/Lab'));

/** Apply the canonical form of the current URL; legacy single-segment URLs are replaced, not stacked. */
function readLocation() {
  const raw = location.hash.slice(1);
  const resolved = resolveHash(raw);
  if (raw !== resolved.hash && (resolved.redirected || raw === ''))
    history.replaceState(null, '', `#${resolved.hash}`);
  return resolved;
}
export default function App() {
  const { t } = usePreferences();
  const [current, setCurrent] = useState(readLocation);
  const { route } = current;
  const [visited, setVisited] = useState<Record<string, string>>(() => ({ [route]: current.hash }));
  const [compact, setCompact] = useStored('symport-nav-compact', false, isBoolean);
  const [openGroups, setOpenGroups] = useStored('symport-nav-groups', ['phone'], isStringArray);
  const [drawer, setDrawer] = useState(false);
  const mobile = useMedia('(max-width: 760px)');
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);
  useEffect(() => {
    const change = () => {
      const next = readLocation();
      setCurrent(next);
      setVisited((previous) => ({
        ...previous,
        [next.route]: next.query ? next.hash : (previous[next.route] ?? next.hash),
      }));
    };
    addEventListener('hashchange', change);
    return () => removeEventListener('hashchange', change);
  }, []);
  useEffect(() => {
    // Move keyboard/screen-reader focus to the new page; the initial load keeps the browser default.
    if (first.current) first.current = false;
    else main.current?.focus({ preventScroll: true });
    document.title = `SymPort`;
  }, [route]);
  const closeDrawer = useCallback(() => setDrawer(false), []);
  return (
    <div className={`shell ${compact && !mobile ? 'shell--compact' : ''}`}>
      <button type="button" className="skip-link" onClick={() => main.current?.focus()}>
        {t('Skip to content', 'К содержимому')}
      </button>
      <Sidebar
        route={route}
        compact={compact}
        onCompact={setCompact}
        mobile={mobile}
        open={drawer && mobile}
        onClose={closeDrawer}
        openGroups={openGroups}
        onGroups={setOpenGroups}
      />
      <main className="main" id="main-content" tabIndex={-1} ref={main}>
        <Topbar
          route={route}
          mobile={mobile}
          menuOpen={drawer && mobile}
          onMenu={() => setDrawer(true)}
        />
        <div className="content">
          {Object.entries(visited).map(([name, intent]) => (
            <Activity key={name} mode={name === route ? 'visible' : 'hidden'}>
              <Suspense fallback={<p role="status">{t('Loading…', 'Загрузка…')}</p>}>
                <section
                  className="react-page"
                  id={`page-${name.replace('/', '-')}`}
                  data-route={name}
                  key={intent}
                >
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
  const planned = plannedSpecs[route];
  if (planned) return <Planned spec={planned} />;
  switch (route) {
    case 'phone/files':
      return <Files />;
    case 'phone/connection':
      return <Connection />;
    case 'phone/contacts':
      return <Personal domain="contacts" />;
    case 'phone/messages':
      return <Personal domain="sms" />;
    case 'phone/calendar':
      return <Personal domain="calendar" />;
    case 'phone/media':
      return <Media />;
    case 'phone/backups':
      return <Backups />;
    case 'apps/catalog':
      return <Catalog />;
    case 'apps/installed':
      return <Installed />;
    case 'apps/packages':
      return <Packages />;
    case 'apps/dependencies':
      return <Dependencies />;
    case 'apps/kits':
      return <Kits />;
    case 'personalize/theme-editor':
      return <ThemeStudio />;
    case 'personalize/themes':
      return <Workbench page="themes" />;
    case 'personalize/ringtones':
      return <Ringtone />;
    case 'tools/diagnostics':
      return <Diagnostics />;
    case 'tools/certificates':
      return <Inspector />;
    case 'tools/firmware':
      return <Firmware />;
    case 'tools/jailbreak':
      return <Jailbreak />;
    case 'tools/activity':
      return <Workbench page="activity" />;
    case 'dev/lab':
      return <Lab />;
    case 'dev/sdk':
      return <Sdk />;
    default:
      return <Dashboard />;
  }
}
