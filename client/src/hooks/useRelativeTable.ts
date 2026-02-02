import { useQuery } from '@tanstack/react-query';
import { fetchRelativeTable, type FetchRelativeParams } from '../api/client';

export function useRelativeTable(params: FetchRelativeParams | null) {
  return useQuery({
    queryKey: ['relativeTable', params],
    queryFn: () => {
      if (!params || params.symbols.length === 0) {
        throw new Error('No symbols provided');
      }
      return fetchRelativeTable(params);
    },
    enabled: !!params && params.symbols.length > 0,
    staleTime: 60 * 1000, // 1 minute
    retry: 1,
  });
}
