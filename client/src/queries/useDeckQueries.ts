/**
 * React Query hooks for deck CRUD operations.
 * Wraps api/userApi deck functions with Zod validation and cache management.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import {
  fetchDeck,
  fetchDecks,
  deleteDeckFromDB,
  createDeckInDB,
  type CreateDeckPayload,
} from "../api/userApi";
import { queryKeys } from "../lib/queryKeys";
import { deckFullSchema, deckMetaSchema } from "../schemas/deck";
import { z } from "zod";

/**
 * Fetch a single deck by ID with Zod validation.
 */
export function useDeckDetail(id: number | undefined) {
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.decks.detail(id!),
    queryFn: async () => {
      const raw = await fetchDeck(authenticatedFetch, id!);
      return deckFullSchema.parse(raw);
    },
    enabled: id != null,
    staleTime: 60 * 1000, // 1 minute
  });
}

/**
 * Fetch the list of user decks with Zod validation.
 */
export function useDeckList() {
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.decks.all,
    queryFn: async () => {
      const raw = await fetchDecks(authenticatedFetch);
      return z.array(deckMetaSchema).parse(raw);
    },
    staleTime: 60 * 1000,
  });
}

/**
 * Delete a deck and invalidate related caches.
 */
export function useDeleteDeck() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => deleteDeckFromDB(authenticatedFetch, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.decks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}

/**
 * Save a deck to the database and invalidate related caches.
 */
export function useSaveDeck() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateDeckPayload) =>
      createDeckInDB(authenticatedFetch, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.decks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}
