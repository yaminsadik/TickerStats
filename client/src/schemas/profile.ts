import { z } from "zod";

const tierEnum = z.enum(["free", "pro", "enterprise"]);

/**
 * Zod schema for UserProfile. Mirrors the interface in api/profileApi.ts.
 * Used to validate API responses at the query boundary.
 */
export const userProfileSchema = z.object({
  auth0_user_id: z.string(),
  email: z.string().nullable(),
  name: z.string().nullable(),
  picture: z.string().nullable(),
  subscription_tier: tierEnum,
  plan_tier: tierEnum,
  subscription_expires_at: z.string().nullable(),
  is_admin: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
  saved_searches_count: z.number(),
  saved_searches_limit: z.number(),
  compare_count_month: z.number(),
  compare_limit: z.number().nullable(),
  deck_count_month: z.number(),
  deck_limit: z.number().nullable(),
  can_export: z.boolean(),
});

export type UserProfileParsed = z.infer<typeof userProfileSchema>;
