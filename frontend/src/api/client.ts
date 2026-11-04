import { z } from 'zod';
import {
  connectionSchema,
  discoverySchema,
  downloadSchema,
  filesSchema,
  historySchema,
  recheckSchema,
  resultSchema,
  type Json,
} from './contracts';
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
export class ApiClient {
  constructor(private readonly token: () => string) {}
  get styleNonce() {
    return this.token();
  }
  async get<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
    const response = await fetch(path, {
      credentials: 'same-origin',
      cache: 'no-store',
      ...(signal ? { signal } : {}),
    });
    return this.decode(response, schema);
  }
  async uploadProgress<T>(
    path: string,
    file: File,
    schema: z.ZodType<T>,
    progress: (value: number) => void,
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', path);
      xhr.timeout = 3600000;
      xhr.setRequestHeader('X-Symport-Token', this.token());
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) progress((100 * e.loaded) / e.total);
      };
      xhr.onerror = () => reject(new ApiError('Upload interrupted', 0));
      xhr.ontimeout = () => reject(new ApiError('Upload timed out', 408));
      xhr.onload = () => {
        if (!xhr.status) {
          reject(new ApiError('Upload interrupted', 0));
          return;
        }
        void this.decode(new Response(xhr.responseText, { status: xhr.status }), schema).then(
          resolve,
          reject,
        );
      };
      xhr.send(file);
    });
  }
  async upload<T>(path: string, file: File, schema: z.ZodType<T>): Promise<T> {
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/octet-stream', 'X-Symport-Token': this.token() },
      body: file,
    });
    return this.decode(response, schema);
  }
  private async decode<T>(response: Response, schema: z.ZodType<T>): Promise<T> {
    const raw: unknown = await response.json();
    if (!response.ok) {
      const error = z.object({ error: z.string() }).safeParse(raw);
      throw new ApiError(
        error.success ? error.data.error : `HTTP ${response.status}`,
        response.status,
      );
    }
    const parsed = schema.safeParse(raw);
    if (!parsed.success) throw new ApiError('Unexpected API response', 502);
    return parsed.data;
  }
  async request<T>(
    path: string,
    body: Record<string, Json>,
    schema: z.ZodType<T>,
    signal?: AbortSignal,
  ): Promise<T> {
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', 'X-Symport-Token': this.token() },
      body: JSON.stringify(body),
      ...(signal ? { signal } : {}),
    });
    return this.decode(response, schema);
  }
  /** Read-only re-probe of one connection (never writes, sends or installs). */
  recheck(device: string, signal?: AbortSignal) {
    return this.request('/api/manager', { action: 'capabilities', device }, recheckSchema, signal);
  }
  discover(signal?: AbortSignal) {
    return this.request('/api/manager', { action: 'discover' }, discoverySchema, signal);
  }
  history(signal?: AbortSignal) {
    return this.request('/api/manager', { action: 'history' }, historySchema, signal);
  }
  list(device: string, path: string, signal?: AbortSignal) {
    return this.request('/api/manager', { action: 'list', device, path }, filesSchema, signal);
  }
  download(device: string, path: string) {
    return this.request('/api/manager', { action: 'download', device, path }, downloadSchema);
  }
  fileAction(
    action: 'upload' | 'transfer' | 'mkdir' | 'delete',
    device: string,
    path: string,
    content = '',
  ) {
    return this.request(
      '/api/manager',
      { action, device, path, content, confirm: true },
      resultSchema,
    );
  }
  connection(action: 'status' | 'enable' | 'disconnect', signal?: AbortSignal) {
    return this.request('/api/connection', { action }, connectionSchema, signal);
  }
}
