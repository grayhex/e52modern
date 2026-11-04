import { describe, it, expect, vi } from 'vitest';
import { FileBrowserAdapterError, FileBrowserBulkActionError } from '@harryy/react-file-browser';
import { createPhoneAdapter, toDevicePath } from '../api/phoneFiles';
import type { ApiClient } from '../api/client';

function fakeApi(overrides: Partial<Record<'list' | 'fileAction', unknown>> = {}) {
  const api = {
    list: vi.fn(async (_device: string, path: string) => ({
      entries:
        path === ''
          ? [
              { name: 'Docs', directory: true, size: null },
              { name: 'a.txt', directory: false, size: 3 },
            ]
          : [{ name: 'b.sis', directory: false, size: 9 }],
    })),
    fileAction: vi.fn(async () => ({ status: 'ok' })),
    ...overrides,
  };
  return api as unknown as ApiClient & typeof api;
}
const all = { upload: true, mkdir: true, delete: true };

describe('phone file adapter', () => {
  it('lists with device-relative paths and browser-style node paths', async () => {
    const api = fakeApi();
    const adapter = createPhoneAdapter(api, 'card', all);
    const root = await adapter.list('/');
    expect(api.list).toHaveBeenCalledWith('card', '', undefined);
    expect(root.items).toEqual([
      { path: '/Docs', name: 'Docs', kind: 'folder' },
      { path: '/a.txt', name: 'a.txt', kind: 'file', size: 3 },
    ]);
    expect((await adapter.list('/Docs')).items[0]?.path).toBe('/Docs/b.sis');
    expect(toDevicePath('/Docs/b.sis')).toBe('Docs/b.sis');
  });
  it('offers only what the connection can do; rename/move/copy never exist', () => {
    const readOnly = createPhoneAdapter(fakeApi(), 'card', {
      upload: false,
      mkdir: false,
      delete: false,
    });
    expect(readOnly.createFolder).toBeUndefined();
    for (const name of ['rename', 'move', 'copy', 'stat', 'bulkDownloadUrl'] as const)
      expect(readOnly[name]).toBeUndefined();
    expect(createPhoneAdapter(fakeApi(), 'card', all).createFolder).toBeTypeOf('function');
  });
  it('refuses writes the connection does not support', async () => {
    const adapter = createPhoneAdapter(fakeApi(), 'card', {
      upload: false,
      mkdir: false,
      delete: false,
    });
    await expect(adapter.delete(['/a.txt'])).rejects.toMatchObject({ code: 'not_supported' });
    await expect(adapter.upload('/x.txt', new File(['x'], 'x.txt'))).rejects.toBeInstanceOf(
      FileBrowserAdapterError,
    );
  });
  it('creates folders, uploads bytes and deletes through the confirmed device actions', async () => {
    const api = fakeApi();
    const adapter = createPhoneAdapter(api, 'card', all);
    await adapter.createFolder?.('/Docs/new');
    expect(api.fileAction).toHaveBeenCalledWith('mkdir', 'card', 'Docs/new');
    const progress = vi.fn();
    const node = await adapter.upload('/up.txt', new File(['hi'], 'up.txt'), {
      onProgress: progress,
    });
    expect(api.fileAction).toHaveBeenCalledWith('upload', 'card', 'up.txt', btoa('hi'));
    expect(node).toMatchObject({ path: '/up.txt', kind: 'file', size: 2 });
    expect(progress).toHaveBeenLastCalledWith(2, 2);
    await adapter.delete(['/a.txt']);
    expect(api.fileAction).toHaveBeenCalledWith('delete', 'card', 'a.txt');
  });
  it('reports partial delete failures without hiding the successes', async () => {
    const api = fakeApi({
      fileAction: vi.fn(async (_a: string, _d: string, path: string) => {
        if (path === 'bad') throw new Error('Folder is not empty');
        return { status: 'ok' };
      }),
    });
    const error = await createPhoneAdapter(api, 'card', all)
      .delete(['/good', '/bad'])
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(FileBrowserBulkActionError);
    expect(error).toMatchObject({
      succeededPaths: ['/good'],
      failures: [{ path: '/bad', message: 'Folder is not empty' }],
    });
  });
  it('maps an existing-file refusal to a conflict and enforces the 8 MiB limit', async () => {
    const api = fakeApi({
      fileAction: vi.fn(async () => {
        throw new Error('Destination already exists; overwrite refused');
      }),
    });
    const adapter = createPhoneAdapter(api, 'card', all);
    await expect(adapter.upload('/a.txt', new File(['x'], 'a.txt'))).rejects.toMatchObject({
      code: 'conflict',
    });
    const big = new File([new Uint8Array(8 * 1024 ** 2 + 1)], 'big.bin');
    await expect(adapter.upload('/big.bin', big)).rejects.toBeInstanceOf(FileBrowserAdapterError);
  });
  it('checks existence from the parent listing and builds same-origin preview URLs', async () => {
    const adapter = createPhoneAdapter(fakeApi(), 'card', all);
    expect(await adapter.exists?.(['/a.txt', '/nope.txt'])).toEqual({
      '/a.txt': true,
      '/nope.txt': false,
    });
    expect(await adapter.signedUrl('/Docs/b c.sis')).toBe(
      '/api/device/file?device=card&path=Docs%2Fb+c.sis',
    );
  });
});
