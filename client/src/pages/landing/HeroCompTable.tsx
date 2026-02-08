import { useState, useEffect, useRef, memo } from "react";
import { CheckCircle, AlertTriangle } from "lucide-react";
import { heroRows, HERO_TIMESTAMP, HERO_TICKER_COUNT } from "./landingData";
import type { HeroRow } from "./landingData";

// ─── Format helpers ─────────────────────────────────────────────────────────

function fmtNum(v: number | null, suffix = ""): string {
  if (v === null) return "—";
  if (suffix === "%") return `${v.toFixed(2)}%`;
  return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + suffix;
}

function fmtPrice(v: number): string {
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ─── Column definitions ─────────────────────────────────────────────────────

interface ColDef {
  key: string;
  label: string;
  group: "core" | "valuation" | "profitability" | "risk" | "dcf";
  align: "left" | "right";
  getValue: (r: HeroRow) => string;
  getSignal?: (r: HeroRow) => "ok" | "warn" | null;
  colorValue?: (r: HeroRow) => string | null;
}

const columns: ColDef[] = [
  {
    key: "symbol",
    label: "Symbol",
    group: "core",
    align: "left",
    getValue: (r) => r.symbol,
  },
  {
    key: "price",
    label: "Price",
    group: "core",
    align: "right",
    getValue: (r) => fmtPrice(r.price),
  },
  {
    key: "marketCap",
    label: "Market Cap",
    group: "core",
    align: "right",
    getValue: (r) => r.marketCap,
  },
  {
    key: "forwardPE",
    label: "Fwd P/E",
    group: "valuation",
    align: "right",
    getValue: (r) => fmtNum(r.forwardPE),
    getSignal: (r) => (r.peOk ? "ok" : null),
  },
  {
    key: "ps",
    label: "P/S",
    group: "valuation",
    align: "right",
    getValue: (r) => fmtNum(r.ps),
    getSignal: (r) => (r.psOk ? "ok" : null),
  },
  {
    key: "profitMargin",
    label: "Profit Margin",
    group: "profitability",
    align: "right",
    getValue: (r) => fmtNum(r.profitMargin, "%"),
    getSignal: (r) => (r.profitMarginWarn ? "warn" : "ok"),
    colorValue: (r) =>
      r.profitMarginWarn
        ? "text-amber-400"
        : r.profitMargin >= 20
          ? "text-emerald-400"
          : null,
  },
  {
    key: "returnPct",
    label: "Return",
    group: "risk",
    align: "right",
    getValue: (r) => fmtNum(r.returnPct, "%"),
    colorValue: (r) =>
      r.returnPct >= 0 ? "text-emerald-400" : "text-red-400",
  },
  {
    key: "volatility",
    label: "Volatility",
    group: "risk",
    align: "right",
    getValue: (r) => fmtNum(r.volatility, "%"),
  },
  {
    key: "maxDrawdown",
    label: "Max Drawdown",
    group: "risk",
    align: "right",
    getValue: (r) => fmtNum(r.maxDrawdown, "%"),
    colorValue: (r) =>
      r.maxDrawdown <= -20 ? "text-red-400" : null,
  },
  {
    key: "dcfValue",
    label: "DCF Value",
    group: "dcf",
    align: "right",
    getValue: (r) => fmtPrice(r.dcfValue),
  },
  {
    key: "dcfUpside",
    label: "DCF Upside",
    group: "dcf",
    align: "right",
    getValue: (r) => fmtNum(r.dcfUpside, "%"),
    colorValue: (r) =>
      r.dcfUpside >= 0 ? "text-emerald-400" : "text-red-400",
  },
];

// ─── Signal badge ───────────────────────────────────────────────────────────

const SignalBadge = memo(function SignalBadge({
  type,
}: {
  type: "ok" | "warn";
}) {
  if (type === "ok") {
    return (
      <CheckCircle
        className="w-3.5 h-3.5 text-emerald-400 inline-block mr-1 flex-shrink-0"
        aria-label="Healthy metric"
      />
    );
  }
  return (
    <AlertTriangle
      className="w-3.5 h-3.5 text-amber-400 inline-block mr-1 flex-shrink-0"
      aria-label="Outlier metric"
    />
  );
});

// ─── Row component ──────────────────────────────────────────────────────────

const HeroTableRow = memo(function HeroTableRow({
  row,
  hoveredCol,
}: {
  row: HeroRow;
  hoveredCol: string | null;
}) {
  return (
    <tr className="border-b border-slate-800/60 hover:bg-slate-800/20 transition-colors duration-150">
      {columns.map((col) => {
        const signal = col.getSignal?.(row) ?? null;
        const colorClass = col.colorValue?.(row) ?? "text-slate-300";
        const isDcf = col.group === "dcf";
        const isHovered = hoveredCol === col.key;

        return (
          <td
            key={col.key}
            className={`px-3 py-2.5 text-xs whitespace-nowrap transition-colors duration-150 ${
              col.align === "left" ? "text-left" : "text-right"
            } ${col.key === "symbol" ? "font-semibold text-slate-100" : colorClass} ${
              isDcf ? "bg-blue-500/[0.04]" : ""
            } ${isHovered ? "bg-slate-700/30" : ""}`}
          >
            <span className="inline-flex items-center gap-0.5">
              {signal && <SignalBadge type={signal} />}
              {col.getValue(row)}
            </span>
          </td>
        );
      })}
    </tr>
  );
});

// ─── Main component ─────────────────────────────────────────────────────────

export default function HeroCompTable() {
  const [hoveredCol, setHoveredCol] = useState<string | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [shimmerDone, setShimmerDone] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Intersection Observer for scroll reveal
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Respect reduced motion
    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReduced) {
      setIsVisible(true);
      setShimmerDone(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // End shimmer after animation
  useEffect(() => {
    if (!isVisible) return;
    const t = setTimeout(() => setShimmerDone(true), 1500);
    return () => clearTimeout(t);
  }, [isVisible]);

  return (
    <div
      ref={ref}
      className={`relative rounded-xl border border-slate-700/60 bg-slate-900/80 backdrop-blur-sm shadow-2xl overflow-hidden transition-all duration-700 ${
        isVisible
          ? "opacity-100 translate-y-0"
          : "opacity-0 translate-y-8"
      }`}
      role="img"
      aria-label="Preview of the TickerStats comp table showing healthcare stock data"
    >
      {/* Shimmer overlay */}
      {!shimmerDone && isVisible && (
        <div
          className="pointer-events-none absolute inset-0 z-10"
          aria-hidden="true"
        >
          <div className="hero-shimmer absolute inset-0" />
        </div>
      )}

      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-800/60 border-b border-slate-700/50">
        <span className="text-[11px] text-slate-400 font-medium">
          Data as of: {HERO_TIMESTAMP}
        </span>
        <span className="text-[11px] text-slate-500">
          {HERO_TICKER_COUNT} tickers
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs" role="presentation">
          <thead>
            <tr className="bg-slate-800/40">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2 font-semibold text-slate-400 text-[11px] uppercase tracking-wider whitespace-nowrap cursor-default select-none transition-colors duration-150 ${
                    col.align === "left" ? "text-left" : "text-right"
                  } ${col.group === "dcf" ? "bg-blue-500/[0.06]" : ""} ${
                    hoveredCol === col.key ? "bg-slate-700/30 text-slate-200" : ""
                  }`}
                  onMouseEnter={() => setHoveredCol(col.key)}
                  onMouseLeave={() => setHoveredCol(null)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {col.key === "dcfValue" || col.key === "dcfUpside" ? (
                      <span className="text-[9px] text-blue-400/60 font-normal normal-case tracking-normal">
                        DCF
                      </span>
                    ) : null}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {heroRows.map((row) => (
              <HeroTableRow
                key={row.symbol}
                row={row}
                hoveredCol={hoveredCol}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Bottom glow line */}
      <div
        className="h-px bg-gradient-to-r from-transparent via-blue-500/40 to-transparent"
        aria-hidden="true"
      />
    </div>
  );
}
