import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import { ModelProfileSelect } from '../components/ModelProfileSelect';
import { targetForProfile, profileById } from '../components/deviceProfiles';
import { DeviceFrame } from '../components/DeviceFrame';
import CfwPreparation from '../features/CfwPreparation';
const sources = {
  sources: [
    {
      id: 'reborn-n8-e7',
      family: 'fixture',
      title: { en: 'Test source', ru: 'Тестовый источник' },
      kind: 'fixture',
      platform: 'Symbian Belle',
      models: [],
      release: { version: 'fixture', date: 'fixture' },
      links: {},
      limitations: [],
      distribution: 'test-only',
      symport: { 'nokia-n8': 'research-only', 'nokia-e7': 'research-only' },
      advisories: [],
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = '';
});
describe('N8/E7 are upgradeable targets, with no guessed Belle or themes', () => {
  it.each(['nokia-n8', 'nokia-e7'])('selects %s without assigning an installed OS', (id) => {
    const change = vi.fn();
    render(
      <PreferencesProvider>
        <ModelProfileSelect target={targetForProfile('nokia-e52')} onTarget={change} />
      </PreferencesProvider>,
    );
    fireEvent.change(screen.getByRole('combobox'), { target: { value: id } });
    expect(change).toHaveBeenCalledWith({
      model: profileById(id)?.target_model,
      os: '',
      rm: '',
      firmware: '',
    });
  });
  it.each(['nokia-n8', 'nokia-e7'])(
    'keeps %s selected when a release is explicitly supplied',
    (id) => {
      render(
        <PreferencesProvider>
          <ModelProfileSelect
            target={{ ...targetForProfile(id), os: 'Belle Refresh' }}
            onTarget={() => {}}
          />
        </PreferencesProvider>,
      );
      expect(screen.getByRole('combobox')).toHaveValue(id);
    },
  );
  it.each(['nokia-n8', 'nokia-e7'])(
    'does not turn the %s handset artwork into a theme preview',
    (id) => {
      const { container } = render(
        <DeviceFrame profile={id}>
          <rect />
        </DeviceFrame>,
      );
      expect(profileById(id)?.artwork).toBeTruthy();
      expect(container).toBeEmptyDOMElement();
    },
  );
  it.each(['en', 'ru'])(
    'prepares a user VPL in %s and hides stale reports after edits',
    async (language) => {
      localStorage.setItem('symport-language', language);
      location.hash = '#tools/cfw?profile=nokia-e7';
      const requests: Record<string, unknown>[] = [];
      vi.stubGlobal(
        'fetch',
        vi.fn(async (_url: string, init: RequestInit) => {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          if (body.action === 'discover')
            return new Response(JSON.stringify({ devices: [], models: [], limitations: {} }));
          requests.push(body);
          return new Response(
            JSON.stringify({
              schema: 'symport.cfw-preparation/1',
              profile: 'nokia-e7',
              source: 'reborn-n8-e7',
              package: { rm: 'RM-626' },
              metadata_basis: 'user VPL',
              checks: [],
              status: 'research-only',
              statement: 'Read-only',
              flashing: 'unsupported',
              physical_device: 'not-tested',
            }),
          );
        }),
      );
      render(
        <QueryClientProvider
          client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
        >
          <ApiProvider client={new ApiClient(() => 'token')}>
            <PreferencesProvider>
              <CfwPreparation sources={sources.sources} images={[]} />
            </PreferencesProvider>
          </ApiProvider>
        </QueryClientProvider>,
      );
      const upload = screen.getByLabelText(
        language === 'en'
          ? 'VPL manifest (optional, 512 KiB)'
          : 'Манифест VPL (необязательно, 512 КиБ)',
      );
      await userEvent.upload(
        upload,
        new File(['<VariantPackingList/>'], 'own.vpl', { type: 'application/xml' }),
      );
      await userEvent.click(
        screen.getByRole('button', {
          name:
            language === 'en'
              ? 'Analyze preparation (dry run)'
              : 'Проверить подготовку (пробный прогон)',
        }),
      );
      await screen.findByRole('link', {
        name: language === 'en' ? 'Download JSON report' : 'Скачать JSON-отчёт',
      });
      expect(requests[0]?.manifest).toBeTruthy();
      expect(requests[0]?.profile).toBe('nokia-e7');
      expect(screen.queryByRole('button', { name: /^(Flash|Прошить)$/ })).not.toBeInTheDocument();
      fireEvent.change(screen.getByLabelText(language === 'en' ? 'Package RM' : 'RM пакета'), {
        target: { value: 'RM-596' },
      });
      expect(
        screen.queryByRole('link', {
          name: language === 'en' ? 'Download JSON report' : 'Скачать JSON-отчёт',
        }),
      ).not.toBeInTheDocument();
    },
  );
});
