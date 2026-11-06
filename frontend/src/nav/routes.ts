import {
  AppWindow,
  AudioLines,
  Boxes,
  CalendarDays,
  Clapperboard,
  Cloud,
  Cpu,
  DatabaseBackup,
  FileBadge,
  FileSearch,
  FolderOpen,
  Hammer,
  History,
  LifeBuoy,
  Image,
  LayoutDashboard,
  Layers,
  LockOpen,
  MessageSquare,
  MonitorPlay,
  Package,
  Palette,
  PenTool,
  Smartphone,
  Stethoscope,
  Store,
  TestTube,
  Users,
  Workflow,
  FlaskConical,
  Wrench,
  Globe,
  HeartPulse,
  ClipboardCheck,
  PackagePlus,
  Usb,
  type LucideIcon,
} from 'lucide-react';

/** Canonical route ids are `group/page`; legacy single-segment ids keep working through `redirects`. */
export type NavItem = {
  id: string;
  icon: LucideIcon;
  en: string;
  ru: string;
  /** `planned` pages are honest placeholders: no working feature is simulated. */
  status: 'ready' | 'planned';
  experimental?: boolean;
};
export type NavGroup = { id: string; icon: LucideIcon; en: string; ru: string; items: NavItem[] };

export const groups: NavGroup[] = [
  {
    id: 'phone',
    icon: Smartphone,
    en: 'My phone',
    ru: 'Мой телефон',
    items: [
      {
        id: 'phone/overview',
        icon: LayoutDashboard,
        en: 'Device overview',
        ru: 'Обзор устройства',
        status: 'ready',
      },
      {
        id: 'phone/files',
        icon: FolderOpen,
        en: 'File manager',
        ru: 'Файловый менеджер',
        status: 'ready',
      },
      { id: 'phone/contacts', icon: Users, en: 'Contacts', ru: 'Контакты', status: 'ready' },
      {
        id: 'phone/messages',
        icon: MessageSquare,
        en: 'Messages',
        ru: 'Сообщения',
        status: 'ready',
      },
      {
        id: 'phone/calendar',
        icon: CalendarDays,
        en: 'Calendar',
        ru: 'Календарь',
        status: 'ready',
      },
      { id: 'phone/media', icon: Clapperboard, en: 'Media', ru: 'Медиа', status: 'ready' },
      {
        id: 'phone/backups',
        icon: DatabaseBackup,
        en: 'Backups',
        ru: 'Резервные копии',
        status: 'ready',
      },
    ],
  },
  {
    id: 'apps',
    icon: AppWindow,
    en: 'Applications',
    ru: 'Приложения',
    items: [
      {
        id: 'apps/catalog',
        icon: Store,
        en: 'App catalog',
        ru: 'Каталог приложений',
        status: 'ready',
      },
      {
        id: 'apps/installed',
        icon: AppWindow,
        en: 'My applications',
        ru: 'Мои приложения',
        status: 'ready',
      },
      {
        id: 'apps/packages',
        icon: Package,
        en: 'Installation packages',
        ru: 'Установочные пакеты',
        status: 'ready',
      },
      {
        id: 'apps/dependencies',
        icon: Workflow,
        en: 'Dependencies',
        ru: 'Зависимости',
        status: 'ready',
      },
      {
        id: 'apps/kits',
        icon: Boxes,
        en: 'Application kits',
        ru: 'Комплекты приложений',
        status: 'ready',
      },
    ],
  },
  {
    id: 'personalize',
    icon: Palette,
    en: 'Personalisation',
    ru: 'Персонализация',
    items: [
      {
        id: 'personalize/themes',
        icon: Palette,
        en: 'Themes',
        ru: 'Темы оформления',
        status: 'ready',
      },
      {
        id: 'personalize/theme-editor',
        icon: PenTool,
        en: 'Theme editor',
        ru: 'Редактор тем',
        status: 'ready',
      },
      {
        id: 'personalize/wallpapers',
        icon: Image,
        en: 'Wallpapers',
        ru: 'Обои',
        status: 'planned',
      },
      {
        id: 'personalize/ringtones',
        icon: AudioLines,
        en: 'Ringtone studio',
        ru: 'Мастер рингтонов',
        status: 'ready',
      },
    ],
  },
  {
    id: 'revive',
    icon: LifeBuoy,
    en: 'Revive',
    ru: 'Восстановление',
    items: [
      {
        id: 'revive/home',
        icon: HeartPulse,
        en: 'Recovery centre',
        ru: 'Центр восстановления',
        status: 'ready',
      },
      {
        id: 'revive/network',
        icon: Globe,
        en: 'Network & TLS',
        ru: 'Сеть и TLS',
        status: 'ready',
      },
      {
        id: 'revive/kit',
        icon: Boxes,
        en: 'Application kit',
        ru: 'Набор приложений',
        status: 'ready',
      },
      {
        id: 'revive/services',
        icon: Cloud,
        en: 'Online services',
        ru: 'Онлайн-сервисы',
        status: 'ready',
      },
      {
        id: 'revive/reborn',
        icon: Usb,
        en: 'Reborn for N95',
        ru: 'Reborn для N95',
        status: 'ready',
        experimental: true,
      },
      {
        id: 'revive/addons',
        icon: PackagePlus,
        en: 'Add-ons & patches',
        ru: 'Дополнения и патчи',
        status: 'ready',
      },
      {
        id: 'revive/post-check',
        icon: ClipboardCheck,
        en: 'After installation',
        ru: 'После установки',
        status: 'ready',
      },
    ],
  },
  {
    id: 'tools',
    icon: Wrench,
    en: 'Tools',
    ru: 'Инструменты',
    items: [
      {
        id: 'tools/diagnostics',
        icon: Stethoscope,
        en: 'Device diagnostics',
        ru: 'Диагностика устройства',
        status: 'ready',
      },
      {
        id: 'tools/certificates',
        icon: FileBadge,
        en: 'Certificate Inspector',
        ru: 'Certificate Inspector',
        status: 'ready',
      },
      {
        id: 'tools/firmware',
        icon: Cpu,
        en: 'Firmware & ROM Explorer',
        ru: 'Firmware & ROM Explorer',
        status: 'ready',
      },
      {
        id: 'tools/cfw',
        icon: FileSearch,
        en: 'Custom firmware',
        ru: 'Кастомные прошивки',
        status: 'ready',
      },
      {
        id: 'tools/jailbreak',
        icon: LockOpen,
        en: 'Jailbreak Manager',
        ru: 'Jailbreak Manager',
        status: 'ready',
        experimental: true,
      },
      {
        id: 'tools/activity',
        icon: History,
        en: 'Operations log',
        ru: 'Журнал операций',
        status: 'ready',
      },
    ],
  },
  {
    id: 'dev',
    icon: Hammer,
    en: 'Development & emulation',
    ru: 'Разработка и эмуляция',
    items: [
      { id: 'dev/lab', icon: MonitorPlay, en: 'Emulator Lab', ru: 'Emulator Lab', status: 'ready' },
      { id: 'dev/sdk', icon: Hammer, en: 'SDK & build', ru: 'SDK и сборка', status: 'ready' },
      {
        id: 'dev/app-tests',
        icon: FlaskConical,
        en: 'Application testing',
        ru: 'Тестирование приложений',
        status: 'planned',
      },
      {
        id: 'dev/theme-tests',
        icon: TestTube,
        en: 'Theme testing',
        ru: 'Тестирование тем',
        status: 'planned',
      },
    ],
  },
];

