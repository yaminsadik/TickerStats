/**
 * React Query hooks for saved searches (analyses).
 * Wraps api/userApi saved analysis functions with Zod validation and cache management.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import { fetchSavedAnalyses, deleteSavedAnalysis } from "../api/userApi";
import { queryKeys } from "../lib/queryKeys";
import { savedAnalysisSchema } from "../schemas/userResources";
import { z } from "zod";

/**
 * Fetch all saved searches with Zod validation.
 */
export function useSavedSearchList() {
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.savedAnalyses,
    queryFn: async () => {
      const raw = await fetchSavedAnalyses(authenticatedFetch);
      return z.array(savedAnalysisSchema).parse(raw);
    },
    staleTime: 60 * 1000,
  });
}

/**
 * Delete a saved search and invalidate related caches.
 */
export function useDeleteSavedSearch() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => deleteSavedAnalysis(authenticatedFetch, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.savedAnalyses });
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}
