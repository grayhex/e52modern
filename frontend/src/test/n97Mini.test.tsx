import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import ThemeStudio from '../features/ThemeStudio';
import { ModelProfileSelect } from '../components/ModelProfileSelect';
import { profileById, targetForProfile } from '../components/deviceProfiles';
import { DeviceFrame } from '../components/DeviceFrame';
import data from '../../../symport/phone/device_models.json';

afterEach(() => {
  vi.unstubAllGlobals();
  location.hash = '';
});
describe('N97 mini targets and theme exclusion', () => {
  it('selects 9.4, preserves both orientations and uses its own handset artwork', () => {
    const model = profileById('nokia-n97-mini');
    expect(targetForProfile('nokia-n97-mini')).toEqual({
      model: 'Nokia N97 mini',
      os: '9.4',
      rm: '',
      firmware: '',
    });
    expect(model?.image).toBe('/phones/nokia-n97-mini.png');
    expect(model?.artwork).toBeNull(); // Decorative handset, not an enabled theme preview.
    expect(model?.screen_modes).toEqual([
      { width: 360, height: 640, orientation: 'portrait' },
      { width: 640, height: 360, orientation: 'landscape' },
    ]);
    localStorage.setItem('symport-language', 'en');
    const change = vi.fn();
    render(
      <PreferencesProvider>
        <ModelProfileSelect target={targetForProfile('nokia-e52')} onTarget={change} />
      </PreferencesProvider>,
    );
    fireEvent.change(screen.getByLabelText('Model profile'), {
      target: { value: 'nokia-n97-mini' },
    });
    expect(change).toHaveBeenCalledWith({
      model: 'Nokia N97 mini',
      os: '9.4',
      rm: '',
      firmware: '',
    });
  });
  it('does not create a fake N97 mini theme frame', () => {
    const { container } = render(
      <DeviceFrame profile="nokia-n97-mini">
        <rect />
      </DeviceFrame>,
    );
    expect(container).toBeEmptyDOMElement();
  });
  it.each(['en', 'ru'])(
    'explains unavailable themes in %s and never sends create/import',
    async (language) => {
      localStorage.setItem('symport-language', language);
      location.hash = '#personalize/theme-editor?profile=nokia-n97-mini';
      const calls: Record<string, unknown>[] = [];
      vi.stubGlobal(
        'fetch',
        vi.fn(async (_url: string, init: RequestInit) => {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          calls.push(body);
          if (body.action === 'discover')
            return new Response(
              JSON.stringify({ devices: [], models: data.models, limitations: {} }),
            );
          if (body.action === 'list')
            return new Response(
              JSON.stringify({
                projects: [],
                profiles: { 'nokia-e52': [240, 320], 'nokia-e72': [320, 240] },
                palettes: { light: {} },
                limitations: [],
              }),
            );
          throw Error('Unexpected mutation: ' + String(body.action));
        }),
      );
      const cache = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      });
      render(
        <QueryClientProvider client={cache}>
          <ApiProvider client={new ApiClient(() => 'test')}>
            <PreferencesProvider>
              <ThemeStudio />
            </PreferencesProvider>
          </ApiProvider>
        </QueryClientProvider>,
      );
      await screen.findByText(language === 'en' ? 'Not supported yet' : 'Пока не поддерживается');
      const create = screen.getByRole('button', {
        name:
          language === 'en' ? 'Create editable CLEAR theme' : 'Создать редактируемую тему CLEAR',
      });
      expect(create).toBeDisabled();
      expect(
        screen.getByLabelText(
          language === 'en' ? 'Import SIS theme (8 MiB)' : 'Импорт SIS-темы (8 МиБ)',
        ),
      ).toBeDisabled();
      fireEvent.click(create);
      await waitFor(() => expect(calls.some((c) => c.action === 'discover')).toBe(true));
      expect(calls.some((c) => ['create', 'import', 'build'].includes(String(c.action)))).toBe(
        false,
      );
      expect(screen.queryByRole('img', { name: /360×640/ })).not.toBeInTheDocument();
    },
  );
});