/** Pages reachable by link but not listed in the menu. */
export const hiddenRoutes: NavItem[] = [
  { id: 'phone/connection', icon: Layers, en: 'Connection', ru: 'Подключение', status: 'ready' },
];

export const allItems: NavItem[] = [...groups.flatMap((g) => g.items), ...hiddenRoutes];
export const DEFAULT_ROUTE = 'phone/overview';

/** Every URL that existed before the menu was restructured, mapped to its canonical route. */
export const redirects: Record<string, string> = {
  manager: 'phone/overview',
  files: 'phone/files',
  connection: 'phone/connection',
  contacts: 'phone/contacts',
  messages: 'phone/messages',
  calendar: 'phone/calendar',
  media: 'phone/media',
  backups: 'phone/backups',
  catalog: 'apps/catalog',
  installed: 'apps/installed',
  themes: 'personalize/themes',
  ringtone: 'personalize/ringtones',
  updates: 'tools/diagnostics?view=updates',
  inspector: 'tools/certificates',
  jailbreak: 'tools/jailbreak',
  activity: 'tools/activity',
  device: 'tools/diagnostics',
  lab: 'dev/lab',
  apps: 'dev/sdk',
  overview: 'dev/sdk?view=environment',
  'tools/revive': 'revive/home',
};

export type Resolved = { route: string; query: string; hash: string; redirected: boolean };

/** Resolve a location hash (without `#`) to a canonical route, keeping query strings. */
export function resolveHash(raw: string): Resolved {
  const [head = '', ...rest] = raw.split('?');
  const originalQuery = rest.join('?');
  const key = head.replace(/^\/+/, '').replace(/\/+$/, '');
  const legacy = redirects[key];
  let route = key;
  let query = originalQuery;
  let redirected = false;
  if (legacy) {
    const [target = DEFAULT_ROUTE, extra = ''] = legacy.split('?');
    route = target;
    query = [extra, originalQuery].filter(Boolean).join('&');
    redirected = true;
  }
  if (!allItems.some((item) => item.id === route)) {
    route = DEFAULT_ROUTE;
    query = '';
    redirected = key !== '';
  }
  return { route, query, hash: query ? `${route}?${query}` : route, redirected };
}

export function findItem(route: string) {
  return allItems.find((item) => item.id === route);
}
export function findGroup(route: string) {
  return groups.find((group) => route.startsWith(group.id + '/'));
}
