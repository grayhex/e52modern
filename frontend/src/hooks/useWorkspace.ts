import { useQuery } from '@tanstack/react-query';
import { useApi } from '../state/app';
import { stateSchema } from '../api/workspace';
export function useWorkspace() {
  const api = useApi();
  return useQuery({
    queryKey: ['workspace'],
    queryFn: ({ signal }) => api.get('/api/state', stateSchema, signal),
    refetchInterval: 2500,
  });
}
