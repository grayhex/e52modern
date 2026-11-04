import { describe, it, expect, vi } from 'vitest';
import { ApiClient, ApiError } from '../api/client';
describe('API boundary', () => {
  it('uses headers, keeps tokens out of URLs and validates responses', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ devices: [], limitations: {} })));
    vi.stubGlobal('fetch', fetch);
    const client = new ApiClient(() => 'private');
    await expect(client.discover()).resolves.toEqual({ devices: [], limitations: {} });
    expect(fetch).toHaveBeenCalledWith(
      '/api/manager',
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-Symport-Token': 'private' }),
        cache: 'no-store',
      }),
    );
  });
  it('rejects unexpected payloads instead of inventing device data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
    await expect(new ApiClient(() => 'token').discover()).rejects.toBeInstanceOf(ApiError);
  });
  it('does not retry an uncertain write', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('Disconnected'));
    vi.stubGlobal('fetch', fetch);
    await expect(new ApiClient(() => 'token').fileAction('delete', 'card', 'x')).rejects.toThrow(
      'Disconnected',
    );
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
