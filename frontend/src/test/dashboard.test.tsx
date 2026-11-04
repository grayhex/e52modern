import { render, screen, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Dashboard from '../features/Dashboard';

const phone = (model: 'E52' | 'E72', extra: Record<string, unknown> = {}) => ({
  id: 'gammu',
  name: `Nokia ${model}`,
  model: `Nokia ${model} (RM-000)`,
  rm: 'RM-000',
  transport: 'gammu',
  connected: true,
  capabilities: ['contacts-read'],
  model_profile: {
    name: `Nokia ${model}`,
    image: model === 'E72' ? '/phones/nokia-e72.png' : '/phones/nokia-e52-silver.png',
    screen:
      model === 'E72'
        ? { width: 320, height: 240, orientation: 'landscape' }
        : { width: 240, height: 320, orientation: 'portrait' },
    s60: '3rd FP2',
    symbian: '9.3',
    input: model === 'E72' ? 'qwerty' : 'numeric-keypad',
  },
  ...extra,
});

async function structure(devices: unknown[]) {
  const client = new ApiClient(() => 'token');
  vi.spyOn(client, 'discover').mockResolvedValue({ devices, limitations: {} } as never);
  vi.spyOn(client, 'history').mockResolvedValue({ operations: [] });
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
  await screen.findByRole('heading', { name: /Nokia E(52|72)/ });
  const out = {
    headings: screen.getAllByRole('heading').map((h) => h.textContent ?? ''),
    links: screen.getAllByRole('link').map((a) => a.textContent ?? ''),
    metrics: [...view.container.querySelectorAll('.MuiCard-root .MuiTypography-caption')].map(
      (n) => n.textContent ?? '',
    ),
    charts: view.container.querySelectorAll('svg').length > 0,
    text: view.container.textContent ?? '',
    image: view.container.querySelector('img')?.getAttribute('src') ?? '',
  };
  cleanup();
  return out;
}

describe('dashboard is identical for E52 and E72', () => {
  it('shows the same sections, tiles and actions; only the model-specific values differ', async () => {
    const e52 = await structure([phone('E52')]);
    const e72 = await structure([phone('E72')]);
    const generic = (list: string[]) => list.map((t) => t.replace(/E(52|72)/g, 'E__'));
    expect(generic(e72.headings)).toEqual(generic(e52.headings));
    expect(e72.links).toEqual(e52.links);
    expect(generic(e72.metrics).length).toBeGreaterThan(8);
    expect(generic(e72.metrics)).toEqual(
      generic(e52.metrics).map((t) => t.replace(/240×320 \(книжная\)/, '320×240 (альбомная)')),
    );
    expect(e52.headings).toContain('Nokia E52');
    expect(e72.headings).toContain('Nokia E72');
    expect(e52.image).toContain('nokia-e52');
    expect(e72.image).toContain('nokia-e72');
    expect(e52.charts && e72.charts).toBe(true);
  });
  it('keeps every section when the connection reports no counters at all', async () => {
    const bare = await structure([phone('E72')]);
    for (const title of [
      'Хранилище',
      'Операции SymPort за 7 дней',
      'Быстрые действия',
      'Состояние устройства',
      'Журнал устройства',
    ])
      expect(bare.headings).toContain(title);
  });
  it('does not borrow storage from an unrelated volume when the identified phone has none', async () => {
    const volume = {
      id: 'card',
      transport: 'mounted-volume',
      connected: true,
      capabilities: ['files'],
      total: 8 * 1024 ** 3,
      free: 2 * 1024 ** 3,
    };
    const out = await structure([phone('E52'), volume]);
    // The card is a separate connection: its counters appear only after the user links it.
    expect(out.text).not.toContain('6.0 ГиБ');
    expect(out.text).toContain('Это подключение не сообщает счётчики накопителя');
  });
});
