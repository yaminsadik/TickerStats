/**
 * React Query hooks for watchlist CRUD operations.
 * Wraps api/userApi watchlist functions with Zod validation and cache management.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth0 } from "@auth0/auth0-react";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import {
  fetchWatchlist,
  addToWatchlist,
  updateWatchlistNotes,
  removeFromWatchlist,
} from "../api/userApi";
import { queryKeys } from "../lib/queryKeys";
import { watchlistItemSchema } from "../schemas/userResources";
import { parseOrThrow } from "../lib/parse";
import { z } from "zod";

/**
 * Fetch the user's watchlist with Zod validation.
 */
export function useWatchlist() {
  const { isAuthenticated } = useAuth0();
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.watchlist,
    queryFn: async () => {
      const raw = await fetchWatchlist(authenticatedFetch);
      return parseOrThrow(z.array(watchlistItemSchema), raw, "watchlist");
    },
    enabled: isAuthenticated,
  });
}

/**
 * Add a ticker to the watchlist (with optional notes) and invalidate cache.
 */
export function useAddToWatchlistFull() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticker, notes }: { ticker: string; notes?: string }) =>
      addToWatchlist(authenticatedFetch, ticker, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist });
    },
  });
}

/**
 * Update notes on a watchlist item and invalidate cache.
 */
export function useUpdateWatchlistNotes() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, notes }: { id: number; notes: string | null }) =>
      updateWatchlistNotes(authenticatedFetch, id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist });
    },
  });
}

/**
 * Remove a ticker from the watchlist and invalidate cache.
 */
export function useRemoveFromWatchlist() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => removeFromWatchlist(authenticatedFetch, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist });
    },
  });
}
