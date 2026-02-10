/**
 * Centralized query key factory for TanStack Query.
 * Every query/mutation that touches the cache should reference keys from here.
 */

/**
 * Deterministic JSON.stringify with sorted object keys.
 * Prevents cache misses when the same params object is reconstructed
 * with different property order or referential identity.
 */
function stableHash(obj: unknown): string {
  return JSON.stringify(obj, (_, v) =>
    v && typeof v === "object" && !Array.isArray(v)
      ? Object.fromEntries(
          Object.entries(v).sort(([a], [b]) => a.localeCompare(b)),
        )
      : v,
  );
}

export const queryKeys = {
  profile: ["profile"] as const,

  decks: {
    all: ["decks"] as const,
    detail: (id: number) => ["decks", id] as const,
  },

  sections: ["sections"] as const,

  relativeTable: (params: unknown) =>
    ["relativeTable", stableHash(params)] as const,

  watchlist: ["watchlist"] as const,

  savedAnalyses: ["savedAnalyses"] as const,

  admin: {
    users: ["admin", "users"] as const,
    stats: ["admin", "stats"] as const,
  },
};
