/**
 * React Query mutation hooks for BrowsePage operations.
 * Wraps api/userApi functions with cache invalidation.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import {
  createSavedAnalysis,
  addToWatchlist,
  type SaveAnalysisPayload,
} from "../api/userApi";
import { getExportUrl, type ExportFormat } from "../api/client";
import type { FetchRelativeParams } from "../api/client";
import { queryKeys } from "../lib/queryKeys";

/**
 * Save a search (analysis) and invalidate related caches.
 */
export function useSaveSearch() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: SaveAnalysisPayload) =>
      createSavedAnalysis(authenticatedFetch, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.savedAnalyses });
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}

/**
 * Add a ticker to the watchlist and invalidate related caches.
 */
export function useAddToWatchlist() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ticker: string) =>
      addToWatchlist(authenticatedFetch, ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist });
    },
  });
}

/**
 * Export the relative table as a file (CSV/XLSX/PDF).
 * Returns the Blob so the caller can trigger the download.
 */
export function useExportTable() {
  const { authenticatedFetch } = useAuthenticatedFetch();

  return useMutation({
    mutationFn: async ({
      params,
      format,
    }: {
      params: FetchRelativeParams;
      format: ExportFormat;
    }) => {
      const url = getExportUrl(params, format);
      const res = await authenticatedFetch(url);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(
          (body as any).detail || `Export failed (${res.status})`,
        );
      }
      const blob = await res.blob();

      // Determine filename from Content-Disposition or fallback
      const disposition = res.headers.get("Content-Disposition");
      const filenameMatch = disposition?.match(/filename="?([^"]+)"?/);
      const filename = filenameMatch?.[1] ?? `export.${format}`;

      // Trigger browser download
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    },
  });
}
