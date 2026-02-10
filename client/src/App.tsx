import { useState, useCallback } from "react";
import { TickerInput } from "./components/TickerInput";
import { ColumnPicker } from "./components/ColumnPicker";
import { Controls } from "./components/Controls";
import { RelativeTable } from "./components/RelativeTable";
import SignalControls from "./components/SignalControls";
import SignalConfigDrawer from "./components/SignalConfigDrawer";
import { useRelativeTable } from "./hooks/useRelativeTable";
import { useSignalSettings } from "./hooks/useSignalSettings";
import { getExportUrl, type ExportFormat } from "./api/client";
import { SNAPSHOT_FIELDS, PERF_METRICS, type PerfPeriod } from "./types/api";
import type { FetchRelativeParams } from "./api/client";

function App() {
  // Ticker input state
  const [tickers, setTickers] = useState<string[]>([]);

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
  }, [tickers, selectedFields, showPerf, selectedPerfMetrics, perfPeriod, showDcf]);

  // Handle Export button
  const handleExport = useCallback(
    (format: ExportFormat = "csv") => {
      if (!queryParams || !data) return;

      const ext = format === "xlsx" ? "xlsx" : format === "pdf" ? "pdf" : "csv";
      const url = getExportUrl(queryParams, format);
      const link = document.createElement("a");
      link.href = url;
      link.download = `relative_table_${new Date().toISOString().split("T")[0]}.${ext}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    [queryParams, data],
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-700 rounded-lg flex items-center justify-center">
              <svg
                className="w-6 h-6 text-white"
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
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">TickerStats</h1>
              <p className="text-sm text-gray-500">
                Investment Club Relative Table
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Input Section */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
          <div className="grid gap-6">
            {/* Ticker Input */}
            <TickerInput
              tickers={tickers}
              onTickersChange={setTickers}
              disabled={isLoading}
            />

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
        </div>

        {/* Column Picker Toggle */}
        <div className="mb-4 flex items-center justify-between">
          <button
            onClick={() => setShowColumnPicker(!showColumnPicker)}
            className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
          >
            <svg
              className={`w-4 h-4 transition-transform ${
                showColumnPicker ? "rotate-90" : ""
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
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
          <div className="mb-6">
            <ColumnPicker
              selectedFields={selectedFields}
              onFieldsChange={setSelectedFields}
              selectedPerfMetrics={selectedPerfMetrics}
              onPerfMetricsChange={setSelectedPerfMetrics}
              showPerf={showPerf}
            />
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5 text-red-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-red-700 font-medium">
                {error instanceof Error ? error.message : "An error occurred"}
              </span>
            </div>
          </div>
        )}

        {/* Loading State */}
        {(isLoading || isFetching) && !data && (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-3 text-gray-500">
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
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
              <svg
                className="w-8 h-8 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-1">
              No data to display
            </h3>
            <p className="text-gray-500">
              Enter some tickers above and click Compare to see the relative
              table.
            </p>
          </div>
        )}

        {/* Table */}
        {data && (
          <RelativeTable
            data={data}
            visibleFields={selectedFields}
            visiblePerfMetrics={selectedPerfMetrics}
            showPerf={showPerf}
            showDcf={showDcf}
            signalSettings={signalSettings}
          />
        )}

        {/* Signal Configuration Drawer */}
        <SignalConfigDrawer
          isOpen={showSignalConfig}
          onClose={() => setShowSignalConfig(false)}
          settings={signalSettings}
          onUpdateRule={updateSignalRule}
          onReset={resetSignalSettings}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-gray-500">
            Data provided by yfinance. For educational purposes only.
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
