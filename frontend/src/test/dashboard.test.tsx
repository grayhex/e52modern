import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Dashboard from '../features/Dashboard';

afterEach(cleanup);

/** Registry entries as the backend sends them. A third model proves the page is data-driven. */
const registry = [
  {
    id: 'nokia-e52',
    model: 'E52',
    name: 'Nokia E52',
    image: '/phones/nokia-e52-silver.png',
    screen: { width: 240, height: 320, orientation: 'portrait' },
    input: 'numeric-keypad',
    s60: '3rd FP2',
    symbian: '9.3',
  },
  {
    id: 'nokia-e72',
    model: 'E72',
    name: 'Nokia E72',
    image: '/phones/nokia-e72.png',
    screen: { width: 320, height: 240, orientation: 'landscape' },
    input: 'qwerty',
    s60: '3rd FP2',
    symbian: '9.3',
  },
  {
    id: 'nokia-e99',
    model: 'E99',
    name: 'Nokia E99',
    image: '/phones/nokia-e99.png',
    screen: { width: 360, height: 640, orientation: 'portrait' },
    input: 'touch',
    s60: '5th',
    symbian: '9.4',
  },
];
const profileOf = (m: (typeof registry)[number]) => ({
  id: m.id,
  name: m.name,
  image: m.image,
  screen: m.screen,
  s60: m.s60,
  symbian: m.symbian,
  input: m.input,
});
const phone = (m: (typeof registry)[number], extra: Record<string, unknown> = {}) => ({
  id: 'gammu',
  name: m.name,
  model: `${m.name} (RM-000)`,
  rm: 'RM-000',
  firmware: '071.004',
  transport: 'gammu',
  connected: true,
  battery: 80,
  signal: 60,
  capabilities: [],
  model_profile: profileOf(m),
  ...extra,
});

async function render_(devices: unknown[], heading: RegExp | string = /Nokia/) {
  const client = new ApiClient(() => 'token');
  vi.spyOn(client, 'discover').mockResolvedValue({
    devices,
    models: registry,
    limitations: {},
  } as never);
  vi.spyOn(client, 'history').mockResolvedValue({ operations: [] });
  vi.spyOn(client, 'request').mockResolvedValue({ measurements: [] } as never);
  vi.spyOn(client, 'get').mockResolvedValue({
    packages: [],
    library: [],
    projects: [],
    jobs: [],
    device_report: {},
    backups: [],
    backup_free: null,
  } as never);
  const view = render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ApiProvider client={client}>
        <PreferencesProvider>
          <Dashboard />
        </PreferencesProvider>
      </ApiProvider>
    </QueryClientProvider>,
  );
  await screen.findByRole('heading', { name: heading });
  return view;
}
const structure = (view: ReturnType<typeof render>) => ({
  headings: screen.getAllByRole('heading').map((h) => h.textContent ?? ''),
  links: screen.getAllByRole('link').map((a) => a.textContent ?? ''),
  text: view.container.textContent ?? '',
  image: view.container.querySelector('.k-identity-media img')?.getAttribute('src') ?? '',
});

