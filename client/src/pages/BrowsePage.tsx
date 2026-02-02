import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, ChevronRight, TrendingUp } from "lucide-react";
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
import {
  createDraft,
  saveDraftContent,
  type DeckDraftBasics,
  type DeckDraftConfig,
} from "../stores/deckDraft";
import type { GenerateDeckResponse, GeneratedSection } from "../api/deckApi";

export default function BrowsePage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);

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
        navigate("/deck/new", { state: { ticker: selectedTicker } });
      } else {
        navigate("/deck/new");
      }
    },
    [navigate, tickers],
  );

  const toTitleCase = (value: string) =>
    value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

  const normalizeImportedDeck = (
    payload: any,
  ): {
    response: GenerateDeckResponse;
    basics: DeckDraftBasics;
    config: DeckDraftConfig;
  } => {
    if (payload?.metadata && payload?.sections) {
      const response = payload as GenerateDeckResponse;
      const ticker = response.metadata?.ticker || payload.ticker || "UNKNOWN";
      const basics: DeckDraftBasics = {
        ticker,
        companyName: response.metadata?.company_name || ticker,
        sector: payload.sector || "Technology",
      };
      const config: DeckDraftConfig = {
        sections: response.sections?.map((s) => s.section_id) || [],
        provider: (response.metadata?.provider || "openai") as
          | "openai"
          | "gemini",
        quality: (payload.provider_used?.reasoning_level || "medium") as
          | "low"
          | "medium"
          | "high",
      };
      return { response, basics, config };
    }

    if (!payload?.results || !Array.isArray(payload.results)) {
      throw new Error("Unsupported deck JSON format");
    }

    const ticker = payload.ticker || "UNKNOWN";
    const providerUsed = payload.provider_used || {};

    const sections: GeneratedSection[] = payload.results.map(
      (section: any) => ({
        section_id: section.section_id || "unknown",
        section_name: toTitleCase(section.section_id || "Section"),
        slides: (section.slides || []).map((slide: any) => ({
          title: slide.title || "Untitled",
          bullets: (slide.bullets || []).map((bullet: any) => ({
            text: bullet.text || "",
            source_needed: Boolean(bullet.source_needed),
          })),
          speaker_notes: slide.speaker_notes,
        })),
        citations:
          section.citations && section.citations.length > 0
            ? section.citations
            : undefined,
      }),
    );

    if (sections.length === 0) {
      throw new Error("No sections found in deck JSON");
    }

    const response: GenerateDeckResponse = {
      metadata: {
        ticker,
        company_name: payload.company_name || ticker,
        generated_at: payload.generated_at || new Date().toISOString(),
        provider: providerUsed.provider || "openai",
        model: providerUsed.model || "unknown",
      },
      sections,
      warnings:
        payload.errors && payload.errors.length > 0
          ? payload.errors
          : undefined,
    };

    const basics: DeckDraftBasics = {
      ticker,
      companyName: response.metadata.company_name || ticker,
      sector: payload.sector || "Technology",
      companyContext: payload.company_context,
      investmentThesis: payload.investment_thesis,
    };

    const config: DeckDraftConfig = {
      sections: sections.map((s) => s.section_id),
      provider: (providerUsed.provider || "openai") as "openai" | "gemini",
      quality: (providerUsed.reasoning_level || "medium") as
        | "low"
        | "medium"
        | "high",
    };

    return { response, basics, config };
  };

  const handleImportDeck = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    setImportError(null);

    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const { response, basics, config } = normalizeImportedDeck(payload);

      const draft = createDraft(basics, config);
      saveDraftContent(draft.id, response);
      navigate(`/deck/${draft.id}`);
    } catch (error) {
      setImportError(
        error instanceof Error ? error.message : "Failed to import deck JSON",
      );
    } finally {
      setIsImporting(false);
      event.target.value = "";
    }
  };

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
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json"
            className="hidden"
            onChange={handleImportDeck}
          />
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={isImporting}
          >
            {isImporting ? "Importing..." : "Import Deck JSON"}
          </Button>
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

      {importError && (
        <Alert variant="error" title="Import failed">
          {importError}
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
        <Card padding="none" className="overflow-hidden">
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
        </Card>
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
