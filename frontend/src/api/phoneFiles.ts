import {
  FileBrowserAdapterError,
  FileBrowserBulkActionError,
  type FileBrowserAdapter,
  type FileNode,
} from '@harryy/react-file-browser';
import { encode } from '../utils/files';
import type { ApiClient } from './client';

export type PhoneFileCapabilities = { upload: boolean; mkdir: boolean; delete: boolean };
const UPLOAD_LIMIT = 8 * 1024 ** 2;

/** Browser paths are `/dir/file`; Device Manager paths are relative `dir/file`. */
export const toDevicePath = (path: string) => path.replace(/^\/+/, '');
const toBrowserPath = (path: string) => '/' + toDevicePath(path);
const join = (dir: string, name: string) => (dir === '/' ? `/${name}` : `${dir}/${name}`);
const parent = (path: string) => path.slice(0, path.lastIndexOf('/')) || '/';

function mapError(error: unknown): never {
  if (error instanceof FileBrowserAdapterError || error instanceof FileBrowserBulkActionError)
    throw error;
  const message = error instanceof Error ? error.message : 'Request failed';
  if (/exist|overwrit|already/i.test(message))
    throw new FileBrowserAdapterError('conflict', message);
  if (/not found|no such/i.test(message)) throw new FileBrowserAdapterError('not_found', message);
  if (/not allowed|unsafe|invalid|path/i.test(message))
    throw new FileBrowserAdapterError('invalid_path', message);
  throw error instanceof Error ? error : new Error(message);
}

/**
 * Phone files through the Device Manager API. Only capabilities the connection really has are
 * exposed: rename, move and copy are not part of that API, so the browser never offers them, and
 * existing files are never overwritten (the device layer refuses).
 */
export function createPhoneAdapter(
  api: ApiClient,
  device: string,
  capabilities: PhoneFileCapabilities,
): FileBrowserAdapter {
  const list = async (path: string, signal?: AbortSignal) => {
    const result = await api.list(device, toDevicePath(path), signal);
    return result.entries.map<FileNode>((entry) => ({
      path: join(path, entry.name),
      name: entry.name,
      kind: entry.directory ? 'folder' : 'file',
      ...(entry.size == null ? {} : { size: entry.size }),
    }));
  };
  const adapter: FileBrowserAdapter = {
    async list(path, options) {
      try {
        return { items: await list(path, options?.signal) };
      } catch (error) {
        return mapError(error);
      }
    },
    async signedUrl(path) {
      return `/api/device/file?${new URLSearchParams({ device, path: toDevicePath(path) })}`;
    },
    async delete(paths) {
      if (!capabilities.delete)
        throw new FileBrowserAdapterError(
          'not_supported',
          'Deleting is not available on this connection',
        );
      const done: string[] = [];
      const failures: { path: string; message: string }[] = [];
      for (const path of paths) {
        try {
          await api.fileAction('delete', device, toDevicePath(path));
          done.push(path);
        } catch (error) {
          failures.push({
            path,
            message: error instanceof Error ? error.message : 'Delete failed',
          });
        }
      }
      if (failures.length)
        throw new FileBrowserBulkActionError('delete', {
          succeededPaths: done,
          failures,
          totalCount: paths.length,
        });
    },
    async upload(path, file, options) {
      if (!capabilities.upload)
        throw new FileBrowserAdapterError(
          'not_supported',
          'Uploading is not available on this connection',
        );
      if (file.size > UPLOAD_LIMIT)
        throw new FileBrowserAdapterError('invalid_path', 'File exceeds the 8 MiB transfer limit');
      try {
        options?.onProgress?.(0, file.size);
        await api.fileAction('upload', device, toDevicePath(path), await encode(file));
        options?.onProgress?.(file.size, file.size);
        return { path: toBrowserPath(path), name: file.name, kind: 'file', size: file.size };
      } catch (error) {
        return mapError(error);
      }
    },
    async exists(paths) {
      const cache = new Map<string, Set<string>>();
      const result: Record<string, boolean> = {};
      for (const path of paths) {
        const dir = parent(path);
        if (!cache.has(dir)) {
          try {
            cache.set(dir, new Set((await list(dir)).map((node) => node.path)));
          } catch {
            cache.set(dir, new Set());
          }
        }
        result[path] = cache.get(dir)?.has(path) ?? false;
      }
      return result;
    },
  };
  if (capabilities.mkdir)
    adapter.createFolder = async (path) => {
      try {
        await api.fileAction('mkdir', device, toDevicePath(path));
        return {
          path: toBrowserPath(path),
          name: path.slice(path.lastIndexOf('/') + 1),
          kind: 'folder',
        };
      } catch (error) {
        return mapError(error);
      }
    };
  return adapter;
}
