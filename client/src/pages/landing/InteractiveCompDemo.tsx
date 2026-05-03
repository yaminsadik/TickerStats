import { useState, useMemo, useCallback, memo } from "react";
import { Lock, Download, X } from "lucide-react";
import {
  DEMO_TICKERS,
  getDemoRows,
  metricGroups,
} from "./landingData";
import type { DemoTicker, MetricGroup, DemoRow } from "./landingData";

// ─── Types ──────────────────────────────────────────────────────────────────

type TimeWindow = "1D" | "1W" | "1M" | "1Y";
const TIME_WINDOWS: TimeWindow[] = ["1D", "1W", "1M", "1Y"];
const DEFAULT_TICKERS: DemoTicker[] = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"];
const ALL_METRIC_GROUPS: MetricGroup[] = ["valuation", "profitability", "performance"];

// ─── Format helper ──────────────────────────────────────────────────────────

function fmtCell(value: number, fmt: string): string {
  if (fmt === "$") return `$${value.toFixed(2)}`;
  if (fmt === "%") return `${value >= 0 ? "" : ""}${value.toFixed(2)}%`;
  if (fmt === "x") return value.toFixed(1);
  return value.toString();
}

function cellColor(value: number, fmt: string): string {
  if (fmt === "%") {
    if (value >= 20) return "text-emerald-400";
    if (value <= -10) return "text-red-400";
    if (value < 0) return "text-red-300";
  }
  return "text-slate-300";
}

// ─── Ticker chip ────────────────────────────────────────────────────────────

