import { useQuery } from '@tanstack/react-query';
import { fetchRelativeTableAuthed, type FetchRelativeParams } from '../api/client';
import { useAuthenticatedFetch } from './useAuthenticatedApi';

export function useRelativeTable(params: FetchRelativeParams | null) {
  const { authenticatedFetch } = useAuthenticatedFetch();
  return useQuery({
    queryKey: ['relativeTable', params],
    queryFn: () => {
      if (!params || params.symbols.length === 0) {
        throw new Error('No symbols provided');
      }
      return fetchRelativeTableAuthed(authenticatedFetch, params);
    },
    enabled: !!params && params.symbols.length > 0,
    staleTime: 60 * 1000, // 1 minute
    retry: 1,
  });
}
