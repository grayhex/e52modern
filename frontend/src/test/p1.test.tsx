import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, it, expect, vi } from 'vitest';
import type { ReactNode } from 'react';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Collections from '../features/Collections';
import ThemeStudio from '../features/ThemeStudio';
import { themeProjectSchema } from '../api/p1';
const palette = {
  bg: '#ffffff',
  text: '#112233',
  status: '#ffffff',
  hl_fill_bot: '#ccddee',
  hl_text: '#000000',
  accent: '#124191',
  panel: '#ffffff',
  line: '#aaaaaa',
  softkey: '#eeeeee',
  softkey_text: '#000000',
};
function mount(view: ReactNode, handle: (body: Record<string, unknown>) => unknown) {
  localStorage.setItem('symport-language', 'en');
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async (_url: string, init: RequestInit) =>
        new Response(
          JSON.stringify(handle(JSON.parse(String(init.body)) as Record<string, unknown>)),
          { status: 200 },
        ),
    ),
  );
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <ApiProvider client={new ApiClient(() => 'session')}>
        <PreferencesProvider>{view}</PreferencesProvider>
      </ApiProvider>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());
describe('P1 review and recovery', () => {
  it('requires partial acknowledgement and explicit consent, then consumes the reviewed plan', async () => {
    const requests: Record<string, unknown>[] = [];
    const c = {
      id: 'a'.repeat(24),
      schema: 'symport.collection/1',
      name: 'My kit',
      profile: 'nokia-e52',
      apps: [{ id: 'example', version: '1', artifacts: [] }],
    };
    mount(<Collections />, (body) => {
      requests.push(body);
      switch (body.action) {
        case 'collections':
          return {
            collections: [c],
            templates: [],
            profiles: {
              'nokia-e52': {
                model: 'Nokia E52',
                symbian: '9.3',
                s60: '3rd FP2',
                screen: [240, 320],
              },
            },
          };
        case 'list':
          return { apps: [], sets: {}, jobs: [], research: [] };
        case 'discover':
          return {
            devices: [
              { id: 'phone', transport: 'mounted', connected: true, capabilities: ['transfer'] },
            ],
            limitations: {},
          };
        case 'recovery-plan':
          return {
            collection: 'My kit',
            profile: 'nokia-e52',
            target: { model: 'Nokia E52' },
            source_profile: 'nokia-e52',
            geometry_changed: false,
            preview_sha256: 'reviewed-hash',
            rows: [
              {
                id: 'example',
                name: 'Example',
                status: 'ready-for-transfer',
                reasons: [],
                sources: [],
                compatibility: 'untested',
              },
            ],
            transfer_ids: ['example'],
            problems: [],
            partial: true,
            instructions: [],
            identity: null,
          };
        case 'recovery-transfer':
          return { status: 'queued-not-installed' };
        default:
          throw Error(String(body.action));
      }
    });
    await screen.findByRole('option', { name: 'My kit · nokia-e52' });
    await userEvent.selectOptions(screen.getByLabelText('Saved collection'), c.id);
    await userEvent.selectOptions(await screen.findByLabelText('Connection'), 'phone');
    await userEvent.click(screen.getByRole('button', { name: 'Preview recovery' }));
    const transfer = await screen.findByRole('button', { name: 'Transfer recovery set' });
    expect(transfer).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: /Transfer only available/ }));
    await userEvent.click(transfer);
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    expect(requests.some((r) => r.action === 'recovery-transfer')).toBe(false);
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    await waitFor(() =>
      expect(requests.find((r) => r.action === 'recovery-transfer')).toMatchObject({
        preview_sha256: 'reviewed-hash',
        confirm: true,
        ack_partial: true,
        device: 'phone',
      }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Transfer recovery set' }),
      ).not.toBeInTheDocument(),
    );
  });
  it('builds for the chosen geometry only after unsigned acknowledgement and invalidates stale export after edits', async () => {
    const requests: Record<string, unknown>[] = [];
    let project = themeProjectSchema.parse({
      id: 'b'.repeat(24),
      name: 'My Nokia Theme',
      profile: 'nokia-e72',
      uid: 0xe1000001,
      mode: 'clear',
      revision: 1,
      palette,
      wallpaper: true,
      icons: {},
      resources: [],
      blockers: [],
    });
    let created = false;
    mount(<ThemeStudio />, (body) => {
      requests.push(body);
      switch (body.action) {
        case 'list':
          return {
            projects: created ? [project] : [],
            profiles: { 'nokia-e72': [320, 240] },
            palettes: { light: palette },
            limitations: [],
          };
        case 'create':
          created = true;
          return project;
        case 'project':
          return project;
        case 'build':
          project = themeProjectSchema.parse({
            ...project,
            built_revision: project.revision,
            build: {
              status: 'static-checked',
              sha256: 'c'.repeat(64),
              size: 100,
              signature: 'unsigned',
            },
          });
          return project;
        case 'asset':
          return { name: 'wallpaper.png', content: 'iVBORw0KGgo=', mime: 'image/png' };
        case 'wallpaper-remove':
          project = themeProjectSchema.parse({
            ...project,
            wallpaper: false,
            revision: project.revision + 1,
            built_revision: null,
          });
          return project;
        case 'save':
          project = themeProjectSchema.parse({
            ...project,
            revision: project.revision + 1,
            built_revision: null,
            palette: body.palette,
          });
          return project;
        default:
          throw Error(String(body.action));
      }
    });
    await userEvent.selectOptions(screen.getByLabelText('Screen profile'), 'nokia-e72');
    await userEvent.click(screen.getByRole('button', { name: 'Create editable CLEAR theme' }));
    const build = await screen.findByRole('button', { name: 'Build & statically validate SIS' });
    expect(build).toBeDisabled();
    expect(requests.find((r) => r.action === 'create')).toMatchObject({ profile: 'nokia-e72' });
    expect(screen.getByRole('img', { name: 'Schematic theme preview 320×240' })).toHaveAttribute(
      'viewBox',
      '0 0 320 240',
    );
    await userEvent.click(screen.getByRole('checkbox', { name: /I understand the unsigned/ }));
    await userEvent.click(build);
    expect(await screen.findByRole('button', { name: 'Export SIS' })).toBeEnabled();
    expect(requests.find((r) => r.action === 'build')).toMatchObject({
      revision: 1,
      confirm_unsigned: true,
    });
    fireEvent.change(screen.getByLabelText('bg'), { target: { value: '#123456' } });
    await userEvent.click(screen.getByRole('button', { name: 'Reset wallpaper' }));
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Reset wallpaper' })).not.toBeInTheDocument(),
    );
    expect(screen.getByLabelText('bg')).toHaveValue('#123456');
    await userEvent.click(screen.getByRole('button', { name: 'Save palette' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export SIS' })).toBeDisabled());
  });
  it('offers no fictional palette editor for a compiled imported SKN', async () => {
    const project = {
      id: 'd'.repeat(24),
      name: 'Imported',
      profile: 'nokia-e52',
      uid: 0xe1000001,
      mode: 'imported',
      revision: 1,
      palette,
      wallpaper: false,
      icons: {},
      resources: [],
      blockers: [],
    };
    mount(<ThemeStudio />, (body) =>
      body.action === 'list'
        ? { projects: [project], profiles: {}, palettes: { light: palette }, limitations: [] }
        : project,
    );
    await screen.findByRole('option', { name: /Imported · nokia-e52/ });
    await userEvent.selectOptions(screen.getByLabelText('Project'), project.id);
    expect(await screen.findByText(/This is a compiled theme/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save palette' })).not.toBeInTheDocument();
    expect(screen.getByText(/Imported appearance is not decoded/)).toBeInTheDocument();
  });
});
