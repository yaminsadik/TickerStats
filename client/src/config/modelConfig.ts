/**
 * Model configuration for the currently active Gemini-only model surface.
 */

import type { DeckDraftConfig } from "../stores/deckDraft";

export type Provider = DeckDraftConfig["provider"];
export type Quality = DeckDraftConfig["quality"];

export type ModelOption = {
  value: string;
  provider: Provider;
  label: string;
  /** Short display name for compact UIs */
  short: string;
};

// ---------------------------------------------------------------------------
// Model lists
// ---------------------------------------------------------------------------

export const FREE_MODEL_OPTIONS: ModelOption[] = [
  { value: "gemini-3-flash-preview", provider: "gemini", label: "Gemini 3 Flash Preview (Vertex AI)", short: "Gemini 3 Flash" },
];

export const PRO_MODEL_OPTIONS: ModelOption[] = [
  { value: "gemini-3-flash-preview", provider: "gemini", label: "Gemini 3 Flash Preview (Vertex AI)", short: "Gemini 3 Flash" },
  { value: "gemini-3.1-pro-preview", provider: "gemini", label: "Gemini 3.1 Pro Preview (Vertex AI)", short: "Gemini 3.1 Pro" },
];

// ---------------------------------------------------------------------------
// Provider metadata
// ---------------------------------------------------------------------------

export const PROVIDER_LABELS: Record<Provider, string> = {
  gemini: "Google Gemini",
};

export const PROVIDER_CHIP: Record<Provider, { short: string; color: string }> = {
  gemini: { short: "GM", color: "bg-sky-500/20 text-sky-300 border-sky-400/40" },
};

// ---------------------------------------------------------------------------
// Quality / reasoning options (provider-specific)
// ---------------------------------------------------------------------------

export const QUALITY_OPTIONS_DEFAULT: { value: Quality; label: string; short: string }[] = [
  { value: "low", label: "Light", short: "Light" },
  { value: "medium", label: "Balanced", short: "Balanced" },
  { value: "high", label: "Deep", short: "Deep" },
];

export const QUALITY_OPTIONS_GEMINI_PRO: { value: Quality; label: string; short: string }[] = [
  { value: "low", label: "Light", short: "Light" },
  { value: "high", label: "Deep", short: "Deep" },
];

export const QUALITY_OPTIONS_GEMINI_FLASH = QUALITY_OPTIONS_DEFAULT;

// ---------------------------------------------------------------------------
// Badge metadata — quality-focused for Pro, cost-aware for Free
// ---------------------------------------------------------------------------

type BadgeSet = { free: string[]; pro: string[] };

const MODEL_BADGES: Record<string, BadgeSet> = {
  "gemini-3-flash-preview": { free: ["Vertex AI", "Low cost"], pro: ["Vertex AI", "Efficient"] },
  "gemini-3.1-pro-preview": { free: ["Vertex AI", "Preview"], pro: ["Vertex AI", "Preview"] },
};

export function getModelBadges(modelId: string, tier: string): string[] {
  const entry = MODEL_BADGES[modelId];
  if (!entry) return [];
  return tier === "pro" || tier === "enterprise" ? entry.pro : entry.free;
}

export const MODEL_RECOMMENDED: Record<string, "free" | "pro" | null> = {
  "gemini-3-flash-preview": "free",
  "gemini-3.1-pro-preview": "pro",
};

// ---------------------------------------------------------------------------
// Reasoning compatibility notes (pitch-deck-quality focused)
// ---------------------------------------------------------------------------

export function getReasoningNote(provider: Provider): string {
  void provider;
  return "Higher Gemini reasoning improves analytical depth and accuracy.";
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function getQualityOptions(provider: Provider, modelId: string) {
  void provider;
  return modelId === "gemini-3.1-pro-preview"
    ? QUALITY_OPTIONS_GEMINI_PRO
    : QUALITY_OPTIONS_GEMINI_FLASH;
}

export function resolveModelForRequest(
  provider: Provider,
  selectedModel: string | undefined,
  quality: Quality,
): string | undefined {
  void provider;
  void quality;
  return selectedModel;
}
