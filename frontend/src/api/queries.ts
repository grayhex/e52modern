import { useQuery } from '@tanstack/react-query';
import { useApi } from '../state/app';
export const keys = {
  devices: ['devices'] as const,
  files: (device: string, path: string) => ['files', device, path] as const,
  history: ['history'] as const,
};
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
