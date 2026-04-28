/**
 * ModelReasoningBar — compact ChatGPT-style toolbar for choosing
 * an AI model and reasoning effort.  Two small popover-trigger buttons
 * sit in a horizontal row:
 *
 *   [ 🟢 GM  Gemini 3 Flash ▾ ]   [ 🧠 Balanced ▾ ]
 *
 * Clicking either opens a dropdown popover with the full list.
 */

import { useState, useRef, useEffect, useMemo } from "react";
import { ChevronDown, Search, Brain, Cpu } from "lucide-react";
import {
  FREE_MODEL_OPTIONS,
  PRO_MODEL_OPTIONS,
  PROVIDER_CHIP,
  getModelBadges,
  MODEL_RECOMMENDED,
  getQualityOptions,
  getReasoningNote,
  type ModelOption,
  type Quality,
} from "../config/modelConfig";
import type { DeckDraftConfig } from "../stores/deckDraft";

interface ModelReasoningBarProps {
  config: DeckDraftConfig;
  setConfig: React.Dispatch<React.SetStateAction<DeckDraftConfig>>;
  tier: string;
}

export default function ModelReasoningBar({
  config,
  setConfig,
  tier,
}: ModelReasoningBarProps) {
  // ----- state -----
  const [modelOpen, setModelOpen] = useState(false);
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const [modelSearch, setModelSearch] = useState("");
  const modelRef = useRef<HTMLDivElement>(null);
  const reasoningRef = useRef<HTMLDivElement>(null);

  // ----- derived -----
  const isPro = tier === "pro" || tier === "enterprise";

  const modelOptions = useMemo(() => {
    if (isPro) return [...PRO_MODEL_OPTIONS, ...FREE_MODEL_OPTIONS];
    return FREE_MODEL_OPTIONS;
  }, [isPro]);

  const selectedModel = useMemo(
    () => modelOptions.find((m) => m.value === config.model),
    [modelOptions, config.model],
  );

  const filteredModels = useMemo(() => {
    const q = modelSearch.trim().toLowerCase();
    if (!q) return modelOptions;
    return modelOptions.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        o.provider.toLowerCase().includes(q),
    );
  }, [modelOptions, modelSearch]);

  const proModels = useMemo(
    () =>
      filteredModels.filter((m) =>
        PRO_MODEL_OPTIONS.some((p) => p.value === m.value),
      ),
    [filteredModels],
  );
  const freeModels = useMemo(
    () =>
      filteredModels.filter((m) =>
        FREE_MODEL_OPTIONS.some((f) => f.value === m.value),
      ),
    [filteredModels],
  );

  const qualityOpts = useMemo(
    () => getQualityOptions(config.provider, config.model || ""),
    [config.provider, config.model],
  );

  const qualityLabel = useMemo(
    () =>
      qualityOpts.find((o) => o.value === config.quality)?.short ??
      config.quality,
    [qualityOpts, config.quality],
  );

  const reasoningDisabled = qualityOpts.length <= 1;

  // ----- close on outside click -----
  useEffect(() => {
    if (!modelOpen && !reasoningOpen) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as Node;
      if (modelOpen && modelRef.current && !modelRef.current.contains(t))
        setModelOpen(false);
      if (
        reasoningOpen &&
        reasoningRef.current &&
        !reasoningRef.current.contains(t)
      )
        setReasoningOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [modelOpen, reasoningOpen]);

  // ----- keep quality valid when model changes -----
  useEffect(() => {
    const allowed = qualityOpts.map((o) => o.value);
    if (!allowed.includes(config.quality)) {
      setConfig((prev) => ({ ...prev, quality: qualityOpts[0].value }));
    }
  }, [qualityOpts, config.quality, setConfig]);

  // ----- render helpers -----
  const providerChip = PROVIDER_CHIP[config.provider];
  const recTier: "pro" | "free" = isPro ? "pro" : "free";

  function pickModel(option: ModelOption) {
    setConfig((prev) => ({
      ...prev,
      model: option.value,
      provider: option.provider,
    }));
    setModelOpen(false);
    setModelSearch("");
  }

  function renderModelList(list: ModelOption[], header?: string) {
    if (list.length === 0) return null;
    return (
      <>
        {header && (
          <div className="px-2 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            {header}
          </div>
        )}
        {list.map((option) => {
          const isSelected = option.value === config.model;
          const badges = getModelBadges(option.value, tier);
          const isRec = MODEL_RECOMMENDED[option.value] === recTier;
          const chip = PROVIDER_CHIP[option.provider];
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => pickModel(option)}
              className={`w-full text-left rounded-lg px-2 py-1.5 transition-colors ${
                isSelected
                  ? "bg-blue-500/15 text-blue-100"
                  : "text-slate-200 hover:bg-slate-800"
              }`}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className={`rounded border px-1 py-px text-[9px] font-bold leading-none ${chip.color}`}
                >
                  {chip.short}
                </span>
                <span className="text-sm font-medium truncate">
                  {option.short}
                </span>
                {isRec && (
                  <span className="ml-auto shrink-0 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-1.5 py-px text-[9px] font-medium text-emerald-300">
                    Rec
                  </span>
                )}
              </div>
              {badges.length > 0 && (
                <div className="mt-0.5 flex gap-1 pl-5">
                  {badges.map((b) => (
                    <span
                      key={b}
                      className="rounded-full border border-slate-600/60 bg-slate-800/60 px-1.5 py-px text-[9px] text-slate-400"
                    >
                      {b}
                    </span>
                  ))}
                </div>
              )}
            </button>
          );
        })}
      </>
    );
  }

  // ===================================================================
  return (
    <div className="flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/60 px-3 py-2">
      {/* ── Model trigger ── */}
      <div ref={modelRef} className="relative">
        <button
          type="button"
          onClick={() => {
            setModelOpen((v) => !v);
            setReasoningOpen(false);
          }}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 hover:border-slate-500 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        >
          <Cpu className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span
            className={`rounded border px-1 py-px text-[9px] font-bold leading-none ${providerChip.color}`}
          >
            {providerChip.short}
          </span>
          <span className="font-medium truncate max-w-[140px]">
            {selectedModel?.short || config.model || "Model"}
          </span>
          <ChevronDown className="w-3 h-3 text-slate-400 shrink-0" />
        </button>

        {modelOpen && (
          <div className="absolute z-30 mt-1 left-0 w-72 sm:w-80 rounded-xl border border-slate-600 bg-slate-900 shadow-xl shadow-black/40 overflow-hidden">
            {/* search */}
            <div className="p-2 border-b border-slate-700">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
                <input
                  value={modelSearch}
                  onChange={(e) => setModelSearch(e.target.value)}
                  placeholder="Search models..."
                  autoFocus
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 py-1.5 pl-8 pr-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
                />
              </div>
            </div>
            <div className="max-h-72 overflow-y-auto p-1.5 space-y-px">
              {isPro ? (
                <>
                  {renderModelList(proModels, "Pro models")}
                  {renderModelList(freeModels, "Standard models")}
                </>
              ) : (
                renderModelList(filteredModels)
              )}
              {filteredModels.length === 0 && (
                <div className="px-2 py-3 text-sm text-slate-400 text-center">
                  No models match your search.
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Reasoning trigger ── */}
      <div ref={reasoningRef} className="relative">
        <button
          type="button"
          disabled={reasoningDisabled}
          onClick={() => {
            setReasoningOpen((v) => !v);
            setModelOpen(false);
          }}
          className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/50 ${
            reasoningDisabled
              ? "border-slate-700/50 bg-slate-900/50 text-slate-500 cursor-default"
              : "border-blue-500/30 bg-blue-500/5 text-blue-200 hover:border-blue-400/50"
          }`}
        >
          <Brain className="w-3.5 h-3.5 shrink-0" />
          <span className="font-medium">{qualityLabel}</span>
          {!reasoningDisabled && (
            <ChevronDown className="w-3 h-3 shrink-0 text-blue-300/70" />
          )}
        </button>

        {reasoningOpen && !reasoningDisabled && (
          <div className="absolute z-30 mt-1 left-0 w-56 rounded-xl border border-slate-600 bg-slate-900 shadow-xl shadow-black/40 overflow-hidden">
            <div className="p-1.5 space-y-px">
              {qualityOpts.map((opt) => {
                const active = opt.value === config.quality;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      setConfig((prev) => ({
                        ...prev,
                        quality: opt.value as Quality,
                      }));
                      setReasoningOpen(false);
                    }}
                    className={`w-full text-left rounded-lg px-3 py-2 text-sm transition-colors ${
                      active
                        ? "bg-blue-500/15 text-blue-100"
                        : "text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    <span className="font-medium">{opt.label}</span>
                  </button>
                );
              })}
            </div>
            <div className="border-t border-slate-700 px-3 py-2">
              <p className="text-[11px] text-slate-400 leading-relaxed">
                {getReasoningNote(config.provider)}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
