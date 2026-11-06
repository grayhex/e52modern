import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Sidebar from '../nav/Sidebar';
import Topbar from '../nav/Topbar';
import Planned from '../nav/Planned';
import { plannedSpecs } from '../features/PlannedPages';
import { allItems, groups, redirects, resolveHash } from '../nav/routes';

function shell(ui: React.ReactNode, devices: unknown = { devices: [], limitations: {} }) {
  const client = new ApiClient(() => 'token');
  vi.spyOn(client, 'discover').mockResolvedValue(devices as never);
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ApiProvider client={client}>
        <PreferencesProvider>{ui}</PreferencesProvider>
      </ApiProvider>
    </QueryClientProvider>,
  );
}
const noop = () => undefined;
function sidebar(props: Partial<React.ComponentProps<typeof Sidebar>> = {}) {
  return (
    <Sidebar
      route="phone/overview"
      compact={false}
      onCompact={noop}
      mobile={false}
      open={false}
      onClose={noop}
      openGroups={['phone']}
      onGroups={noop}
      {...props}
    />
  );
}

describe('route registry', () => {
  it('has the six groups with the requested sub-items', () => {
    expect(groups.map((g) => g.ru)).toEqual([
      'Мой телефон',
      'Приложения',
      'Персонализация',
      'Восстановление',
      'Инструменты',
      'Разработка и эмуляция',
    ]);
    expect(groups.map((g) => g.items.length)).toEqual([7, 5, 4, 7, 6, 4]);
    expect(new Set(allItems.map((i) => i.id)).size).toBe(allItems.length);
  });
  it('redirects every legacy URL to an existing page and keeps its query', () => {
    for (const [legacy, target] of Object.entries(redirects)) {
      const resolved = resolveHash(legacy);
      expect(resolved.redirected).toBe(true);
      expect(allItems.some((i) => i.id === resolved.route)).toBe(true);
      expect(target.startsWith(resolved.route)).toBe(true);
    }
    const inspector = resolveHash('inspector?source=device&path=a.sis');
    expect(inspector).toMatchObject({ route: 'tools/certificates', redirected: true });
    expect(inspector.query).toBe('source=device&path=a.sis');
    expect(resolveHash('updates').hash).toBe('tools/diagnostics?view=updates');
    expect(resolveHash('phone/files')).toMatchObject({ route: 'phone/files', redirected: false });
    expect(resolveHash('')).toMatchObject({ route: 'phone/overview' });
    expect(resolveHash('nonsense/page').route).toBe('phone/overview');
  });
  it('marks unfinished pages as planned and gives each a placeholder spec', () => {
    const planned = allItems.filter((i) => i.status === 'planned').map((i) => i.id);
    expect(planned.sort()).toEqual(Object.keys(plannedSpecs).sort());
  });
});

describe('sidebar', () => {
  it('exposes groups as accessible disclosure buttons and marks the current page', () => {
    shell(sidebar());
    const phone = screen.getByRole('button', { name: /Мой телефон/ });
    expect(phone).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('button', { name: /Приложения/ })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(screen.getByRole('link', { name: 'Обзор устройства' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('link', { name: 'Файловый менеджер' })).not.toHaveAttribute(
      'aria-current',
    );
  });
  it('asks to toggle a group and keeps closed groups out of the tab order', async () => {
    const onGroups = vi.fn();
    shell(sidebar({ onGroups }));
    await userEvent.click(screen.getByRole('button', { name: /Приложения/ }));
    const toggle = onGroups.mock.calls.at(-1)?.[0] as (previous: string[]) => string[];
    expect(toggle(['phone'])).toEqual(['phone', 'apps']);
    expect(toggle(['phone', 'apps'])).toEqual(['phone']);
    const closed = document.getElementById('nav-region-apps')?.querySelector('ul');
    expect(closed).toHaveAttribute('inert');
  });
  it('shows a "soon" badge for planned pages only', () => {
    shell(sidebar({ openGroups: ['personalize'] }));
    const editor = screen.getByRole('link', { name: /Редактор тем/ });
    expect(within(editor).queryByText('Скоро')).toBeNull();
    expect(
      within(screen.getByRole('link', { name: /Обои/ })).getByText('Скоро'),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('link', { name: /Мастер рингтонов/ })).queryByText('Скоро'),
    ).toBeNull();
  });
  it('shows icons only in compact mode but keeps accessible names', () => {
    shell(sidebar({ compact: true }));
    expect(screen.getByRole('link', { name: 'Файловый менеджер' })).toHaveAttribute(
      'aria-label',
      'Файловый менеджер',
    );
    expect(document.querySelector('.sidebar--compact')).not.toBeNull();
    expect(screen.queryByRole('button', { name: /Мой телефон/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'Развернуть меню' })).toBeInTheDocument();
  });
  it('is inert and off-canvas on a phone until opened', () => {
    shell(sidebar({ mobile: true, open: false }));
    expect(document.getElementById('sidebar')).toHaveAttribute('inert');
    expect(document.getElementById('sidebar')).toHaveAttribute('data-open', 'false');
  });
  it('shows the connected phone from real discovery data, and never invents one', async () => {
    shell(sidebar(), {
      devices: [
        { id: 'usb', model: 'Nokia E52', transport: 'gammu', connected: true, capabilities: [] },
      ],
      limitations: {},
    });
    expect(await screen.findByText(/Nokia E52/)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /Подключение: Nokia E52 — Подключено/ }),
    ).toHaveAttribute('href', '#phone/connection');
  });
  it('reports no phone when discovery finds none and "unknown" when discovery fails', async () => {
    shell(sidebar());
    expect(await screen.findByText('Телефон не подключён')).toBeInTheDocument();
  });
  it('lets the user switch language; the theme is light only while dark mode is off', async () => {
    shell(sidebar());
    await userEvent.click(screen.getByRole('button', { name: 'Настройки' }));
    await userEvent.selectOptions(screen.getByLabelText('Язык'), 'en');
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('en');
    expect(screen.queryByLabelText('Theme')).toBeNull();
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});

describe('breadcrumbs and placeholders', () => {
  it('builds SymPort / group / page with the page marked current', () => {
    shell(<Topbar route="tools/firmware" mobile={false} menuOpen={false} onMenu={noop} />);
    const crumbs = screen.getByRole('navigation', { name: 'Путь по разделам' });
    expect(within(crumbs).getByText('Инструменты')).toBeInTheDocument();
    expect(crumbs.querySelector('[aria-current="page"]')).toHaveTextContent(
      'Firmware & ROM Explorer',
    );
  });
  it('a placeholder says "in development" and offers no working controls', () => {
    const spec = plannedSpecs['personalize/wallpapers'];
    if (!spec) throw Error('missing spec');
    shell(<Planned spec={spec} />);
    expect(screen.getByText('В разработке')).toBeInTheDocument();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.getByText(/результаты не имитируются/)).toBeInTheDocument();
  });
});
