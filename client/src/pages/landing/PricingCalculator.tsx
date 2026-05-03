import { CheckCircle, Lock } from "lucide-react";

// ─── Feature gate data ──────────────────────────────────────────────────────

interface FeatureRow {
  label: string;
  free: boolean;
  pro: boolean;
}

const gatedFeatures: FeatureRow[] = [
  { label: "Comp table access", free: true, pro: true },
  { label: "First AI pitch deck", free: true, pro: true },
  { label: "DCF valuation", free: true, pro: true },
  { label: "Full deck preview", free: true, pro: true },
  { label: "2 PDF/PPTX deck exports", free: false, pro: true },
  { label: "No subscription required", free: true, pro: true },
];

// ─── Main component ─────────────────────────────────────────────────────────

export default function PricingCalculator() {
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/80 p-6 md:p-8">
      <h3 className="text-lg font-bold text-white mb-1">
        Pay when the deck is ready
      </h3>
      <p className="text-sm text-slate-400 mb-6">
        Generate a first deck free. Export the finished deck for one simple price.
      </p>

      <div className="rounded-lg p-4 mb-6 border bg-blue-500/10 border-blue-500/30">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-blue-500/20">
            <CheckCircle className="w-4 h-4 text-blue-300" />
          </div>
          <div>
            <div className="text-sm font-bold text-blue-300">
              $4.99 for 2 deck exports
            </div>
            <div className="text-xs text-slate-400">
              Two export credits, no monthly plan, no surprise renewal.
            </div>
          </div>
        </div>
      </div>

      {/* Feature gating comparison */}
      <div className="space-y-0">
        <div className="grid grid-cols-[1fr_60px_60px] gap-2 text-[10px] uppercase tracking-wider text-slate-500 font-semibold pb-2 border-b border-slate-800">
          <span>Feature</span>
          <span className="text-center">Free</span>
          <span className="text-center">Export</span>
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
