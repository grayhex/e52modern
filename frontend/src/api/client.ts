import { z } from 'zod';
import {
  connectionSchema,
  discoverySchema,
  downloadSchema,
  filesSchema,
  historySchema,
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
