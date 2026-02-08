/**
 * React Query hooks for admin panel operations.
 * Wraps api/profileApi admin functions with Zod validation and cache management.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import {
  fetchAdminUsers,
  fetchAdminStats,
  updateAdminUser,
  type AdminUserUpdatePayload,
} from "../api/profileApi";
import { queryKeys } from "../lib/queryKeys";
import { adminUserSchema, adminStatsSchema } from "../schemas/admin";
import { z } from "zod";

/**
 * Fetch admin users list with Zod validation.
 */
export function useAdminUsers() {
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.admin.users,
    queryFn: async () => {
      const raw = await fetchAdminUsers(authenticatedFetch);
      return z.array(adminUserSchema).parse(raw);
    },
    staleTime: 30 * 1000,
  });
}

/**
 * Fetch admin stats with Zod validation.
 */
export function useAdminStats() {
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useQuery({
    queryKey: queryKeys.admin.stats,
    queryFn: async () => {
      const raw = await fetchAdminStats(authenticatedFetch);
      return adminStatsSchema.parse(raw);
    },
    staleTime: 30 * 1000,
  });
}

/**
 * Update an admin user (tier, admin status, etc.) and invalidate related caches.
 */
export function useUpdateAdminUser() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      userId,
      payload,
    }: {
      userId: string;
      payload: AdminUserUpdatePayload;
    }) => updateAdminUser(authenticatedFetch, userId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.stats });
    },
  });
}
