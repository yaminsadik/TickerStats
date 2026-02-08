import { useQuery } from '@tanstack/react-query';
import { fetchRelativeTableAuthed, type FetchRelativeParams } from '../api/client';
import { useAuthenticatedFetch } from './useAuthenticatedApi';
import { queryKeys } from '../lib/queryKeys';
import { relativeTableResponseSchema } from '../schemas/relativeTable';

export function useRelativeTable(params: FetchRelativeParams | null) {
  const { authenticatedFetch } = useAuthenticatedFetch();
  return useQuery({
    queryKey: queryKeys.relativeTable(params),
    queryFn: async () => {
      if (!params || params.symbols.length === 0) {
        throw new Error('No symbols provided');
      }
      const raw = await fetchRelativeTableAuthed(authenticatedFetch, params);
      return relativeTableResponseSchema.parse(raw);
    },
    enabled: !!params && params.symbols.length > 0,
    staleTime: 60 * 1000, // 1 minute
    retry: 1,
  });
}
