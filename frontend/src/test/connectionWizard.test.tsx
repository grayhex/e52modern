import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { deviceSchema } from '../api/contracts';
import { ApiProvider, PreferencesProvider } from '../state/app';
import ConnectionWizard from '../features/ConnectionWizard';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const e52 = deviceSchema.parse({
  id: 'usb',
  name: 'Nokia E52',
  model: 'Nokia E52 (RM-469)',
  rm: 'RM-469',
  firmware: '071.004',
  transport: 'gammu',
  connection_kind: 'gammu-usb',
  connected: true,
  capabilities: [],
  capability_matrix: {
    'identity.read': {
      mode: 'read',
      status: 'available',
      attempt: 'verified',
      source: 'gammu-native:details',
      evidence: 'ok',
      checked_at: '2026-11-04T10:00:00+00:00',
    },
  },
});

function setup(options: {
  mode: 'direct' | 'windows-bridge';
  connected?: boolean;
  devices?: unknown[];
}) {
  const client = new ApiClient(() => 't');
  const connection = vi
    .spyOn(client, 'connection')
    .mockImplementation((action) =>
      Promise.resolve(
        action === 'enable'
          ? { mode: 'windows-bridge', connected: false, relay_token: 'a'.repeat(43) }
          : { mode: options.mode, connected: options.connected ?? true },
      ),
    );
  vi.spyOn(client, 'discover').mockResolvedValue({
    devices: (options.devices ?? []) as never,
    limitations: {},
  });
  vi.spyOn(client, 'request').mockResolvedValue({
    serial: [{ port: 'COM3' }],
    bluetooth: [],
    volumes: [],
    usb: [],
    diagnostics: [],
  } as never);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ApiProvider client={client}>
        <PreferencesProvider>
          <ConnectionWizard />
        </PreferencesProvider>
      </ApiProvider>
    </QueryClientProvider>,
  );
  return { connection };
}
const step = (id: string) => document.querySelector(`[data-step="${id}"]`) as HTMLElement;

describe('ConnectionWizard', () => {
  it('walks to a verified connection over local transports without writing anything', async () => {
    setup({ mode: 'direct', devices: [e52] });
    await waitFor(() => expect(step('capabilities').dataset.status).toBe('success'));
    expect(step('bridge').dataset.status).toBe('skipped');
    expect(step('identify').textContent).toContain('RM-469');
    await waitFor(() =>
      expect(screen.getByText(/Nokia идентифицирована/).closest('li')?.dataset.on).toBe('true'),
    );
    // The selected connection is picked automatically when it is the only identified phone.
    await waitFor(() => expect(screen.getByRole('radio', { checked: true })).toBeTruthy());
    expect(
      document.querySelector('a[download="symport-first-connection-report.json"]'),
    ).toBeTruthy();
  });

  it('reports a Bridge that is not running and offers concrete fixes', async () => {
    setup({ mode: 'windows-bridge', connected: false });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    fireEvent.click(await screen.findByRole('button', { name: 'Проверить Bridge' }));
    await waitFor(() => expect(step('bridge').dataset.status).toBe('failed'));
    expect(step('bridge').textContent).toContain('bridge-not-found');
    expect(step('bridge').textContent).toContain('SymPortBridge.exe');
  });

  it('turns a declined approval into its own failure and releases the lease', async () => {
    const { connection } = setup({ mode: 'windows-bridge', connected: false });
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ error: 'Access was declined on the PC' }), { status: 403 }),
        ),
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Запросить доступ' }));
    await waitFor(() => expect(step('pairing').dataset.status).toBe('failed'));
    expect(step('pairing').textContent).toContain('pair-declined');
    expect(connection).toHaveBeenCalledWith('disconnect');
  });

  it('retry only re-reads: diagnostics never call a write action', async () => {
    const { connection } = setup({ mode: 'direct', devices: [e52] });
    await waitFor(() => expect(step('identify').dataset.status).toBe('success'));
    fireEvent.click(screen.getByRole('button', { name: /Повторить диагностику/ }));
    await waitFor(() => expect(connection.mock.calls.length).toBeGreaterThan(1));
    for (const [action] of connection.mock.calls) expect(['status']).toContain(action);
  });

  it('shows the lost device after a phone that answered disappears', async () => {
    const client = new ApiClient(() => 't');
    vi.spyOn(client, 'connection').mockResolvedValue({ mode: 'direct', connected: true });
    let answer = true;
    vi.spyOn(client, 'discover').mockImplementation(() =>
      Promise.resolve({
        devices: answer ? [e52] : [{ ...e52, connected: false }],
        limitations: {},
      }),
    );
    vi.spyOn(client, 'request').mockResolvedValue({
      serial: [],
      bluetooth: [],
      volumes: [],
      usb: [],
      diagnostics: [],
    } as never);
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ApiProvider client={client}>
          <PreferencesProvider>
            <ConnectionWizard />
          </PreferencesProvider>
        </ApiProvider>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(step('identify').dataset.status).toBe('success'));
    answer = false;
    fireEvent.click(screen.getByRole('button', { name: /Повторить диагностику/ }));
    await waitFor(() => expect(step('identify').textContent).toContain('device-lost'));
  });
});
