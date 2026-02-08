import { useState, useMemo } from "react";
import { CheckCircle, Lock, ArrowRight } from "lucide-react";

// ─── Feature gate data ──────────────────────────────────────────────────────

interface FeatureRow {
  label: string;
  free: boolean;
  pro: boolean;
}

const gatedFeatures: FeatureRow[] = [
  { label: "Comp table access", free: true, pro: true },
  { label: "AI pitch deck generation", free: true, pro: true },
  { label: "DCF valuation", free: true, pro: true },
  { label: "Export (CSV, XLSX, PDF, PPTX)", free: false, pro: true },
  { label: "Premium models (GPT-5.2, Gemini 3 Pro)", free: false, pro: true },
  { label: "Unlimited compares", free: false, pro: true },
];

// ─── Main component ─────────────────────────────────────────────────────────

export default function PricingCalculator() {
  const [compares, setCompares] = useState(5);
  const [decks, setDecks] = useState(3);

  const recommendation = useMemo(() => {
    if (compares <= 5 && decks <= 3) {
      return {
        tier: "free" as const,
        label: "Free covers you",
        color: "emerald",
        message: "You're within Free tier limits.",
      };
    }
    return {
      tier: "pro" as const,
      label: "You need Pro",
      color: "blue",
      message: `$29/month — unlocks unlimited compares, ${
        decks > 3 ? `${Math.min(decks, 100)} decks/month` : "100 decks/month"
      }, and all exports.`,
    };
  }, [compares, decks]);

  const isFree = recommendation.tier === "free";

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/80 p-6 md:p-8">
      <h3 className="text-lg font-bold text-white mb-1">
        How much will you use?
      </h3>
      <p className="text-sm text-slate-400 mb-6">
        Slide to estimate your monthly usage and see which plan fits.
      </p>

      {/* Sliders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8">
        {/* Compares slider */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label
              htmlFor="compares-slider"
              className="text-xs font-semibold text-slate-300"
            >
              Compares / month
            </label>
            <span
              className={`text-sm font-bold tabular-nums ${
                compares > 5 ? "text-blue-400" : "text-emerald-400"
              }`}
            >
              {compares}
            </span>
          </div>
          <input
            id="compares-slider"
            type="range"
            min={0}
            max={50}
            step={1}
            value={compares}
            onChange={(e) => setCompares(Number(e.target.value))}
            className="w-full accent-blue-500 h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-slate-900 [&::-webkit-slider-thumb]:shadow-lg"
            aria-label="Number of compares per month"
          />
          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
            <span>0</span>
            <span className="text-slate-500">Free limit: 5</span>
            <span>50</span>
          </div>
        </div>

        {/* Decks slider */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label
              htmlFor="decks-slider"
              className="text-xs font-semibold text-slate-300"
            >
              Decks / month
            </label>
            <span
              className={`text-sm font-bold tabular-nums ${
                decks > 3 ? "text-blue-400" : "text-emerald-400"
              }`}
            >
              {decks}
            </span>
          </div>
          <input
            id="decks-slider"
            type="range"
            min={0}
            max={50}
            step={1}
            value={decks}
            onChange={(e) => setDecks(Number(e.target.value))}
            className="w-full accent-blue-500 h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-slate-900 [&::-webkit-slider-thumb]:shadow-lg"
            aria-label="Number of decks per month"
          />
          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
            <span>0</span>
            <span className="text-slate-500">Free limit: 3</span>
            <span>50</span>
          </div>
        </div>
      </div>

      {/* Recommendation badge */}
      <div
        className={`rounded-lg p-4 mb-6 border transition-colors duration-300 ${
          isFree
            ? "bg-emerald-500/10 border-emerald-500/30"
            : "bg-blue-500/10 border-blue-500/30"
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              isFree ? "bg-emerald-500/20" : "bg-blue-500/20"
            }`}
          >
            {isFree ? (
              <CheckCircle className="w-4 h-4 text-emerald-400" />
            ) : (
              <ArrowRight className="w-4 h-4 text-blue-400" />
            )}
          </div>
          <div>
            <div
              className={`text-sm font-bold ${
                isFree ? "text-emerald-300" : "text-blue-300"
              }`}
            >
              {recommendation.label}
            </div>
            <div className="text-xs text-slate-400">
              {recommendation.message}
            </div>
          </div>
        </div>
      </div>

      {/* Feature gating comparison */}
      <div className="space-y-0">
        <div className="grid grid-cols-[1fr_60px_60px] gap-2 text-[10px] uppercase tracking-wider text-slate-500 font-semibold pb-2 border-b border-slate-800">
          <span>Feature</span>
          <span className="text-center">Free</span>
          <span className="text-center">Pro</span>
        </div>
        {gatedFeatures.map((f) => (
          <div
            key={f.label}
            className="grid grid-cols-[1fr_60px_60px] gap-2 py-2 border-b border-slate-800/50 items-center"
          >
            <span className="text-xs text-slate-300">{f.label}</span>
            <span className="flex justify-center">
              {f.free ? (
                <CheckCircle className="w-4 h-4 text-emerald-400" />
              ) : (
                <Lock className="w-3.5 h-3.5 text-slate-600" />
              )}
            </span>
            <span className="flex justify-center">
              {f.pro ? (
                <CheckCircle className="w-4 h-4 text-blue-400" />
              ) : (
                <Lock className="w-3.5 h-3.5 text-slate-600" />
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