const TickerChip = memo(function TickerChip({
  ticker,
  active,
  onToggle,
  disabled,
}: {
  ticker: string;
  active: boolean;
  onToggle: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onToggle}
      disabled={disabled && !active}
      aria-pressed={active}
      className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-950 ${
        active
          ? "bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20"
          : disabled
            ? "bg-slate-800/40 border-slate-700/40 text-slate-600 cursor-not-allowed"
            : "bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
      }`}
    >
      {ticker}
    </button>
  );
});

// ─── Export locked tooltip ──────────────────────────────────────────────────

function ExportButton() {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setShowTooltip((v) => !v)}
        onBlur={() => setShowTooltip(false)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/60 border border-slate-700/60 text-slate-500 cursor-not-allowed transition-colors hover:bg-slate-800"
        aria-label="Export requires a paid unlock"
      >
        <Download className="w-3.5 h-3.5" />
        Export
        <Lock className="w-3 h-3 text-slate-600" />
      </button>
      {showTooltip && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-200 whitespace-nowrap shadow-xl z-20"
          role="tooltip"
        >
          <button
            onClick={() => setShowTooltip(false)}
            className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-slate-700 flex items-center justify-center hover:bg-slate-600"
            aria-label="Close tooltip"
          >
            <X className="w-2.5 h-2.5 text-slate-300" />
          </button>
          <Lock className="w-3 h-3 inline mr-1 text-amber-400" />
          Export requires a <span className="text-blue-400 font-semibold">paid unlock</span>
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-slate-800" />
        </div>
      )}
    </div>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function InteractiveCompDemo() {
  const [selectedTickers, setSelectedTickers] = useState<Set<DemoTicker>>(
    () => new Set(DEFAULT_TICKERS),
  );
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("1Y");
  const [activeGroups, setActiveGroups] = useState<Set<MetricGroup>>(
    () => new Set<MetricGroup>(["valuation", "performance"]),
  );

  const toggleTicker = useCallback(
    (t: DemoTicker) => {
      setSelectedTickers((prev) => {
        const next = new Set(prev);
        if (next.has(t)) {
          if (next.size <= 3) return prev; // min 3
          next.delete(t);
        } else {
          if (next.size >= 5) return prev; // max 5
          next.add(t);
        }
        return next;
      });
    },
    [],
  );

  const toggleGroup = useCallback((g: MetricGroup) => {
    setActiveGroups((prev) => {
      const next = new Set(prev);
      if (next.has(g)) {
        if (next.size <= 1) return prev; // min 1
        next.delete(g);
      } else {
        next.add(g);
      }
      return next;
    });
  }, []);

  const rows = useMemo(
    () =>
      getDemoRows(
        DEMO_TICKERS.filter((t) => selectedTickers.has(t)) as DemoTicker[],
        timeWindow,
      ),
    [selectedTickers, timeWindow],
  );

  // Build visible columns
  const visibleCols = useMemo(() => {
    const cols: { key: keyof DemoRow; label: string; fmt: string }[] = [
      { key: "symbol", label: "Symbol", fmt: "" },
      { key: "price", label: "Price", fmt: "$" },
      { key: "marketCap", label: "Market Cap", fmt: "" },
    ];
    for (const g of ALL_METRIC_GROUPS) {
      if (activeGroups.has(g)) {
        cols.push(...metricGroups[g].columns);
      }
    }
    return cols;
  }, [activeGroups]);

  return (
    <div className="space-y-5">
      {/* Controls bar */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        {/* Ticker chips */}
        <div className="flex flex-wrap gap-2" role="group" aria-label="Select tickers to compare">
          {DEMO_TICKERS.map((t) => (
            <TickerChip
              key={t}
              ticker={t}
              active={selectedTickers.has(t)}
              onToggle={() => toggleTicker(t)}
              disabled={selectedTickers.size >= 5}
            />
          ))}
          <span className="text-[10px] text-slate-600 self-center ml-1">
            {selectedTickers.size}/5 selected
          </span>
        </div>

        {/* Time window + metric toggles + export */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Time window */}
          <div
            className="inline-flex rounded-lg border border-slate-700 overflow-hidden"
            role="tablist"
            aria-label="Performance time window"
          >
            {TIME_WINDOWS.map((w) => (
              <button
                key={w}
                role="tab"
                aria-selected={timeWindow === w}
                onClick={() => setTimeWindow(w)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset ${
                  timeWindow === w
                    ? "bg-blue-600 text-white"
                    : "bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-700/60"
                }`}
              >
                {w}
              </button>
            ))}
          </div>

          {/* Metric group toggles */}
          <div className="flex gap-2" role="group" aria-label="Metric groups">
            {ALL_METRIC_GROUPS.map((g) => (
              <button
                key={g}
                aria-pressed={activeGroups.has(g)}
                onClick={() => toggleGroup(g)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  activeGroups.has(g)
                    ? "bg-slate-700 border-slate-600 text-slate-100"
                    : "bg-slate-800/40 border-slate-700/40 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
                }`}
              >
                {metricGroups[g].label}
              </button>
            ))}
          </div>

          <ExportButton />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-700/60 bg-slate-900/80 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-800/50">
                {visibleCols.map((col) => (
                  <th
                    key={col.key}
                    className={`px-3 py-2.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider whitespace-nowrap ${
                      col.key === "symbol" ? "text-left" : "text-right"
                    }`}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.symbol}
                  className="border-t border-slate-800/50 hover:bg-slate-800/20 transition-colors"
                >
                  {visibleCols.map((col) => {
                    const raw = row[col.key];
                    const display =
                      col.key === "symbol"
                        ? String(raw)
                        : col.key === "marketCap"
                          ? String(raw)
                          : fmtCell(raw as number, col.fmt);
                    const color =
                      col.key === "symbol"
                        ? "text-slate-100 font-semibold"
                        : col.key === "marketCap"
                          ? "text-slate-300"
                          : cellColor(raw as number, col.fmt);

                    return (
                      <td
                        key={col.key}
                        className={`px-3 py-2.5 whitespace-nowrap ${
                          col.key === "symbol" ? "text-left" : "text-right"
                        } ${color}`}
                      >
                        {display}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
