import { useCallback, useState } from 'react';

/** Navigation layout preferences only (open groups, compact rail); never personal data. */
function read<T>(key: string, fallback: T, valid: (value: unknown) => value is T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw === null) return fallback;
    const parsed: unknown = JSON.parse(raw);
    return valid(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}
function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Private browsing may deny storage; the menu still works for this session. */
  }
}
export function useStored<T>(
  key: string,
  fallback: T,
  valid: (value: unknown) => value is T,
): [T, (value: T | ((previous: T) => T)) => void] {
  const [state, setState] = useState<T>(() => read(key, fallback, valid));
  const update = useCallback(
    (value: T | ((previous: T) => T)) => {
      setState((previous) => {
        const next = typeof value === 'function' ? (value as (p: T) => T)(previous) : value;
        write(key, next);
        return next;
      });
    },
    [key],
  );
  return [state, update];
}
export const isBoolean = (value: unknown): value is boolean => typeof value === 'boolean';
export const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === 'string');
