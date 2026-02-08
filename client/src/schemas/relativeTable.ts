import { z } from "zod";

/**
 * Zod schemas for the relative table API response.
 * Mirrors interfaces in types/api.ts.
 */

const perfRequestSchema = z.object({
  period: z.string(),
  metrics: z.array(z.string()),
});

const requestedParamsSchema = z.object({
  symbols: z.array(z.string()),
  fields: z.array(z.string()),
  perf: perfRequestSchema.nullable(),
  dcf: z.boolean(),
});

const rowDataSchema = z.object({
  symbol: z.string(),
  snapshot: z.record(z.string(), z.number().nullable()),
  performance: z.record(z.string(), z.number().nullable()).nullable(),
  dcf: z.record(z.string(), z.number().nullable()).nullable(),
  missingFields: z.array(z.string()).default([]),
  missingPerf: z.array(z.string()).nullable().optional(),
  error: z.string().nullable(),
});

export const relativeTableResponseSchema = z.object({
  asOf: z.string(),
  units: z.record(z.string(), z.string()),
  requested: requestedParamsSchema,
  rows: z.array(rowDataSchema),
});

export type RelativeTableResponseParsed = z.infer<
  typeof relativeTableResponseSchema
>;
