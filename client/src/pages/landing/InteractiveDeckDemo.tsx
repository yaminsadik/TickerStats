import { useState, useCallback, useEffect, useRef } from "react";
import {
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  FileText,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Layers,
  Calculator,
} from "lucide-react";
import { deckSections } from "./landingData";

// ─── Section icon mapper ────────────────────────────────────────────────────

const sectionIcons: Record<string, React.ReactNode> = {
  overview: <FileText className="w-4 h-4" />,
  swot: <Layers className="w-4 h-4" />,
  bull: <TrendingUp className="w-4 h-4" />,
  bear: <TrendingDown className="w-4 h-4" />,
  relative: <BarChart3 className="w-4 h-4" />,
  dcf: <Calculator className="w-4 h-4" />,
};

// ─── Claim badge ────────────────────────────────────────────────────────────

function ClaimBadge({
  claim,
}: {
  claim: { text: string; verified: boolean; timestamp: string };
}) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-medium border ${
        claim.verified
          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
          : "bg-amber-500/10 border-amber-500/30 text-amber-400"
      }`}
    >
      {claim.verified ? (
        <CheckCircle className="w-3 h-3" />
      ) : (
        <AlertTriangle className="w-3 h-3" />
      )}
      <span className="max-w-[180px] truncate">{claim.text}</span>
      <span className="text-slate-500 hidden sm:inline">
        · {claim.timestamp}
      </span>
    </div>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function InteractiveDeckDemo() {
  const [activeSectionId, setActiveSectionId] = useState(deckSections[0].id);
  const [variationIndex, setVariationIndex] = useState<Record<string, number>>(
    () =>
      Object.fromEntries(deckSections.map((s) => [s.id, 0])),
  );
  const [isRegenerating, setIsRegenerating] = useState(false);
  const previewRef = useRef<HTMLDivElement>(null);

  const activeSection = deckSections.find((s) => s.id === activeSectionId)!;
  const currentVariation =
    activeSection.variations[variationIndex[activeSectionId] ?? 0];

  const handleRegenerate = useCallback(() => {
    setIsRegenerating(true);
    // Simulate regeneration delay
    setTimeout(() => {
      setVariationIndex((prev) => ({
        ...prev,
        [activeSectionId]:
          ((prev[activeSectionId] ?? 0) + 1) %
          activeSection.variations.length,
      }));
      setIsRegenerating(false);
    }, 600);
  }, [activeSectionId, activeSection.variations.length]);

  // Scroll preview to top on section change
  useEffect(() => {
    previewRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [activeSectionId]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-0 rounded-xl border border-slate-700/60 bg-slate-900/80 overflow-hidden min-h-[420px]">
      {/* Section list (left sidebar) */}
      <nav
        className="bg-slate-800/40 border-b md:border-b-0 md:border-r border-slate-700/50 p-3 flex md:flex-col gap-1 overflow-x-auto md:overflow-x-visible"
        aria-label="Deck sections"
        role="tablist"
      >
        <div className="hidden md:block text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-3 py-2">
          Deck Outline
        </div>
        {deckSections.map((section) => (
          <button
            key={section.id}
            role="tab"
            aria-selected={activeSectionId === section.id}
            onClick={() => setActiveSectionId(section.id)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
              activeSectionId === section.id
                ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/40 border border-transparent"
            }`}
          >
            <span
              className={
                activeSectionId === section.id
                  ? "text-blue-400"
                  : "text-slate-500"
              }
            >
              {sectionIcons[section.id]}
            </span>
            <span className="hidden sm:inline">{section.label}</span>
            <span className="sm:hidden">{section.label.split(" ")[0]}</span>
          </button>
        ))}
      </nav>

      {/* Preview pane (right) */}
      <div
        ref={previewRef}
        className="p-5 md:p-6 overflow-y-auto max-h-[520px]"
        role="tabpanel"
        aria-label={`${activeSection.label} preview`}
        aria-live="polite"
      >
        {/* Header + regenerate button */}
        <div className="flex items-start justify-between gap-3 mb-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-wider text-blue-400 font-semibold">
                {activeSection.label}
              </span>
              <span className="text-[10px] text-slate-600">
                Variation {(variationIndex[activeSectionId] ?? 0) + 1}/
                {activeSection.variations.length}
              </span>
            </div>
            <h4
              className={`text-sm font-bold text-slate-100 leading-snug transition-opacity duration-300 ${
                isRegenerating ? "opacity-40" : "opacity-100"
              }`}
            >
              {currentVariation.title}
            </h4>
          </div>
          <button
            onClick={handleRegenerate}
            disabled={isRegenerating}
            className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 border border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white transition-all disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            aria-label="Regenerate this section"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isRegenerating ? "animate-spin" : ""}`}
            />
            Regenerate
          </button>
        </div>

        {/* Bullets */}
        <ul
          className={`space-y-3 mb-5 transition-opacity duration-300 ${
            isRegenerating ? "opacity-30" : "opacity-100"
          }`}
        >
          {currentVariation.bullets.map((bullet, i) => (
            <li
              key={`${activeSectionId}-${variationIndex[activeSectionId]}-${i}`}
              className="flex items-start gap-2.5 text-xs text-slate-300 leading-relaxed"
            >
              <span className="text-blue-500 mt-0.5 flex-shrink-0">
                {i + 1}.
              </span>
              <span>{bullet}</span>
            </li>
          ))}
        </ul>

        {/* Speaker notes */}
        <div
          className={`rounded-lg bg-slate-800/50 border border-slate-700/40 p-3 mb-5 transition-opacity duration-300 ${
            isRegenerating ? "opacity-30" : "opacity-100"
          }`}
        >
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1.5">
            Speaker Notes
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            {currentVariation.speakerNotes}
          </p>
        </div>

        {/* Claim check badges */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2">
            Claim Checks
          </div>
          <div
            className={`flex flex-wrap gap-2 transition-opacity duration-300 ${
              isRegenerating ? "opacity-30" : "opacity-100"
            }`}
          >
            {currentVariation.claims.map((claim, i) => (
              <ClaimBadge
                key={`${activeSectionId}-${variationIndex[activeSectionId]}-${i}`}
                claim={claim}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
