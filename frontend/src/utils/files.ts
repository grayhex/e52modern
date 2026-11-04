export async function encode(file: Blob) {
  let raw = '';
  for (const b of new Uint8Array(await file.arrayBuffer())) raw += String.fromCharCode(b);
  return btoa(raw);
}
export function bytes(size: number | null | undefined) {
  if (size == null) return '—';
  for (const [factor, unit] of [
    [1024 ** 3, 'GiB'],
    [1024 ** 2, 'MiB'],
    [1024, 'KiB'],
  ] as const)
    if (size >= factor) return `${(size / factor).toFixed(1)} ${unit}`;
  return `${size} B`;
}
