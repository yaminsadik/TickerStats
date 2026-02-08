import { useQuery } from '@tanstack/react-query';
import { fetchRelativeTableAuthed, type FetchRelativeParams } from '../api/client';
import { useAuthenticatedFetch } from './useAuthenticatedApi';
import { queryKeys } from '../lib/queryKeys';
import { relativeTableResponseSchema } from '../schemas/relativeTable';
import { parseOrThrow } from '../lib/parse';

export function useRelativeTable(params: FetchRelativeParams | null) {
  const { authenticatedFetch } = useAuthenticatedFetch();
  return useQuery({
    queryKey: queryKeys.relativeTable(params),
    queryFn: async () => {
      if (!params || params.symbols.length === 0) {
        throw new Error('No symbols provided');
      }
      const raw = await fetchRelativeTableAuthed(authenticatedFetch, params);
      return parseOrThrow(relativeTableResponseSchema, raw, 'relativeTable');
    },
    enabled: !!params && params.symbols.length > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes – heavy endpoint
    retry: 1,
  });
}
