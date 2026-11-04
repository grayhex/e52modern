import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { PreferencesProvider } from '../state/app';
import { Reading, ConfirmDialog } from '../components/ui';
describe('safe UI primitives', () => {
  it('distinguishes an unknown value from a measured zero', () => {
    render(
      <PreferencesProvider>
        <Reading value={0} />
        <Reading value={null} />
      </PreferencesProvider>,
    );
    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.getByText(/Нет данных/)).toBeInTheDocument();
  });
  it('starts confirmation on Cancel and requires explicit confirmation', async () => {
    const confirm = vi.fn(),
      cancel = vi.fn();
    render(
      <PreferencesProvider>
        <ConfirmDialog message="Delete file.txt" onConfirm={confirm} onCancel={cancel} />
      </PreferencesProvider>,
    );
    expect(screen.getByRole('button', { name: 'Отмена' })).toHaveFocus();
    expect(confirm).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить' }));
    expect(confirm).toHaveBeenCalledOnce();
  });
});
