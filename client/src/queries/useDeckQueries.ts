/**
 * React Query hooks for deck CRUD operations.
 * Wraps api/userApi deck functions with Zod validation and cache management.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth0 } from "@auth0/auth0-react";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import {
  fetchDeck,
  fetchDecks,
  deleteDeckFromDB,
  createDeckInDB,
  unlockDeckExport,
  type CreateDeckPayload,
} from "../api/userApi";
import { queryKeys } from "../lib/queryKeys";
import { deckFullSchema, deckMetaSchema } from "../schemas/deck";
import { parseOrThrow } from "../lib/parse";
import { z } from "zod";

/**
 * Fetch a single deck by ID with Zod validation.
 */
export function useDeckDetail(id: number | undefined) {
  const { isAuthenticated } = useAuth0();
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.decks.detail(id!),
    queryFn: async () => {
      const raw = await fetchDeck(authenticatedFetch, id!);
      return parseOrThrow(deckFullSchema, raw, "deck");
    },
    enabled: id != null && isAuthenticated,
  });
}

/**
 * Fetch the list of user decks with Zod validation.
 */
export function useDeckList() {
  const { isAuthenticated } = useAuth0();
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.decks.all,
    queryFn: async () => {
      const raw = await fetchDecks(authenticatedFetch);
      return parseOrThrow(z.array(deckMetaSchema), raw, "deckList");
    },
    enabled: isAuthenticated,
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

/**
 * Unlock export for a saved deck using an available export credit.
 */
export function useUnlockDeckExport() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => unlockDeckExport(authenticatedFetch, id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.decks.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}
