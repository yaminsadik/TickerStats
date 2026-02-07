import { useEffect, useState, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { fetchProfile, type UserProfile } from "../api/profileApi";
import { useAuthenticatedFetch } from "./useAuthenticatedApi";

/**
 * Hook that fetches and caches the current user's profile (tier, limits, etc.).
 * Returns `null` while loading or when the user is not authenticated.
 */
export function useUserProfile() {
  const { isAuthenticated, isLoading: authLoading } = useAuth0();
  const { authenticatedFetch } = useAuthenticatedFetch();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const p = await fetchProfile(authenticatedFetch);
      setProfile(p);
    } catch (err: any) {
      setError(err.message || "Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, authenticatedFetch]);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      refresh();
    }
  }, [authLoading, isAuthenticated, refresh]);

  return {
    profile,
    loading: loading || authLoading,
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
