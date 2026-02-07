import { useState, useRef, useEffect } from "react";
import { HelpCircle } from "lucide-react";
import { PERF_PERIODS, PERIOD_LABELS, type PerfPeriod } from "../types/api";
import type { ExportFormat } from "../api/client";
import { DcfExplainerModal } from "./DcfExplainerModal";
import { PerformanceExplainerModal } from "./PerformanceExplainerModal";

interface ControlsProps {
  showPerf: boolean;
  onShowPerfChange: (show: boolean) => void;
  showDcf: boolean;
  onShowDcfChange: (show: boolean) => void;
  perfPeriod: PerfPeriod;
  onPerfPeriodChange: (period: PerfPeriod) => void;
  onCompare: () => void;
  onExport: (format: ExportFormat) => void;
  isLoading: boolean;
  canCompare: boolean;
  canExport: boolean;
}

export function Controls({
  showPerf,
  onShowPerfChange,
  showDcf,
  onShowDcfChange,
  perfPeriod,
  onPerfPeriodChange,
  onCompare,
  onExport,
  isLoading,
  canCompare,
  canExport,
}: ControlsProps) {
  const [showDcfExplainer, setShowDcfExplainer] = useState(false);
  const [showPerfExplainer, setShowPerfExplainer] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  // Close export menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    };
    if (showExportMenu) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showExportMenu]);

  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Performance Toggle */}
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <div className="relative">
            <input
              type="checkbox"
              checked={showPerf}
              onChange={(e) => onShowPerfChange(e.target.checked)}
              className="sr-only"
            />
            <div
              className={`w-10 h-6 rounded-full transition-colors ${
                showPerf ? "bg-green-500" : "bg-gray-300"
              }`}
            />
            <div
              className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                showPerf ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </div>
          <span className="text-sm font-medium text-gray-700">
            Include Performance
          </span>
        </label>
        <button
          onClick={() => setShowPerfExplainer(true)}
          className="p-1 text-green-600 hover:text-green-700 hover:bg-green-50 rounded transition-colors"
          title="Learn how performance metrics are calculated"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </div>

      {/* DCF Toggle */}
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <div className="relative">
            <input
              type="checkbox"
              checked={showDcf}
              onChange={(e) => onShowDcfChange(e.target.checked)}
              className="sr-only"
            />
            <div
              className={`w-10 h-6 rounded-full transition-colors ${
                showDcf ? "bg-purple-500" : "bg-gray-300"
              }`}
            />
            <div
              className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                showDcf ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </div>
          <span className="text-sm font-medium text-gray-700">Include DCF</span>
        </label>
        <button
          onClick={() => setShowDcfExplainer(true)}
          className="p-1 text-purple-600 hover:text-purple-700 hover:bg-purple-50 rounded transition-colors"
          title="Learn how DCF is calculated"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </div>

      {/* Period Dropdown */}
      {showPerf && (
        <div className="flex items-center gap-2">
          <label htmlFor="period" className="text-sm font-medium text-gray-700">
            Period:
          </label>
          <select
            id="period"
            value={perfPeriod}
            onChange={(e) => onPerfPeriodChange(e.target.value as PerfPeriod)}
            className="px-3 py-1.5 text-sm text-gray-900 bg-white border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {PERF_PERIODS.map((period) => (
              <option key={period} value={period}>
                {PERIOD_LABELS[period]}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex items-center gap-2 ml-auto">
        {/* Export Dropdown */}
        <div className="relative" ref={exportMenuRef}>
          <button
            onClick={() => setShowExportMenu((prev) => !prev)}
            disabled={!canExport}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            Export
            <svg className="w-3 h-3 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {showExportMenu && (
            <div className="absolute right-0 mt-1 w-40 bg-white border border-gray-200 rounded-lg shadow-lg z-20 py-1">
              {([
                { format: "csv" as const, label: "CSV (.csv)" },
                { format: "xlsx" as const, label: "Excel (.xlsx)" },
                { format: "pdf" as const, label: "PDF (.pdf)" },
              ]).map(({ format, label }) => (
                <button
                  key={format}
                  onClick={() => {
                    onExport(format);
                    setShowExportMenu(false);
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Compare Button */}
        <button
          onClick={onCompare}
          disabled={!canCompare || isLoading}
          className="inline-flex items-center gap-1.5 px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <>
              <svg
                className="w-4 h-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Loading...
            </>
          ) : (
            <>
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                />
              </svg>
              Compare
            </>
          )}
        </button>
      </div>

      {/* Explainer Modals */}
      <DcfExplainerModal
        isOpen={showDcfExplainer}
        onClose={() => setShowDcfExplainer(false)}
      />
      <PerformanceExplainerModal
        isOpen={showPerfExplainer}
        onClose={() => setShowPerfExplainer(false)}
      />
    </div>
  );
}
