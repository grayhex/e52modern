import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { blockedReason, connectionKey, unverifiedReason } from '../api/capabilities';
import { deviceSchema, type CapabilityState, type Device } from '../api/contracts';
import { keys, useCapabilityGuard, useDevices } from '../api/queries';
import { supports } from '../components/ui';
import CapabilityMatrix from '../components/CapabilityMatrix';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Dashboard from '../features/Dashboard';

const at = '2026-11-04T10:00:00+00:00';
const state = (
  status: CapabilityState['status'],
  mode: CapabilityState['mode'] = 'read',
  attempt?: CapabilityState['attempt'],
  evidence = 'because',
): CapabilityState => ({
  mode,
  status,
  attempt:
    attempt ??
    (status === 'available'
      ? 'verified'
      : status === 'not-tested'
        ? mode === 'write'
          ? 'confirmed-only'
          : 'unverified'
        : 'blocked'),
  source: 'test-probe',
  evidence,
  checked_at: at,
});
const device = (matrix: Record<string, CapabilityState>, extra: Partial<Device> = {}): Device =>
  deviceSchema.parse({
    id: 'usb',
    name: 'Nokia E52',
    transport: 'gammu',
    connected: true,
    capabilities: ['files', 'contacts-read'], // stale flat list must not override the matrix
    capability_matrix: matrix,
    capability_fingerprint: 'aaaa',
    capabilities_checked_at: at,
    ...extra,
  });

afterEach(cleanup);

function wrap(client: ApiClient, cache: QueryClient, node: React.ReactNode) {
  return (
    <QueryClientProvider client={cache}>
      <ApiProvider client={client}>
        <PreferencesProvider>{node}</PreferencesProvider>
      </ApiProvider>
    </QueryClientProvider>
  );
}

describe('capability matrix is the source of truth', () => {
  it('supports() honours blocked operations even when the flat list lists them', () => {
    const d = device({
      'files.list': state('unsupported', 'read', 'blocked', 'no filesystem'),
      'files.upload': state('not-tested', 'write'),
      'files.stage': state('unsupported', 'write'),
      'packages.opp-push': state('not-tested', 'write'),
    });
    expect(supports(d, 'list')).toBe(false);
    // A write that is not blocked may be attempted after confirmation, but is not "verified".
    expect(supports(d, 'upload')).toBe(true);
    expect(supports(d, 'mkdir')).toBe(false);
    expect(supports(d, 'transfer')).toBe(true);
    expect(supports(d, 'delete')).toBe(false);
  });

  it('explains why an operation is blocked, and stays silent when it may be tried', () => {
    const d = device({
      'contacts.read': state(
        'not-tested',
        'read',
        'blocked',
        'gammu identify does not read stores',
      ),
      'files.list': state('available'),
    });
    expect(blockedReason(d, 'contacts.read')?.evidence).toContain('identify');
    expect(blockedReason(d, 'files.list')).toBeNull();
    expect(blockedReason(d, 'contacts.read', 'files.list')).toBeNull();
    // Missing operation in a reported matrix is "no probe result", never "available".
    expect(blockedReason(d, 'sms.read')?.status).toBe('not-tested');
    // A peer without a matrix gives no reason (legacy behaviour is handled by the backend).
    expect(blockedReason({ ...d, capability_matrix: undefined }, 'contacts.read')).toBeNull();
  });

  it('verified-only workflows are blocked by an unprobed read, with the reason', () => {
    const d = device({
      'contacts.read': state('not-tested', 'read', 'unverified', 'identify reads no store'),
      'calendar.read': state('available'),
    });
    expect(blockedReason(d, 'contacts.read')).toBeNull(); // may be tried
    expect(unverifiedReason(d, 'contacts.read')?.evidence).toContain('identify');
    expect(unverifiedReason(d, 'calendar.read')).toBeNull();
    expect(unverifiedReason(d, 'tasks.read')?.status).toBe('not-tested');
  });

  it('connection key changes with phone, link and connectivity', () => {
    const a = device({});
    expect(connectionKey(a)).not.toBe(connectionKey({ ...a, capability_fingerprint: 'bbbb' }));
    expect(connectionKey(a)).not.toBe(connectionKey({ ...a, connected: false }));
    expect(connectionKey(a)).toBe(connectionKey({ ...a, battery: 5 }));
  });
});

function Harness({ id }: { id: string }) {
  const found = useDevices().data?.devices.find((d) => d.id === id);
  return found ? <CapabilityMatrix device={found} /> : null;
}

