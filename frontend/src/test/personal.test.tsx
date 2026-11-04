import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { ApiProvider, PreferencesProvider } from '../state/app';
import Personal from '../features/Personal';
import { Field } from '../components/workspace';
import { catalogSchema } from '../api/catalog';
afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});
describe('migration contracts and accessible interaction', () => {
  it('gives a select its label without concatenating option text', () => {
    render(
      <Field label="Store">
        <select>
          <option>Calendar</option>
          <option>Tasks</option>
        </select>
      </Field>,
    );
    expect(screen.getByRole('combobox', { name: 'Store' })).toBeInTheDocument();
  });
  it('accepts the existing catalog nullable metadata without inventing defaults', () => {
    const parsed = catalogSchema.parse({
      apps: [
        {
          id: 'manual',
          name: 'Author download',
          description: 'User content',
          category: 'system',
          version: '1',
          format: 'sis',
          compatibility: 'untested',
          delivery: 'manual',
          network: 'offline',
          collection: [],
          sources: [],
          manual_url: null,
          delivery_reason: null,
        },
      ],
      sets: {},
      jobs: [],
      research: [],
    });
    expect(parsed.apps[0]?.manual_url).toBeNull();
  });
  it('previews edits, starts on Cancel, and consumes a plan before an uncertain write', async () => {
    localStorage.setItem('symport-language', 'en');
    const actions: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        const body: unknown = JSON.parse(String(init.body));
        if (!body || typeof body !== 'object' || !('action' in body)) throw Error('Missing action');
        const action = String(body.action);
        actions.push(action);
        const result =
          action === 'discover'
            ? {
                devices: [
                  {
                    id: 'fixture',
                    transport: 'gammu',
                    model: 'TEST DOUBLE',
                    connected: true,
                    capabilities: ['personal-data', 'contacts-read'],
                  },
                ],
                limitations: {},
              }
            : action === 'personal-read'
              ? {
                  snapshot: 'snapshot-test',
                  fingerprint: 'fingerprint-test',
                  rows: [
                    {
                      name: 'Contact A',
                      phones: ['+1234567'],
                      emails: [],
                      native_id: '1',
                      source_snapshot: 'snapshot-test',
                    },
                  ],
                  duplicates: [],
                }
              : action === 'personal-preview'
                ? {
                    plan: 'one-shot-plan',
                    changes: [
                      {
                        operation: 'update',
                        before: { phones: ['+1234567'] },
                        after: { phones: ['+7654321'] },
                      },
                    ],
                    conflicts: [],
                    skipped: 0,
                  }
                : action === 'personal-apply'
                  ? { error: 'Read-back unavailable. Read phone before retrying.' }
                  : {};
        return new Response(JSON.stringify(result), {
          status: action === 'personal-apply' ? 409 : 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }),
    );
    const cache = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const rendered = render(
      <QueryClientProvider client={cache}>
        <ApiProvider client={new ApiClient(() => 'test-token')}>
          <PreferencesProvider>
            <Personal domain="contacts" />
          </PreferencesProvider>
        </ApiProvider>
      </QueryClientProvider>,
    );
    await screen.findByRole('option', { name: /TEST DOUBLE/ });
    await userEvent.selectOptions(
      await screen.findByLabelText('Connection', { exact: true }),
      'fixture',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Read phone' }));
    const phones = await screen.findByLabelText('phones: Contact A');
    await userEvent.clear(phones);
    await userEvent.type(phones, '+7654321');
    await userEvent.click(screen.getByRole('button', { name: 'Preview synchronization' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Apply changes' }));
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    expect(actions).not.toContain('personal-apply');
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    await screen.findAllByText('Read-back unavailable. Read phone before retrying.');
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('button', { name: 'Apply changes' })).not.toBeInTheDocument();
    expect(actions.filter((a) => a === 'personal-apply')).toHaveLength(1);
    rendered.unmount();
    await waitFor(() => expect(cache.getQueriesData({ queryKey: ['personal'] })).toEqual([]));
    cache.clear();
  });
});