describe('dashboard is one page for every registered model', () => {
  it('shows the same sections and actions for E52, E72 and a model added later', async () => {
    const seen = [];
    for (const m of registry) {
      const view = await render_([phone(m)], m.name);
      seen.push({ m, ...structure(view) });
      cleanup();
    }
    const generic = (list: string[]) => list.map((t) => t.replace(/E(52|72|99)/g, 'E__'));
    for (const other of seen.slice(1)) {
      expect(generic(other.headings)).toEqual(generic(seen[0]?.headings ?? []));
      expect(other.links).toEqual(seen[0]?.links);
      expect(other.image).toContain(
        other.m.image.replace('/phones/', 'phones/').replace('.png', ''),
      );
    }
    for (const title of [
      'Хранилище',
      'Операции SymPort за 7 дней',
      'Состояние устройства',
      'Журнал устройства',
    ])
      expect(seen[0]?.headings).toContain(title);
  });

  it('subtitle uses the registry geometry, including a later landscape/touch model', async () => {
    const e72 = await render_([phone(registry[1] as never)], 'Nokia E72');
    expect(structure(e72).text).toContain('320×240 (альбомная)');
    cleanup();
    const e99 = await render_([phone(registry[2] as never)], 'Nokia E99');
    expect(structure(e99).text).toContain(
      'Symbian 9.4 · S60 5th · Сенсорный экран · 360×640 (книжная)',
    );
  });

  it('labels a documented model that has no registered artwork instead of inventing a picture', async () => {
    const e71 = {
      ...phone(registry[0] as never),
      name: 'Nokia E71',
      model: 'Nokia E71 (RM-346)',
      model_profile: {
        id: 'nokia-e71',
        name: 'Nokia E71',
        image: null,
        screen: null,
        s60: '3rd FP1',
        symbian: '9.2',
        input: null,
      },
    };
    const view = await render_([e71], 'Nokia E71');
    expect(screen.getByRole('img', { name: /Обобщённая иллюстрация/ })).toBeTruthy();
    expect(view.container.querySelector('.k-identity-media img')).toBeNull();
    expect(structure(view).text).toContain('пока нет изображения');
    expect(structure(view).text).toContain('Symbian 9.2 · S60 3rd FP1');
    expect(structure(view).text).not.toContain('240×320');
  });

  it('offers only registered artwork as an illustration when the model is not identified', async () => {
    const view = await render_(
      [{ id: 'gammu', transport: 'gammu', connected: true, capabilities: [], model: null }],
      'Телефон Symbian',
    );
    expect(structure(view).text).toContain('Только иллюстрация');
    const buttons = screen
      .getAllByRole('button')
      .filter((b) => /^E\d\d$/.test(b.textContent ?? ''));
    expect(buttons.map((b) => b.textContent)).toEqual(['E52', 'E72', 'E99']);
    fireEvent.click(buttons[1] as HTMLElement);
    expect(view.container.querySelector('.k-chooser img')?.getAttribute('alt')).toContain(
      'Иллюстрация',
    );
  });
});

describe('states', () => {
  it('shows a useful empty state with the wizard as the call to action before any connection', async () => {
    const view = await render_([], 'Телефон не подключён');
    expect(
      screen.getByRole('link', { name: 'Открыть мастер подключения' }).getAttribute('href'),
    ).toBe('#phone/connection');
    expect(view.container.querySelector('.k-metric')).toBeNull();
    expect(
      view.container.querySelector('svg.MuiChartsSurface-root, .MuiChartsSurface-root'),
    ).toBeNull();
  });

  it('draws only measured values and lists the rest as not reported', async () => {
    const view = await render_(
      [phone(registry[0] as never, { battery: null, signal: null })],
      'Nokia E52',
    );
    const text = structure(view).text;
    expect(text).toContain('Не сообщается этим транспортом: батарея, сигнал');
    expect(view.container.querySelectorAll('.k-metric').length).toBeLessThan(3);
    expect(text).not.toMatch(/Заряд батареи/);
  });

  it('never invents a trend or a zero for a missing reading', async () => {
    const view = await render_([phone(registry[0] as never, { battery: null })], 'Nokia E52');
    const text = structure(view).text.toLowerCase();
    for (const banned of ['вчера', 'yesterday', 'лучше чем']) expect(text).not.toContain(banned);
    expect(text).not.toContain('заряд батареи0');
  });

  it('shows the battery/signal chart only with at least three real samples', async () => {
    const client = new ApiClient(() => 'token');
    vi.spyOn(client, 'discover').mockResolvedValue({
      devices: [phone(registry[0] as never)],
      models: registry,
      limitations: {},
    } as never);
    vi.spyOn(client, 'history').mockResolvedValue({ operations: [] });
    vi.spyOn(client, 'get').mockResolvedValue({ backups: [] } as never);
    const request = vi.spyOn(client, 'request').mockResolvedValue({
      measurements: [
        { time: '2026-11-04T10:00:00Z', battery: 80, signal: 50 },
        { time: '2026-11-04T11:00:00Z', battery: 79, signal: null },
      ],
    } as never);
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ApiProvider client={client}>
          <PreferencesProvider>
            <Dashboard />
          </PreferencesProvider>
        </ApiProvider>
      </QueryClientProvider>,
    );
    await screen.findByRole('heading', { name: 'Nokia E52' });
    await vi.waitFor(() => expect(request).toHaveBeenCalled());
    expect(screen.queryByText('Батарея и сигнал')).toBeNull();
  });
});
