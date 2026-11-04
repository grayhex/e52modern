import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi, usePreferences } from '../state/app';
import { connectionKey } from './capabilities';
export const keys = {
  devices: ['devices'] as const,
  files: (device: string, path: string) => ['files', device, path] as const,
  history: ['history'] as const,
};
/** Query roots whose second key element is a connection id. */
export const DEVICE_SCOPED_ROOTS = ['files', 'personal', 'media', 'diagnostics'] as const;
export function useDevices() {
  const api = useApi();
  return useQuery({
    queryKey: keys.devices,
    queryFn: ({ signal }) => api.discover(signal),
    staleTime: 30000,
    refetchInterval: 30000,
    retry: false,
  });
}
/**
 * Drops everything cached for a connection as soon as it stops being the same connection:
 * other phone/model/firmware/transport/profile, disconnect or a vanished profile. Stale
 * “available” answers from the previous phone must never survive a change.
 */
export function useCapabilityGuard() {
  const queryClient = useQueryClient();
  const { setContactIndex } = usePreferences();
  const { data, isError } = useDevices();
  const seen = useRef(new Map<string, string>());
  useEffect(() => {
    const previous = seen.current;
    const current = new Map<string, string>();
    for (const device of data?.devices ?? []) current.set(device.id, connectionKey(device));
    // A failed discovery (backend or Bridge lost) invalidates everything we knew.
    const changed = isError
      ? [...previous.keys()]
      : [...previous.keys()].filter((id) => previous.get(id) !== current.get(id));
    for (const id of changed) {
      for (const root of DEVICE_SCOPED_ROOTS)
        queryClient.removeQueries({
          predicate: (q) => q.queryKey[0] === root && q.queryKey[1] === id,
        });
      setContactIndex(null);
    }
    if (changed.length) void queryClient.invalidateQueries({ queryKey: ['workspace'] });
    seen.current = isError ? new Map() : current;
  }, [data, isError, queryClient, setContactIndex]);
}
