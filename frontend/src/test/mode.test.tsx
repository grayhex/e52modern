import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Sidebar from '../nav/Sidebar';
import Topbar from '../nav/Topbar';
import DeveloperOnly from '../nav/DeveloperOnly';
import { allItems, groups, isDeveloperRoute, visibleGroups } from '../nav/routes';

function shell(ui: React.ReactNode) {
  const client = new ApiClient(() => 'token');
  vi.spyOn(client, 'discover').mockResolvedValue({ devices: [], limitations: {} } as never);
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
const sidebar = (
  <Sidebar
    route="phone/overview"
    compact={false}
    onCompact={noop}
    mobile={false}
    open={false}
    onClose={noop}
    openGroups={['phone', 'apps', 'personalize', 'revive', 'tools', 'dev']}
    onGroups={noop}
  />
);

beforeEach(() => localStorage.clear());

describe('user and developer modes', () => {
  it('keeps everyday functions in user mode and hides development, firmware and experimental pages', () => {
    const ids = visibleGroups('user').flatMap((g) => g.items.map((i) => i.id));
    for (const id of [
      'phone/files',
      'phone/contacts',
      'phone/backups',
      'apps/catalog',
      'personalize/themes',
      'personalize/ringtones',
      'revive/network',
      'tools/diagnostics',
      'tools/activity',
    ])
      expect(ids).toContain(id);
    for (const id of [
      'dev/lab',
      'dev/sdk',
      'tools/firmware',
      'tools/cfw',
      'tools/jailbreak',
      'tools/certificates',
      'apps/dependencies',
      'revive/reborn',
      'revive/addons',
    ])
      expect(ids).not.toContain(id);
    expect(visibleGroups('user').map((g) => g.id)).not.toContain('dev');
  });
  it('developer mode shows the whole registry', () => {
    expect(visibleGroups('developer')).toBe(groups);
    expect(visibleGroups('developer').flatMap((g) => g.items)).toHaveLength(
      allItems.filter((i) => i.id !== 'phone/connection').length,
    );
  });
  it('knows which routes need developer mode', () => {
    expect(isDeveloperRoute('dev/lab')).toBe(true);
    expect(isDeveloperRoute('tools/firmware')).toBe(true);
    expect(isDeveloperRoute('phone/files')).toBe(false);
    expect(isDeveloperRoute('phone/connection')).toBe(false);
    expect(isDeveloperRoute('nope')).toBe(false);
  });
  it('starts in user mode and switches the menu with the mode switch, remembering the choice', async () => {
    shell(sidebar);
    const menu = screen.getByRole('navigation', { name: 'Разделы' });
    expect(within(menu).queryByRole('link', { name: 'Emulator Lab' })).toBeNull();
    expect(within(menu).queryByRole('link', { name: 'Firmware & ROM Explorer' })).toBeNull();
    expect(within(menu).getByRole('link', { name: 'Файловый менеджер' })).toBeInTheDocument();
    const users = screen.getByRole('button', { name: 'Пользователь' });
    expect(users).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(screen.getByRole('button', { name: 'Разработчик' }));
    expect(within(menu).getByRole('link', { name: 'Emulator Lab' })).toBeInTheDocument();
    expect(within(menu).getByRole('link', { name: 'Firmware & ROM Explorer' })).toBeInTheDocument();
    expect(localStorage.getItem('symport-mode')).toBe('developer');
    await userEvent.click(screen.getByRole('button', { name: 'Пользователь' }));
    expect(within(menu).queryByRole('link', { name: 'Emulator Lab' })).toBeNull();
    expect(localStorage.getItem('symport-mode')).toBe('user');
  });
  it('restores a saved developer mode and shows the badge in the top bar', () => {
    localStorage.setItem('symport-mode', 'developer');
    shell(<Topbar route="dev/lab" mobile={false} menuOpen={false} onMenu={noop} />);
    expect(screen.getByTestId('mode-badge')).toHaveTextContent('Режим разработчика');
  });
  it('starts in developer mode when the deployment asks for it, but a saved choice wins', () => {
    const meta = document.createElement('meta');
    meta.name = 'symport-default-mode';
    meta.content = 'developer';
    document.head.append(meta);
    try {
      shell(<Topbar route="dev/lab" mobile={false} menuOpen={false} onMenu={noop} />);
      expect(screen.getByTestId('mode-badge')).toBeInTheDocument();
    } finally {
      meta.remove();
    }
  });
  it('explains a developer page opened in user mode and offers to turn the mode on', async () => {
    shell(<DeveloperOnly route="tools/firmware" />);
    expect(screen.getByText(/Этот раздел — для режима разработчика/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Включить режим разработчика/ }));
    expect(localStorage.getItem('symport-mode')).toBe('developer');
  });
});
