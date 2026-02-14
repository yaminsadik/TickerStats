/**
 * Model configuration — single source of truth for all client-side
 * model definitions, provider chips, quality options, and badge metadata.
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
  { value: "gpt-5-mini", provider: "openai", label: "GPT-5 Mini (OpenAI)", short: "GPT-5 Mini" },
  { value: "gemini-3-flash-preview", provider: "gemini", label: "Gemini 3 Flash (Google)", short: "Gemini 3 Flash" },
  { value: "deepseek-chat", provider: "deepseek", label: "DeepSeek V3.2", short: "DeepSeek V3.2" },
  { value: "claude-haiku-4-5", provider: "anthropic", label: "Claude Haiku 4.5 (Anthropic)", short: "Haiku 4.5" },
  { value: "glm-4.7-flash", provider: "zai", label: "GLM-4.7 Flash (Z.AI)", short: "GLM-4.7 Flash" },
  { value: "glm-4.7-flashx", provider: "zai", label: "GLM-4.7 FlashX (Z.AI)", short: "GLM-4.7 FlashX" },
];

export const PRO_MODEL_OPTIONS: ModelOption[] = [
  { value: "gpt-5.2", provider: "openai", label: "GPT-5.2 (OpenAI)", short: "GPT-5.2" },
  { value: "gemini-3-pro", provider: "gemini", label: "Gemini 3 Pro (Google)", short: "Gemini 3 Pro" },
  { value: "claude-sonnet-4-5", provider: "anthropic", label: "Claude Sonnet 4.5 (Anthropic)", short: "Sonnet 4.5" },
  { value: "glm-5", provider: "zai", label: "GLM-5 (Z.AI)", short: "GLM-5" },
];

// ---------------------------------------------------------------------------
// Provider metadata
// ---------------------------------------------------------------------------

export const PROVIDER_LABELS: Record<Provider, string> = {
  openai: "OpenAI",
  gemini: "Google Gemini",
  deepseek: "DeepSeek",
  zai: "Z.AI",
  anthropic: "Anthropic",
};

export const PROVIDER_CHIP: Record<Provider, { short: string; color: string }> = {
  openai: { short: "OA", color: "bg-emerald-500/20 text-emerald-300 border-emerald-400/40" },
  gemini: { short: "GM", color: "bg-sky-500/20 text-sky-300 border-sky-400/40" },
  deepseek: { short: "DS", color: "bg-indigo-500/20 text-indigo-300 border-indigo-400/40" },
  zai: { short: "ZA", color: "bg-orange-500/20 text-orange-300 border-orange-400/40" },
  anthropic: { short: "AN", color: "bg-violet-500/20 text-violet-300 border-violet-400/40" },
};

// ---------------------------------------------------------------------------
// Quality / reasoning options (provider-specific)
// ---------------------------------------------------------------------------

export const QUALITY_OPTIONS_DEFAULT: { value: Quality; label: string; short: string }[] = [
  { value: "low", label: "Light", short: "Light" },
  { value: "medium", label: "Balanced", short: "Balanced" },
  { value: "high", label: "Deep", short: "Deep" },
];

export const QUALITY_OPTIONS_OPENAI = QUALITY_OPTIONS_DEFAULT;

export const QUALITY_OPTIONS_DEEPSEEK: { value: Quality; label: string; short: string }[] = [
  { value: "medium", label: "Standard", short: "Standard" },
  { value: "high", label: "Deep reasoning", short: "Deep" },
];

export const QUALITY_OPTIONS_GEMINI_PRO: { value: Quality; label: string; short: string }[] = [
  { value: "low", label: "Light", short: "Light" },
  { value: "high", label: "Deep", short: "Deep" },
];

export const QUALITY_OPTIONS_GEMINI_FLASH = QUALITY_OPTIONS_DEFAULT;
export const QUALITY_OPTIONS_ANTHROPIC = QUALITY_OPTIONS_DEFAULT;
export const QUALITY_OPTIONS_ZAI = QUALITY_OPTIONS_DEFAULT;

// ---------------------------------------------------------------------------
// Badge metadata — quality-focused for Pro, cost-aware for Free
// ---------------------------------------------------------------------------

type BadgeSet = { free: string[]; pro: string[] };

const MODEL_BADGES: Record<string, BadgeSet> = {
  "gpt-5-mini":             { free: ["Fast", "Low cost"],         pro: ["Fast", "Efficient"] },
  "gemini-3-flash-preview": { free: ["Low cost", "Long context"], pro: ["Long context", "Efficient"] },
  "deepseek-chat":          { free: ["Fast", "Low cost"],         pro: ["Fast", "Efficient"] },
  "claude-haiku-4-5":       { free: ["Fast", "Low cost"],         pro: ["Fast", "Efficient"] },
  "glm-4.7-flash":          { free: ["Fast", "Free"],             pro: ["Fast", "Free"] },
  "glm-4.7-flashx":         { free: ["Balanced", "Long context"], pro: ["Balanced", "Long context"] },
  "gpt-5.2":                { free: ["Best quality"],             pro: ["Best quality"] },
  "gemini-3-pro":           { free: ["Best quality", "Long context"], pro: ["Best quality", "Long context"] },
  "claude-sonnet-4-5":      { free: ["Best quality"],             pro: ["Best quality"] },
  "glm-5":                  { free: ["Best quality", "Long context"], pro: ["Best quality", "Long context"] },
};

export function getModelBadges(modelId: string, tier: string): string[] {
  const entry = MODEL_BADGES[modelId];
  if (!entry) return [];
  return tier === "pro" || tier === "enterprise" ? entry.pro : entry.free;
}

export const MODEL_RECOMMENDED: Record<string, "free" | "pro" | null> = {
  "gpt-5-mini": "free",
  "gpt-5.2": "pro",
};

// ---------------------------------------------------------------------------
// Reasoning compatibility notes (pitch-deck-quality focused)
// ---------------------------------------------------------------------------

export function getReasoningNote(provider: Provider): string {
  switch (provider) {
    case "deepseek":
      return "Deeper reasoning unlocks more nuanced investment insights.";
    case "anthropic":
      return "More thinking budget leads to more thorough analysis.";
    case "gemini":
      return "Higher reasoning improves analytical depth and accuracy.";
    default:
      return "Higher reasoning produces deeper, more thoughtful analysis.";
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function getQualityOptions(provider: Provider, modelId: string) {
  if (provider === "openai") return QUALITY_OPTIONS_OPENAI;
  if (provider === "deepseek") return QUALITY_OPTIONS_DEEPSEEK;
  if (provider === "gemini") {
    return modelId === "gemini-3-pro" ? QUALITY_OPTIONS_GEMINI_PRO : QUALITY_OPTIONS_GEMINI_FLASH;
  }
  if (provider === "anthropic") return QUALITY_OPTIONS_ANTHROPIC;
  if (provider === "zai") return QUALITY_OPTIONS_ZAI;
  return QUALITY_OPTIONS_DEFAULT;
}

export function resolveModelForRequest(
  provider: Provider,
  selectedModel: string | undefined,
  quality: Quality,
): string | undefined {
  if (provider === "deepseek") {
    return quality === "high" ? "deepseek-reasoner" : "deepseek-chat";
  }
  return selectedModel;
}
