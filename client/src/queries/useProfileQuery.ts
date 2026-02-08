/**
 * React Query hook for the current user's profile.
 * Wraps fetchProfile with Zod validation and caching.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth0 } from "@auth0/auth0-react";
import { useCallback } from "react";
import { fetchProfile } from "../api/profileApi";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import { queryKeys } from "../lib/queryKeys";
import { userProfileSchema } from "../schemas/profile";
import { parseOrThrow } from "../lib/parse";

export function useProfileQuery() {
  const { isAuthenticated, isLoading: authLoading } = useAuth0();
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  const { data: profile = null, isLoading, error } = useQuery({
    queryKey: queryKeys.profile,
    queryFn: async () => {
      const raw = await fetchProfile(authenticatedFetch);
      return parseOrThrow(userProfileSchema, raw, "profile");
    },
    enabled: isAuthenticated && !authLoading,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: queryKeys.profile });
  }, [queryClient]);

  return {
    profile,
    loading: isLoading || authLoading,
    error: error instanceof Error ? error.message : error ? String(error) : null,
    refresh,
  };
}
