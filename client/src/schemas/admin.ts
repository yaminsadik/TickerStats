import { z } from "zod";

/**
 * Zod schemas for admin API responses.
 * Mirrors interfaces in api/profileApi.ts.
 */

export const adminUserSchema = z.object({
  auth0_user_id: z.string(),
  email: z.string().nullable(),
  name: z.string().nullable(),
  picture: z.string().nullable(),
  subscription_tier: z.enum(["free", "pro", "enterprise"]),
  stripe_customer_id: z.string().nullable(),
  subscription_expires_at: z.string().nullable(),
  is_admin: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type AdminUserParsed = z.infer<typeof adminUserSchema>;

export const adminStatsSchema = z.object({
  total_users: z.number(),
  paid_users: z.number(),
  free_users: z.number(),
  total_saved_analyses: z.number(),
  total_decks: z.number(),
  total_watchlist_items: z.number(),
});

export type AdminStatsParsed = z.infer<typeof adminStatsSchema>;