describe('CapabilityMatrix', () => {
  it('shows state, evidence, source and time, and rechecks read-only', async () => {
    const before = device({
      'identity.read': state('available', 'read', undefined, 'identify answered'),
      'contacts.read': state('not-tested', 'read', 'blocked', 'store not probed'),
      'sms.send': state('unsupported', 'write', undefined, 'no verified-send profile'),
      'files.upload': state('not-tested', 'write'),
    });
    const after = {
      ...before,
      capability_matrix: {
        ...before.capability_matrix,
        'contacts.read': state('available', 'read', undefined, 'store status answered'),
      },
    };
    const client = new ApiClient(() => 't');
    const recheck = vi.spyOn(client, 'recheck').mockResolvedValue({ device: after });
    const cache = new QueryClient();
    vi.spyOn(client, 'discover').mockResolvedValue({ devices: [before], limitations: {} });
    render(wrap(client, cache, <Harness id="usb" />));
    await screen.findByRole('button', { name: /Перепроверить/ });
    const row = (op: string) => document.querySelector(`tr[data-op="${op}"]`) as HTMLElement;
    expect(row('identity.read').textContent).toContain('Проверено');
    expect(row('identity.read').textContent).toContain('test-probe');
    expect(row('contacts.read').dataset.status).toBe('not-tested');
    expect(row('sms.send').dataset.status).toBe('unsupported');
    expect(row('files.upload').textContent).toContain('Только после подтверждения');
    fireEvent.click(screen.getByRole('button', { name: /Перепроверить/ }));
    await waitFor(() => expect(recheck).toHaveBeenCalledWith('usb'));
    await waitFor(() => expect(row('contacts.read').dataset.status).toBe('available'));
    const cached = cache.getQueryData<{ devices: Device[] }>(keys.devices);
    expect(cached?.devices[0]?.capability_matrix?.['contacts.read']?.status).toBe('available');
  });

  it('refuses to guess when a component reported no matrix', () => {
    const client = new ApiClient(() => 't');
    render(
      wrap(
        client,
        new QueryClient(),
        <CapabilityMatrix device={device({}, { capability_matrix: undefined })} />,
      ),
    );
    expect(screen.getByText(/ни одна служба не считается доступной/)).toBeTruthy();
  });
});

function Guard() {
  useCapabilityGuard();
  const cache = useQueryClient();
  return (
    <button
      onClick={() => void cache.invalidateQueries({ queryKey: keys.devices })}
      data-testid="refresh"
    />
  );
}

describe('cache invalidation on connection change', () => {
  const seed = (cache: QueryClient) => {
    cache.setQueryData(['files', 'usb', ''], { entries: [] });
    cache.setQueryData(['personal', 'usb', 'contacts'], { rows: ['private'] });
    cache.setQueryData(['media', 'usb', ''], { items: [] });
    cache.setQueryData(['files', 'other', ''], { entries: [] });
  };
  async function scenario(next: () => Device[] | Error, expectRemoved: boolean) {
    const client = new ApiClient(() => 't');
    const first = device({ 'files.list': state('available') });
    let call = 0;
    vi.spyOn(client, 'discover').mockImplementation(() => {
      call += 1;
      if (call === 1) return Promise.resolve({ devices: [first], limitations: {} });
      const value = next();
      return value instanceof Error
        ? Promise.reject(value)
        : Promise.resolve({ devices: value, limitations: {} });
    });
    const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(wrap(client, cache, <Guard />));
    await waitFor(() => expect(cache.getQueryData(keys.devices)).toBeTruthy());
    seed(cache);
    cache.setQueryData(['files', 'usb', ''], { entries: [] });
    fireEvent.click(screen.getByTestId('refresh'));
    await waitFor(() => expect(call).toBeGreaterThan(1));
    await waitFor(() =>
      expect(cache.getQueryData(['personal', 'usb', 'contacts']) === undefined).toBe(expectRemoved),
    );
    expect(cache.getQueryData(['files', 'other', ''])).toBeTruthy();
    expect(cache.getQueryData(['media', 'usb', '']) === undefined).toBe(expectRemoved);
  }

  it('keeps caches while the connection is unchanged', async () => {
    await scenario(() => [device({ 'files.list': state('available') })], false);
  });
  it('drops them when another phone answers on the same connection', async () => {
    await scenario(
      () => [device({ 'files.list': state('available') }, { capability_fingerprint: 'e72e' })],
      true,
    );
  });
  it('drops them on disconnect', async () => {
    await scenario(() => [device({}, { connected: false })], true);
  });
  it('drops them when discovery itself fails (Bridge lost)', async () => {
    await scenario(() => new Error('Bridge unreachable'), true);
  });
});

describe('dashboard storage is not mixed between connections', () => {
  const phone = device(
    { 'identity.read': state('available') },
    { model: 'Nokia E52', capability_fingerprint: 'e52a', total: null, free: null },
  );
  const volume = deviceSchema.parse({
    id: 'card',
    name: 'Card',
    transport: 'mounted-volume',
    connected: true,
    capabilities: [],
    total: 8 * 1024 ** 3,
    free: 2 * 1024 ** 3,
  });
  async function open() {
    const client = new ApiClient(() => 't');
    vi.spyOn(client, 'discover').mockResolvedValue({ devices: [phone, volume], limitations: {} });
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
    return render(
      wrap(
        client,
        new QueryClient({ defaultOptions: { queries: { retry: false } } }),
        <Dashboard />,
      ),
    );
  }
  it('shows no phone storage until the user links the volume', async () => {
    localStorage.clear();
    const view = await open();
    await screen.findByText(/не сообщает счётчики/);
    expect(view.container.textContent).not.toContain('2.0 ГиБ');
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'card' } });
    await screen.findByText(/связали с этим телефоном/);
    expect(view.container.textContent).toContain('2.0 ГиБ');
  });
  it('ignores a link made for another phone or firmware', async () => {
    localStorage.setItem(
      'symport-linked-volume',
      JSON.stringify({ phone: 'usb', fingerprint: 'old-phone', volume: 'card' }),
    );
    await open();
    await screen.findByText(/не сообщает счётчики/);
  });
});
