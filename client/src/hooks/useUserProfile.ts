import { useProfileQuery } from "../queries/useProfileQuery";

/**
 * Hook that fetches and caches the current user's profile (tier, limits, etc.).
 * Returns `null` while loading or when the user is not authenticated.
 *
 * Internally backed by React Query + Zod validation.
 */
export function useUserProfile() {
  const { profile, loading, error, refresh } = useProfileQuery();

  return {
    profile,
    loading,
    error,
    refresh,
    /** Convenience: is user on a paid plan (pro/enterprise) or admin? */
    canExport: profile?.can_export ?? false,
    /** Convenience: has the user hit the saved-search limit? */
    atSaveLimit:
      profile != null &&
      !profile.can_export &&
      profile.saved_searches_count >= profile.saved_searches_limit,
    savedSearchesCount: profile?.saved_searches_count ?? 0,
    savedSearchesLimit: profile?.saved_searches_limit ?? 3,
    compareCount: profile?.compare_count_month ?? 0,
    compareLimit: profile?.compare_limit ?? null,
    deckCount: profile?.deck_count_month ?? 0,
    deckLimit: profile?.deck_limit ?? null,
    tier: profile?.plan_tier ?? profile?.subscription_tier ?? "free",
    isAdmin: profile?.is_admin ?? false,
  };
}
