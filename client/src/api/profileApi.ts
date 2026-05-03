import { API_BASE } from "../config/apiBase";

/**
 * API client for user profile and admin endpoints.
 */

type AuthFetch = (url: string, options?: RequestInit) => Promise<Response>;

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const msg = (body as any).detail || `Request failed (${response.status})`;
    const err = new Error(msg);
    (err as any).status = response.status;
    throw err;
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Profile types
// ---------------------------------------------------------------------------

export interface UserProfile {
  auth0_user_id: string;
  email: string | null;
  name: string | null;
  picture: string | null;
  subscription_tier: "free" | "pro" | "enterprise";
  plan_tier: "free" | "pro" | "enterprise";
  subscription_expires_at: string | null;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
  saved_searches_count: number;
  saved_searches_limit: number;
  compare_count_month: number;
  compare_limit: number | null;
  deck_count_month: number;
  deck_limit: number | null;
  can_export: boolean;
  deck_export_credits: number;
  daily_thinking_uses: number;
  daily_thinking_limit: number | null;
  monthly_model_cost_usd: number;
}

export interface ProfileUpdatePayload {
  name?: string;
  picture?: string;
}

// ---------------------------------------------------------------------------
// Profile API
// ---------------------------------------------------------------------------

export async function fetchProfile(
  authFetch: AuthFetch
): Promise<UserProfile> {
  const res = await authFetch(`${API_BASE}/api/user/profile`);
  return jsonOrThrow<UserProfile>(res);
}

export async function updateProfile(
  authFetch: AuthFetch,
  payload: ProfileUpdatePayload
): Promise<UserProfile> {
  const res = await authFetch(`${API_BASE}/api/user/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return jsonOrThrow<UserProfile>(res);
}

// ---------------------------------------------------------------------------
// Admin types
// ---------------------------------------------------------------------------

export interface AdminUser {
  auth0_user_id: string;
  email: string | null;
  name: string | null;
  picture: string | null;
  subscription_tier: "free" | "pro" | "enterprise";
  stripe_customer_id: string | null;
  subscription_expires_at: string | null;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminStats {
  total_users: number;
  paid_users: number;
  free_users: number;
  total_saved_analyses: number;
  total_decks: number;
  total_watchlist_items: number;
}

export interface AdminUserUpdatePayload {
  subscription_tier?: "free" | "pro" | "enterprise";
  is_admin?: boolean;
  subscription_expires_at?: string;
}

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export async function fetchAdminUsers(
  authFetch: AuthFetch
): Promise<AdminUser[]> {
  const res = await authFetch(`${API_BASE}/api/admin/users`);
  return jsonOrThrow<AdminUser[]>(res);
}

export async function updateAdminUser(
  authFetch: AuthFetch,
  userId: string,
  payload: AdminUserUpdatePayload
): Promise<AdminUser> {
  const res = await authFetch(
    `${API_BASE}/api/admin/users/${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return jsonOrThrow<AdminUser>(res);
}

export async function fetchAdminStats(
  authFetch: AuthFetch
): Promise<AdminStats> {
  const res = await authFetch(`${API_BASE}/api/admin/stats`);
  return jsonOrThrow<AdminStats>(res);
}
