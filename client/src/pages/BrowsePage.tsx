import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  ChevronRight,
  TrendingUp,
  Settings,
  HelpCircle,
} from "lucide-react";
import { TickerInput } from "../components/TickerInput";
import { ColumnPicker } from "../components/ColumnPicker";
import { Controls } from "../components/Controls";
import { RelativeTable } from "../components/RelativeTable";
import SignalControls from "../components/SignalControls";
import SignalConfigDrawer from "../components/SignalConfigDrawer";
import { useRelativeTable } from "../hooks/useRelativeTable";
import { useSignalSettings } from "../hooks/useSignalSettings";
import { getExportUrl } from "../api/client";
import { Button, Card, Alert } from "../components/ui";
import { SNAPSHOT_FIELDS, PERF_METRICS, type PerfPeriod } from "../types/api";
import type { FetchRelativeParams } from "../api/client";

export default function BrowsePage() {
  const navigate = useNavigate();

  // Ticker input state
  const [tickers, setTickers] = useState<string[]>([]);

  // Tickers selected for relative valuation heatmap
  const [selectedForHeatmap, setSelectedForHeatmap] = useState<string[]>([]);

  // Heatmap customization options
  const [heatmapShowPerf, setHeatmapShowPerf] = useState(false);
  const [heatmapShowDcf, setHeatmapShowDcf] = useState(false);
  const [heatmapPerfPeriod, setHeatmapPerfPeriod] = useState<PerfPeriod>("3mo");
  const [showHeatmapConfig, setShowHeatmapConfig] = useState(false);

  // Column visibility state
  const [selectedFields, setSelectedFields] = useState<string[]>([
    ...SNAPSHOT_FIELDS,
  ]);
  const [selectedPerfMetrics, setSelectedPerfMetrics] = useState<string[]>([
    ...PERF_METRICS,
  ]);

  // Performance toggle and period
  const [showPerf, setShowPerf] = useState(false);
  const [perfPeriod, setPerfPeriod] = useState<PerfPeriod>("3mo");

  // DCF toggle
  const [showDcf, setShowDcf] = useState(false);

  // Column picker visibility
  const [showColumnPicker, setShowColumnPicker] = useState(false);

  // Signal config drawer visibility
  const [showSignalConfig, setShowSignalConfig] = useState(false);

  // Signal settings with localStorage persistence
  const {
    settings: signalSettings,
    toggleEnabled: toggleSignals,
    setGlobalMode: setSignalMode,
    updateRule: updateSignalRule,
    resetToDefaults: resetSignalSettings,
  } = useSignalSettings();

  // Query params for fetching - only set when Compare is clicked
  const [queryParams, setQueryParams] = useState<FetchRelativeParams | null>(
    null,
  );

  // Fetch data
  const { data, isLoading, error, isFetching } = useRelativeTable(queryParams);

  // Handle Compare button
  const handleCompare = useCallback(() => {
    if (tickers.length === 0) return;

    const params: FetchRelativeParams = {
      symbols: tickers,
      fields: selectedFields,
    };

    if (showPerf && selectedPerfMetrics.length > 0) {
      params.perf = selectedPerfMetrics;
      params.perfPeriod = perfPeriod;
    }

    if (showDcf) {
      params.dcf = true;
    }

    setQueryParams(params);
  }, [
    tickers,
    selectedFields,
    showPerf,
    selectedPerfMetrics,
    perfPeriod,
    showDcf,
  ]);

  // Handle Export button
  const handleExport = useCallback(() => {
    if (!queryParams || !data) return;

    const url = getExportUrl(queryParams);
    const link = document.createElement("a");
    link.href = url;
    link.download = `relative_table_${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [queryParams, data]);

  // Handle Generate Deck - navigate to wizard with selected ticker
  const handleGenerateDeck = useCallback(
    (ticker?: string) => {
      const selectedTicker =
        ticker || (tickers.length > 0 ? tickers[0] : undefined);
      if (selectedTicker) {
        // Pass ticker and only the selected comparables for heatmap
        const comparables = selectedForHeatmap.filter(
          (t) => t !== selectedTicker,
        );
        navigate("/deck/new", {
          state: {
            ticker: selectedTicker,
            comparables: comparables.length > 0 ? comparables : undefined,
            heatmapConfig:
              selectedForHeatmap.length > 0
                ? {
                    showPerf: heatmapShowPerf,
                    showDcf: heatmapShowDcf,
                    perfPeriod: heatmapPerfPeriod,
                  }
                : undefined,
          },
        });
      } else {
        navigate("/deck/new");
      }
    },
    [
      navigate,
      tickers,
      selectedForHeatmap,
      heatmapShowPerf,
      heatmapShowDcf,
      heatmapPerfPeriod,
    ],
  );

  return (
    <div className="space-y-6">
      {/* Page Header with CTA */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Browse Stocks</h1>
          <p className="text-slate-400 mt-1">
            Compare and analyze investment opportunities
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={() => handleGenerateDeck()}
            size="lg"
            className="flex items-center gap-2"
          >
            <FileText className="w-5 h-5" />
            Generate Deck
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Input Section */}
      <Card>
        <div className="grid gap-6">
          {/* Ticker Input */}
          <TickerInput
            tickers={tickers}
            onTickersChange={setTickers}
            disabled={isLoading}
          />

          {/* Relative Valuation Heatmap Selection */}
          {tickers.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-slate-300">
                  Select tickers for Relative Valuation Heatmap
                </label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setSelectedForHeatmap(tickers)}
                    className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    Select All
                  </button>
                  <button
                    onClick={() => setSelectedForHeatmap([])}
                    className="text-xs text-slate-400 hover:text-slate-300 transition-colors"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
                {tickers.map((ticker) => (
                  <label
                    key={ticker}
                    className="flex items-center gap-2 px-3 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 cursor-pointer transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={selectedForHeatmap.includes(ticker)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedForHeatmap([
                            ...selectedForHeatmap,
                            ticker,
                          ]);
                        } else {
                          setSelectedForHeatmap(
                            selectedForHeatmap.filter((t) => t !== ticker),
                          );
                        }
                      }}
                      className="w-4 h-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-900"
                    />
                    <span className="text-sm text-slate-300">{ticker}</span>
                  </label>
                ))}
              </div>

              {/* Selected tickers display */}
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <TrendingUp className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="text-sm font-medium text-blue-300">
                        Selected for Relative Valuation Heatmap
                      </h4>
                      <button
                        onClick={() => setShowHeatmapConfig(!showHeatmapConfig)}
                        className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1"
                      >
                        <Settings className="w-3.5 h-3.5" />
                        Configure
                      </button>
                    </div>
                    <p className="text-xs text-blue-300/70 mb-2">
                      These tickers will be used in the comparative analysis
                      section of your deck
                    </p>
                    {selectedForHeatmap.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {selectedForHeatmap.map((ticker) => (
                          <span
                            key={ticker}
                            className="inline-flex items-center gap-1 px-2 py-1 bg-blue-500/20 text-blue-200 rounded text-xs font-medium"
                          >
                            {ticker}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 italic mb-3">
                        No tickers selected yet. Select tickers above to include
                        them in the heatmap.
                      </p>
                    )}

                    {/* Heatmap Configuration Options */}
                    {showHeatmapConfig && selectedForHeatmap.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-blue-500/20">
                        <div className="space-y-3">
                          {/* Performance Toggle */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={heatmapShowPerf}
                                  onChange={(e) =>
                                    setHeatmapShowPerf(e.target.checked)
                                  }
                                  className="sr-only peer"
                                />
                                <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                              </label>
                              <span className="text-xs text-slate-300">
                                Performance Metrics
                              </span>
                              <button
                                className="text-slate-500 hover:text-slate-400"
                                title="Include performance metrics like returns and volatility"
                              >
                                <HelpCircle className="w-3.5 h-3.5" />
                              </button>
                            </div>
                            {heatmapShowPerf && (
                              <select
                                value={heatmapPerfPeriod}
                                onChange={(e) =>
                                  setHeatmapPerfPeriod(
                                    e.target.value as PerfPeriod,
                                  )
                                }
                                className="text-xs bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                              >
                                <option value="1mo">1 Month</option>
                                <option value="3mo">3 Months</option>
                                <option value="6mo">6 Months</option>
                                <option value="1y">1 Year</option>
                                <option value="3y">3 Years</option>
                                <option value="5y">5 Years</option>
                              </select>
                            )}
                          </div>

                          {/* DCF Toggle */}
                          <div className="flex items-center gap-2">
                            <label className="relative inline-flex items-center cursor-pointer">
                              <input
                                type="checkbox"
                                checked={heatmapShowDcf}
                                onChange={(e) =>
                                  setHeatmapShowDcf(e.target.checked)
                                }
                                className="sr-only peer"
                              />
                              <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                            </label>
                            <span className="text-xs text-slate-300">
                              DCF Valuation
                            </span>
                            <button
                              className="text-slate-500 hover:text-slate-400"
                              title="Include DCF-based target prices and valuations"
                            >
                              <HelpCircle className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          {/* Help Text */}
                          <div className="flex items-start gap-2 pt-2 border-t border-blue-500/20">
                            <HelpCircle className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                            <p className="text-xs text-blue-300/60">
                              Configure which metrics to include in the relative
                              valuation comparison table. Performance shows
                              historical returns, while DCF shows intrinsic
                              value estimates.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Controls Row */}
          <Controls
            showPerf={showPerf}
            onShowPerfChange={setShowPerf}
            showDcf={showDcf}
            onShowDcfChange={setShowDcf}
            perfPeriod={perfPeriod}
            onPerfPeriodChange={setPerfPeriod}
            onCompare={handleCompare}
            onExport={handleExport}
            isLoading={isLoading || isFetching}
            canCompare={tickers.length > 0}
            canExport={!!data && data.rows.length > 0}
          />
        </div>
      </Card>

      {/* Column Picker Toggle */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setShowColumnPicker(!showColumnPicker)}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
        >
          <ChevronRight
            className={`w-4 h-4 transition-transform ${showColumnPicker ? "rotate-90" : ""}`}
          />
          {showColumnPicker ? "Hide" : "Show"} Column Settings
        </button>

        {/* Signal Controls */}
        <SignalControls
          settings={signalSettings}
          onToggle={toggleSignals}
          onModeChange={setSignalMode}
          onConfigure={() => setShowSignalConfig(true)}
        />
      </div>

      {/* Column Picker */}
      {showColumnPicker && (
        <Card>
          <ColumnPicker
            selectedFields={selectedFields}
            onFieldsChange={setSelectedFields}
            selectedPerfMetrics={selectedPerfMetrics}
            onPerfMetricsChange={setSelectedPerfMetrics}
            showPerf={showPerf}
          />
        </Card>
      )}

      {/* Error State */}
      {error && (
        <Alert variant="error" title="Error loading data">
          {error instanceof Error ? error.message : "An error occurred"}
        </Alert>
      )}

      {/* Loading State */}
      {(isLoading || isFetching) && !data && (
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center gap-3 text-slate-400">
            <svg
              className="w-6 h-6 animate-spin"
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
            <span>Fetching data...</span>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!data && !isLoading && !error && (
        <Card className="text-center py-16">
          <div className="w-16 h-16 mx-auto mb-4 bg-slate-800 rounded-full flex items-center justify-center">
            <TrendingUp className="w-8 h-8 text-slate-500" />
          </div>
          <h3 className="text-lg font-medium text-white mb-1">
            No data to display
          </h3>
          <p className="text-slate-400 mb-6">
            Enter some tickers above and click Compare to see the relative
            table.
          </p>
          <Button variant="outline" onClick={() => handleGenerateDeck()}>
            Or generate a pitch deck
          </Button>
        </Card>
      )}

      {/* Table */}
      {data && (
        <div className="rounded-lg overflow-hidden bg-slate-900 border border-slate-800">
          <RelativeTable
            data={data}
            visibleFields={selectedFields}
            visiblePerfMetrics={selectedPerfMetrics}
            showPerf={showPerf}
            showDcf={showDcf}
            signalSettings={signalSettings}
          />
          {/* Generate Deck for selected ticker CTA */}
          {data.rows.length > 0 && (
            <div className="border-t border-slate-800 p-4 bg-slate-900/50">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">
                  Select a ticker to generate an investment pitch deck
                </p>
                <div className="flex flex-wrap gap-2">
                  {data.rows.slice(0, 5).map((row) => (
                    <Button
                      key={row.symbol}
                      variant="outline"
                      size="sm"
                      onClick={() => handleGenerateDeck(row.symbol)}
                    >
                      <FileText className="w-4 h-4 mr-1" />
                      {row.symbol}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Signal Configuration Drawer */}
      <SignalConfigDrawer
        isOpen={showSignalConfig}
        onClose={() => setShowSignalConfig(false)}
        settings={signalSettings}
        onUpdateRule={updateSignalRule}
        onReset={resetSignalSettings}
      />
    </div>
  );
}
