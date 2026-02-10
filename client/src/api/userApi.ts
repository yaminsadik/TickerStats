import { API_BASE } from "../config/apiBase";

/**
 * API client for user-scoped endpoints (watchlist, saved analyses, decks).
 * All functions accept an `authenticatedFetch` obtained from useAuthenticatedApi().
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WatchlistItem {
  id: number;
  ticker: string;
  notes: string | null;
  created_at: string;
}

export interface SavedAnalysis {
  id: number;
  name: string;
  description: string | null;
  symbols: string[];
  snapshot_fields: string[] | null;
  perf_periods: string[] | null;
  include_dcf: boolean;
  snapshot_data?: import("../types/api").RelativeTableResponse | null;
  created_at: string;
  updated_at: string;
}

export interface DeckMeta {
  id: number;
  ticker: string;
  title: string;
  llm_provider: string | null;
  created_at: string;
}

export interface DeckFull extends DeckMeta {
  content: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

type AuthFetch = (url: string, options?: RequestInit) => Promise<Response>;

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const msg =
      (body as any).detail || `Request failed (${response.status})`;
    throw new Error(msg);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Watchlist
// ---------------------------------------------------------------------------

export async function fetchWatchlist(
  authFetch: AuthFetch
): Promise<WatchlistItem[]> {
  const res = await authFetch(`${API_BASE}/api/user/watchlist`);
  return jsonOrThrow<WatchlistItem[]>(res);
}

export async function addToWatchlist(
  authFetch: AuthFetch,
  ticker: string,
  notes?: string
): Promise<WatchlistItem> {
  const res = await authFetch(`${API_BASE}/api/user/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: ticker.toUpperCase(), notes: notes ?? null }),
  });
  return jsonOrThrow<WatchlistItem>(res);
}

export async function updateWatchlistNotes(
  authFetch: AuthFetch,
  id: number,
  notes: string | null
): Promise<WatchlistItem> {
  const res = await authFetch(`${API_BASE}/api/user/watchlist/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes }),
  });
  return jsonOrThrow<WatchlistItem>(res);
}

export async function removeFromWatchlist(
  authFetch: AuthFetch,
  id: number
): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/user/watchlist/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as any).detail || "Delete failed");
  }
}

// ---------------------------------------------------------------------------
// Saved Analyses
// ---------------------------------------------------------------------------

export interface SaveAnalysisPayload {
  name: string;
  description?: string;
  symbols: string[];
  snapshot_fields?: string[];
  perf_periods?: string[];
  include_dcf?: boolean;
  snapshot_data?: import("../types/api").RelativeTableResponse | null;
}

export async function fetchSavedAnalyses(
  authFetch: AuthFetch
): Promise<SavedAnalysis[]> {
  const res = await authFetch(`${API_BASE}/api/user/saved-analyses`);
  return jsonOrThrow<SavedAnalysis[]>(res);
}

export async function createSavedAnalysis(
  authFetch: AuthFetch,
  payload: SaveAnalysisPayload
): Promise<SavedAnalysis> {
  const res = await authFetch(`${API_BASE}/api/user/saved-analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow<SavedAnalysis>(res);
}

export async function fetchSavedAnalysis(
  authFetch: AuthFetch,
  id: number
): Promise<SavedAnalysis> {
  const res = await authFetch(`${API_BASE}/api/user/saved-analyses/${id}`);
  return jsonOrThrow<SavedAnalysis>(res);
}

export async function deleteSavedAnalysis(
  authFetch: AuthFetch,
  id: number
): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/user/saved-analyses/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as any).detail || "Delete failed");
  }
}

// ---------------------------------------------------------------------------
// Decks
// ---------------------------------------------------------------------------

export interface CreateDeckPayload {
  ticker: string;
  title: string;
  content: Record<string, unknown>;
  llm_provider?: string;
}

export async function fetchDecks(
  authFetch: AuthFetch
): Promise<DeckMeta[]> {
  const res = await authFetch(`${API_BASE}/api/user/decks`);
  return jsonOrThrow<DeckMeta[]>(res);
}

export async function createDeckInDB(
  authFetch: AuthFetch,
  payload: CreateDeckPayload
): Promise<DeckFull> {
  const res = await authFetch(`${API_BASE}/api/user/decks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow<DeckFull>(res);
}

export async function fetchDeck(
  authFetch: AuthFetch,
  id: number
): Promise<DeckFull> {
  const res = await authFetch(`${API_BASE}/api/user/decks/${id}`);
  return jsonOrThrow<DeckFull>(res);
}

export async function deleteDeckFromDB(
  authFetch: AuthFetch,
  id: number
): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/user/decks/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as any).detail || "Delete failed");
  }
}
