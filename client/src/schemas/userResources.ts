import { z } from "zod";
import { relativeTableResponseSchema } from "./relativeTable";

/**
 * Zod schemas for user-scoped resources.
 * Mirrors interfaces in api/userApi.ts.
 */

// -- WatchlistItem ------------------------------------------------------------

export const watchlistItemSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  notes: z.string().nullable(),
  created_at: z.string(),
});

export type WatchlistItemParsed = z.infer<typeof watchlistItemSchema>;

// -- SavedAnalysis ------------------------------------------------------------

export const savedAnalysisSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().nullable(),
  symbols: z.array(z.string()),
  snapshot_fields: z.array(z.string()).nullable(),
  perf_periods: z.array(z.string()).nullable(),
  include_dcf: z.boolean(),
  snapshot_data: relativeTableResponseSchema.nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export type SavedAnalysisParsed = z.infer<typeof savedAnalysisSchema>;
