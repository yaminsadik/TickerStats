import { useState, useCallback, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  FileText,
  ChevronRight,
  TrendingUp,
  Settings,
  HelpCircle,
  Save,
  Star,
  RefreshCw,
  Loader2,
  Lock,
} from "lucide-react";
import { TickerInput } from "../components/TickerInput";
import { ColumnPicker } from "../components/ColumnPicker";
import { Controls } from "../components/Controls";
import { RelativeTable } from "../components/RelativeTable";
import SignalControls from "../components/SignalControls";
import SignalConfigDrawer from "../components/SignalConfigDrawer";
import { useRelativeTable } from "../hooks/useRelativeTable";
import { useSignalSettings } from "../hooks/useSignalSettings";
import { useUserProfile } from "../hooks/useUserProfile";
import { type ExportFormat } from "../api/client";
import { Button, Card, Alert, Input, TableSkeleton } from "../components/ui";
import { SNAPSHOT_FIELDS, PERF_METRICS, type PerfPeriod } from "../types/api";
import type { FetchRelativeParams } from "../api/client";
import {
  useSaveSearch,
  useAddToWatchlist,
  useExportTable,
} from "../queries/useBrowseMutations";

export default function BrowsePage() {
  const navigate = useNavigate();
  const location = useLocation();

  // User profile for free-tier gates
  const {
    canExport: userCanExport,
    atSaveLimit,
    savedSearchesCount,
    savedSearchesLimit,
    compareCount,
    compareLimit,
    tier,
  } = useUserProfile();

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

  // --- Mutation hooks ---
  const saveSearchMutation = useSaveSearch();
  const addWatchlistMutation = useAddToWatchlist();
  const exportTableMutation = useExportTable();

  // --- Save Search state ---
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveDesc, setSaveDesc] = useState("");

  // --- Watchlist feedback ---
  const [watchlistMsg, setWatchlistMsg] = useState<string | null>(null);

  // Load saved analysis from navigation state (coming from SavedSearchesPage)
  useEffect(() => {
    const state = location.state as {
      savedAnalysis?: {
        symbols: string[];
        snapshot_fields?: string[] | null;
        perf_periods?: string[] | null;
        include_dcf?: boolean;
        snapshot_data?: import("../types/api").RelativeTableResponse | null;
      };
    } | null;
    if (state?.savedAnalysis) {
      const sa = state.savedAnalysis;
      setTickers(sa.symbols);
      if (sa.snapshot_fields) setSelectedFields(sa.snapshot_fields);
      if (sa.perf_periods && sa.perf_periods.length > 0) {
        setShowPerf(true);
      }
      if (sa.include_dcf) setShowDcf(true);
      // Clear the location state so refresh doesn't re-apply
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  // --- Save Search handler ---
  const handleSaveSearch = useCallback(() => {
    if (!saveName.trim() || tickers.length === 0) return;
    saveSearchMutation.mutate(
      {
        name: saveName.trim(),
        description: saveDesc.trim() || undefined,
        symbols: tickers,
        snapshot_fields: selectedFields,
        perf_periods: showPerf ? selectedPerfMetrics : undefined,
        include_dcf: showDcf,
        snapshot_data: data ?? undefined,
      },
      {
        onSuccess: () => {
          setShowSaveModal(false);
          setSaveName("");
          setSaveDesc("");
          // Auto-dismiss success after 3s
          setTimeout(() => saveSearchMutation.reset(), 3000);
        },
      },
    );
  }, [
    saveSearchMutation,
    saveName,
    saveDesc,
    tickers,
    selectedFields,
    showPerf,
    selectedPerfMetrics,
    showDcf,
    data,
  ]);

  // --- Add to Watchlist handler ---
  const handleAddToWatchlist = useCallback(
    (ticker: string) => {
      setWatchlistMsg(null);
      addWatchlistMutation.mutate(ticker, {
        onSuccess: () => {
          setWatchlistMsg(`${ticker} added to watchlist`);
          setTimeout(() => setWatchlistMsg(null), 3000);
        },
        onError: (err: Error) => {
          if (err.message?.includes("already")) {
            setWatchlistMsg(`${ticker} is already in your watchlist`);
          } else {
            setWatchlistMsg(`Failed to add ${ticker}: ${err.message}`);
          }
          setTimeout(() => setWatchlistMsg(null), 3000);
        },
      });
    },
    [addWatchlistMutation],
  );

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
  const handleExport = useCallback(
    (format: ExportFormat = "csv") => {
      if (!queryParams || !data) return;
      exportTableMutation.mutate({ params: queryParams, format });
    },
    [queryParams, data, exportTableMutation],
  );

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
          {tickers.length > 0 && (
            <Button
              variant="outline"
              size="lg"
              className="flex items-center gap-2"
              onClick={() => {
                saveSearchMutation.reset();
                setShowSaveModal(true);
              }}
              aria-label="Save current search"
            >
              {atSaveLimit ? (
                <Lock className="w-5 h-5" aria-hidden="true" />
              ) : (
                <Save className="w-5 h-5" aria-hidden="true" />
              )}
              Save Search
              {tier === "free" && (
                <span className="text-[10px] font-bold uppercase tracking-wide bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">
                  {savedSearchesCount}/{savedSearchesLimit}
                </span>
              )}
            </Button>
          )}
          <Button
            onClick={() => handleGenerateDeck()}
            size="lg"
            className="flex items-center gap-2"
            aria-label="Generate pitch deck"
          >
            <FileText className="w-5 h-5" aria-hidden="true" />
            Generate Deck
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      {/* Success / info toasts */}
      {saveSearchMutation.isSuccess && (
        <Alert variant="success" title="Saved">
          Search saved successfully!{" "}
          <button
            className="underline text-green-300"
            onClick={() => navigate("/saved-searches")}
          >
            View saved searches
          </button>
        </Alert>
      )}
      {watchlistMsg && (
        <Alert
          variant={watchlistMsg.includes("Failed") ? "error" : "info"}
          title="Watchlist"
        >
          {watchlistMsg}
        </Alert>
      )}
      {exportTableMutation.isError && (
        <Alert variant="error" title="Export">
          {exportTableMutation.error instanceof Error
            ? exportTableMutation.error.message
            : "Export failed"}
        </Alert>
      )}

      {/* Save Search Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-md mx-4">
            <h2 className="text-lg font-bold text-white mb-4">Save Search</h2>
            {atSaveLimit ? (
              <div className="space-y-4">
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Lock className="w-5 h-5 text-amber-400" />
                    <h3 className="text-sm font-semibold text-amber-300">
                      Free Plan Limit Reached
                    </h3>
                  </div>
                  <p className="text-sm text-amber-200/80">
                    You've used all {savedSearchesLimit} saved searches on the
                    free plan. Upgrade to Pro for unlimited saved searches.
                  </p>
                </div>
                <div className="flex gap-2 justify-end pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowSaveModal(false);
                      saveSearchMutation.reset();
                    }}
                  >
                    Close
                  </Button>
                  <Button size="sm" onClick={() => navigate("/profile")}>
                    Upgrade
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <Input
                  placeholder="Name (e.g. Tech Giants Comparison)"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  autoFocus
                />
                <Input
                  placeholder="Description (optional)"
                  value={saveDesc}
                  onChange={(e) => setSaveDesc(e.target.value)}
                />
                <p className="text-xs text-slate-400">
                  Saving {tickers.length} ticker
                  {tickers.length !== 1 ? "s" : ""}:{" "}
                  {tickers.slice(0, 5).join(", ")}
                  {tickers.length > 5 ? ` +${tickers.length - 5} more` : ""}
                </p>
                {tier === "free" && (
                  <p className="text-xs text-slate-500">
                    {savedSearchesCount}/{savedSearchesLimit} saved searches
                    used (free plan)
                  </p>
                )}
                {saveSearchMutation.isError && (
                  <p className="text-sm text-red-400">
                    {saveSearchMutation.error instanceof Error
                      ? saveSearchMutation.error.message
                      : "Failed to save"}
                  </p>
                )}
                <div className="flex gap-2 justify-end pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowSaveModal(false);
                      saveSearchMutation.reset();
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSaveSearch}
                    disabled={saveSearchMutation.isPending || !saveName.trim()}
                  >
                    {saveSearchMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Save className="w-4 h-4 mr-2" />
                    )}
                    Save
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

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
            exportLocked={!userCanExport}
          />
          {compareLimit !== null && (
            <div className="mt-2 text-xs text-slate-500">
              Compare usage: {compareCount}/{compareLimit} this month (free
              plan)
            </div>
          )}
        </div>
      </Card>

      {/* Column Picker Toggle */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setShowColumnPicker(!showColumnPicker)}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-400 hover:text-white transition-colors"
          aria-expanded={showColumnPicker}
          aria-controls="column-picker"
        >
          <ChevronRight
            className={`w-4 h-4 transition-transform ${showColumnPicker ? "rotate-90" : ""}`}
            aria-hidden="true"
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
        <Card id="column-picker" role="region" aria-label="Column settings">
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
        <Alert variant="error" title="Failed to Load Data">
          <div className="space-y-3">
            <p className="text-sm">
              {error instanceof Error
                ? error.message
                : "An unexpected error occurred while fetching data."}{" "}
              This might be due to invalid ticker symbols or network issues.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCompare}
                className="text-white"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Retry
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setTickers([]);
                  setQueryParams(null);
                }}
              >
                Clear All Tickers
              </Button>
            </div>
            <p className="text-xs text-slate-400">
              Need help?{" "}
              <a href="/contact" className="text-blue-400 hover:underline">
                Contact support
              </a>
            </p>
          </div>
        </Alert>
      )}

      {/* Loading State */}
      {(isLoading || isFetching) && !data && (
        <Card>
          <TableSkeleton rows={5} cols={selectedFields.length + 1} />
        </Card>
      )}

      {/* Empty State */}
      {!data && !isLoading && !error && (
        <Card className="text-center py-16 px-6">
          <div className="w-24 h-24 mx-auto mb-6 bg-slate-800 rounded-full flex items-center justify-center">
            <TrendingUp className="w-12 h-12 text-slate-500" />
          </div>
          <h3 className="text-2xl font-bold text-white mb-2">
            Start Your Analysis
          </h3>
          <p className="text-slate-400 mb-8 max-w-md mx-auto">
            Compare stocks side-by-side with real-time market data and
            fundamental metrics. Enter tickers above to get started.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
            <Button
              variant="primary"
              size="lg"
              onClick={() => {
                // Add example tickers
                const exampleTickers = [
                  "AAPL",
                  "MSFT",
                  "GOOGL",
                  "META",
                  "NVDA",
                ];
                setTickers(exampleTickers);
                // Trigger comparison
                setTimeout(() => {
                  const params: FetchRelativeParams = {
                    symbols: exampleTickers,
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
                }, 100);
              }}
            >
              <TrendingUp className="w-5 h-5 mr-2" />
              Try Example: Tech Giants
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => handleGenerateDeck()}
            >
              <FileText className="w-5 h-5 mr-2" />
              Generate Pitch Deck
            </Button>
          </div>
          <div className="text-sm text-slate-500">
            <p className="mb-2">
              💡 <strong>Popular searches:</strong>
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              <button
                onClick={() =>
                  setTickers(["AAPL", "MSFT", "GOOGL", "META", "NVDA"])
                }
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-full text-xs text-slate-300 transition-colors"
              >
                FAANG
              </button>
              <button
                onClick={() => setTickers(["JPM", "BAC", "WFC", "C", "GS"])}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-full text-xs text-slate-300 transition-colors"
              >
                Big Banks
              </button>
              <button
                onClick={() => setTickers(["JNJ", "PFE", "UNH", "ABBV", "TMO"])}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-full text-xs text-slate-300 transition-colors"
              >
                Healthcare
              </button>
              <button
                onClick={() => setTickers(["XOM", "CVX", "COP", "SLB", "EOG"])}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-full text-xs text-slate-300 transition-colors"
              >
                Energy
              </button>
            </div>
          </div>
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
            <div className="border-t border-slate-800 p-4 bg-slate-900/50 space-y-3">
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
              <div className="flex items-center justify-between border-t border-slate-800 pt-3">
                <p className="text-sm text-slate-400">
                  Add a ticker to your watchlist
                </p>
                <div className="flex flex-wrap gap-2">
                  {data.rows.slice(0, 8).map((row) => (
                    <Button
                      key={row.symbol}
                      variant="outline"
                      size="sm"
                      onClick={() => handleAddToWatchlist(row.symbol)}
                      disabled={
                        addWatchlistMutation.isPending &&
                        addWatchlistMutation.variables === row.symbol
                      }
                    >
                      {addWatchlistMutation.isPending &&
                      addWatchlistMutation.variables === row.symbol ? (
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                      ) : (
                        <Star className="w-4 h-4 mr-1" />
                      )}
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
