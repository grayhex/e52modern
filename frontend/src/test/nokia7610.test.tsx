import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Dashboard from '../features/Dashboard';
import { ModelProfileSelect } from '../components/ModelProfileSelect';
import {
  deviceProfiles,
  platformLabel,
  profileById,
  targetForProfile,
} from '../components/deviceProfiles';
import { DeviceFrame } from '../components/DeviceFrame';
import { issueText } from '../components/depStatus';

afterEach(() => {
  cleanup();
  localStorage.clear();
});

const p7610 = profileById('nokia-7610');

/** The row a transport reports: identity only, with no telemetry and no probed personal data store. */
const identityOnly = {
  id: 'gammu',
  name: 'Nokia 7610',
  model: '7610',
  rm: null,
  firmware: null,
  transport: 'gammu',
  connected: true,
  battery: null,
  signal: null,
  capabilities: [],
  model_profile: p7610,
};

async function dashboard(device: Record<string, unknown>) {
  const client = new ApiClient(() => 'token');
  vi.spyOn(client, 'discover').mockResolvedValue({
    devices: [device],
    models: [p7610],
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
  await screen.findByRole('heading', { name: 'Nokia 7610' });
  return view;
}

describe('Nokia 7610 is its own S60 2nd Edition model', () => {
  it('is registered with its own artwork, geometry and platform, and no theme support', () => {
    expect(p7610).toBeTruthy();
    expect(p7610?.image).toBe('/phones/nokia-7610.png');
    expect(p7610?.screen).toEqual({ width: 176, height: 208, orientation: 'portrait' });
    expect(p7610?.s60).toBe('2nd');
    expect(p7610?.symbian).toBe('7.0s');
    expect(p7610?.hardware).toBe('not-tested');
    expect(p7610?.theme_studio.status).toBe('unsupported');
    expect(deviceProfiles.some((p) => p.id === 'nokia-7610')).toBe(true);
    expect(platformLabel('2nd')).toBe('S60 2nd');
  });

  it('can be chosen as a target without assigning firmware, RM or a measured OS', () => {
    const change = vi.fn();
    render(
      <PreferencesProvider>
        <ModelProfileSelect target={targetForProfile('nokia-e52')} onTarget={change} />
      </PreferencesProvider>,
    );
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'nokia-7610' } });
    expect(change).toHaveBeenCalledWith({ model: 'Nokia 7610', os: '7.0s', rm: '', firmware: '' });
    expect(screen.getByRole('option', { name: /Nokia 7610 · 176×208 \/ S60 2nd/ })).toBeTruthy();
  });

  it('does not turn the handset illustration into a theme preview', () => {
    const { container } = render(
      <DeviceFrame profile="nokia-7610">
        <rect />
      </DeviceFrame>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the model, platform and transport, and invents no telemetry or stores', async () => {
    const view = await dashboard(identityOnly);
    const text = view.container.textContent ?? '';
    expect(text).toContain('Symbian 7.0s');
    expect(text).toContain('S60 2nd');
    expect(text).toContain('176×208 (книжная)');
    expect(text).toContain('gammu');
    const image = view.container.querySelector('.k-identity-media img')?.getAttribute('src') ?? '';
    expect(image).toContain('phones/nokia-7610');
    // Battery and signal were not reported: no zero and no percentage is drawn.
    expect(text).not.toMatch(/\b0%/);
    expect(text).not.toContain('82%');
    expect(text).toContain('Не проверено');
    expect(text).toContain('Нет данных');
  });

  it('keeps the labelled "not tested" statuses for an identity-only connection', async () => {
    const view = await dashboard(identityOnly);
    const status = view.container.querySelector('.k-panel')?.textContent ?? '';
    expect(status.length).toBeGreaterThan(0);
    expect(view.container.textContent).not.toMatch(/Подтверждено операций\s*[1-9]/);
  });

  it('explains the legacy platform in package analysis in both languages', () => {
    expect(issueText['legacy-platform-not-assessed']?.[0]).toMatch(/not assessed/);
    expect(issueText['legacy-platform-not-assessed']?.[1]).toMatch(/не оценивается/);
  });
});
