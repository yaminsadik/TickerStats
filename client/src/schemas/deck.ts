import { z } from "zod";

/**
 * Zod schemas for deck-related API responses.
 * Mirrors interfaces in api/userApi.ts and api/deckApi.ts.
 */

// -- Section (from deckApi.ts) ------------------------------------------------

export const sectionSchema = z
  .object({
    id: z.string(),
    name: z.string().optional(),
    label: z.string().optional(),
    description: z.string().nullable().optional(),
    default: z.boolean().optional(),
  })
  .transform((section) => ({
    id: section.id,
    name: section.name ?? section.label ?? section.id,
    description: section.description ?? "",
    default: section.default ?? false,
  }));

export type SectionParsed = z.infer<typeof sectionSchema>;

// -- DeckMeta / DeckFull (from userApi.ts) ------------------------------------

export const deckMetaSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  title: z.string(),
  llm_provider: z.string().nullable(),
  created_at: z.string(),
});

export const deckFullSchema = deckMetaSchema.extend({
  content: z.record(z.string(), z.unknown()),
});

export type DeckMetaParsed = z.infer<typeof deckMetaSchema>;
export type DeckFullParsed = z.infer<typeof deckFullSchema>;

// -- GenerateDeckResponse (from deckApi.ts) -----------------------------------

const bulletPointSchema = z.object({
  text: z.string(),
  source_needed: z.boolean(),
});

const slideSchema = z.object({
  title: z.string(),
  bullets: z.array(bulletPointSchema),
  speaker_notes: z.string().optional(),
});

const generatedSectionSchema = z.object({
  section_id: z.string(),
  section_name: z.string(),
  slides: z.array(slideSchema),
  citations: z.array(z.string()).optional(),
});

export const generateDeckResponseSchema = z.object({
  ticker: z.string(),
  company_name: z.string(),
  plan_tier: z.enum(["free", "pro", "enterprise"]).optional(),
  model_mode: z.enum(["auto", "specific"]).optional(),
  analysis_depth: z.enum(["low", "medium", "high"]).optional(),
  generated_at: z.string(),
  provider_used: z.object({
    provider: z.string(),
    model: z.string(),
    reasoning_level: z.string(),
  }),
  computed_inputs: z
    .object({
      comps_table: z.unknown().optional(),
    })
    .optional(),
  results: z.array(generatedSectionSchema),
  errors: z.array(z.string()).optional(),
  request_id: z.string().optional(),
  // Legacy format support
  metadata: z
    .object({
      ticker: z.string(),
      company_name: z.string(),
      generated_at: z.string(),
      provider: z.string(),
      model: z.string(),
    })
    .optional(),
  sections: z.array(generatedSectionSchema).optional(),
  warnings: z.array(z.string()).optional(),
});

export type GenerateDeckResponseParsed = z.infer<
  typeof generateDeckResponseSchema
>;
