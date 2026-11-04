import type { Device } from '../api/contracts';

export type Operation = { time: string; action: string; status: string };

/** Storage split from the byte counters the transport really reports; null when either is missing. */
export function storage(device: Device | undefined) {
  if (!device || device.total == null || device.free == null || device.total <= 0) return null;
  const free = Math.min(device.free, device.total);
  const used = device.total - free;
  return { total: device.total, free, used, usedPercent: Math.round((used / device.total) * 100) };
}

export function formatBytes(value: number) {
  for (const [factor, unit] of [
    [1024 ** 3, 'ГиБ'],
    [1024 ** 2, 'МиБ'],
    [1024, 'КиБ'],
  ] as const)
    if (value >= factor) return `${(value / factor).toFixed(value >= factor * 10 ? 0 : 1)} ${unit}`;
  return `${value} Б`;
}

const dayKey = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

/** Operations per local day for the last `days` days, split into succeeded / not succeeded. */
export function perDay(operations: Operation[], days = 7, now = new Date()) {
  const buckets: { date: string; label: string; ok: number; other: number }[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    buckets.push({ date: dayKey(day), label: String(day.getDate()), ok: 0, other: 0 });
  }
  for (const op of operations) {
    const parsed = new Date(op.time);
    if (Number.isNaN(parsed.getTime())) continue;
    const bucket = buckets.find((b) => b.date === dayKey(parsed));
    if (!bucket) continue;
    if (op.status === 'success') bucket.ok += 1;
    else bucket.other += 1;
  }
  return buckets;
}

export const localeFor = (language: 'ru' | 'en') => (language === 'ru' ? 'ru-RU' : 'en-GB');
export function timeLabel(iso: string, locale = 'ru-RU') {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
}
