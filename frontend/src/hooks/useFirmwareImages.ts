import { useQuery } from '@tanstack/react-query';
import { useApi } from '../state/app';
import { imageListSchema } from '../api/firmware';

export const firmwareKeys = { images: ['firmware', 'images'] as const };
/** Uploaded firmware images; polls only while an index is being built. */
export function useFirmwareImages() {
  const api = useApi();
  return useQuery({
    queryKey: firmwareKeys.images,
    queryFn: ({ signal }) =>
      api.request('/api/firmware', { action: 'list' }, imageListSchema, signal),
    refetchInterval: (query) =>
      query.state.data?.images.some((image) => image.status === 'indexing') ? 1000 : false,
  });
}
