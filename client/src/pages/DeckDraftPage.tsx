import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import Breadcrumbs, { BreadcrumbItem } from "../components/Breadcrumbs";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  ExternalLink,
  FileCode,
  Settings,
  FileText,
  Presentation,
} from "lucide-react";
import {
  Button,
  Card,
  Badge,
  Alert,
  Spinner,
  JsonViewerModal,
  SectionSkeleton,
  type DeckExportData,
} from "../components/ui";
import { RelativeTable } from "../components/RelativeTable";
import { ColumnPicker } from "../components/ColumnPicker";
import SignalControls from "../components/SignalControls";
import SignalConfigDrawer from "../components/SignalConfigDrawer";
import { exportDeckToPDF, exportDeckToPPTX } from "../utils/deckExport";
import { useRelativeTable } from "../hooks/useRelativeTable";
import { useSignalSettings } from "../hooks/useSignalSettings";
import { useUserProfile } from "../hooks/useUserProfile";
import type { FetchRelativeParams } from "../api/client";
import { SNAPSHOT_FIELDS, PERF_METRICS, type PerfPeriod } from "../types/api";
import type { RelativeTableResponse, RowData } from "../types/api";
import {
  getDraft,
  deleteDraft,
  mergeSectionIntoDraft,
  type DeckDraft,
} from "../stores/deckDraft";
import {
  regenerateSection,
  type GeneratedSection,
  type Slide,
  type BulletPoint,
} from "../api/deckApi";

/**
 * Convert comps_table format to RelativeTableResponse format
 */
function convertCompsToRelativeTable(
  compsTable: any,
): RelativeTableResponse | null {
  if (!compsTable || !compsTable.target || !compsTable.comparables) {
    return null;
  }

  const rows: RowData[] = [];

  // Add target row
  if (compsTable.target) {
    rows.push({
      symbol: compsTable.target.ticker,
      snapshot: compsTable.target.snapshot || {},
      performance: compsTable.target.performance || null,
      dcf: null,
      missingFields: compsTable.target.missing_fields || [],
      error: compsTable.target.has_error ? "Data error" : null,
    });
  }

  // Add comparable rows
  if (compsTable.comparables && Array.isArray(compsTable.comparables)) {
    compsTable.comparables.forEach((comp: any) => {
      rows.push({
        symbol: comp.ticker,
        snapshot: comp.snapshot || {},
        performance: comp.performance || null,
        dcf: null,
        missingFields: comp.missing_fields || [],
        error: comp.has_error ? "Data error" : null,
      });
    });
  }

  return {
    asOf: new Date().toISOString(),
    units: {
      sharePrice: "USD",
      marketCap: "USD",
      enterpriseValue: "USD",
      forwardPE: "ratio",
      priceSales: "ratio",
      priceBook: "ratio",
      evEbitda: "ratio",
      evRevenue: "ratio",
      profitMargin: "percent",
      roa: "percent",
      roe: "percent",
      debtEquity: "ratio",
      beta: "number",
    },
    requested: {
      symbols: rows.map((r) => r.symbol),
      fields: compsTable.metrics_included?.snapshot || [...SNAPSHOT_FIELDS],
      perf: null,
      dcf: false,
    },
    rows,
  };
}

export default function DeckDraftPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { canExport } = useUserProfile();

  const [draft, setDraft] = useState<DeckDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(
    null,
  );
  const [showJsonViewer, setShowJsonViewer] = useState(false);
  const { settings: signalSettings } = useSignalSettings();

  // Load draft on mount
  useEffect(() => {
    if (id) {
      const loadedDraft = getDraft(id);
      setDraft(loadedDraft);
      // Expand all sections by default
      if (loadedDraft?.generatedContent?.sections) {
        setExpandedSections(
          new Set(
            loadedDraft.generatedContent.sections.map((s) => s.section_id),
          ),
        );
      }
    }
    setLoading(false);
  }, [id]);

  // Regenerate section mutation
  const regenerateMutation = useMutation({
    mutationFn: (sectionId: string) => {
      if (!draft) throw new Error("No draft loaded");
      return regenerateSection({
        ticker: draft.basics.ticker,
        company_name:
          draft.basics.companyName ||
          draft.generatedContent?.metadata?.company_name ||
          draft.basics.ticker,
        sector: draft.basics.sector || "Technology",
        fund_constraints: {
          time_horizon: "12-24 months",
          risk_profile: "moderate",
          style: "student investment fund pitch deck",
        },
        section_id: sectionId,
        provider: draft.config.provider,
        reasoning_level: draft.config.quality,
        include_comps: true,
      });
    },
    onMutate: (sectionId) => {
      setRegeneratingSection(sectionId);
    },
    onSuccess: (newSection) => {
      if (id) {
        const updatedDraft = mergeSectionIntoDraft(id, newSection);
        if (updatedDraft) {
          setDraft(updatedDraft);
        }
      }
      setRegeneratingSection(null);
    },
    onError: () => {
      setRegeneratingSection(null);
    },
  });

  // Toggle section expansion
  const toggleSection = (sectionId: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  };

  // Delete draft
  const handleDelete = () => {
    if (
      id &&
      confirm(
        "Are you sure you want to delete this draft? This cannot be undone.",
      )
    ) {
      deleteDraft(id);
      navigate("/deck/new");
    }
  };

  // Build export data in the expected format
  const exportData: DeckExportData | null = useMemo(() => {
    if (!draft?.generatedContent) return null;

    const gc = draft.generatedContent;

    // If data already has results array, it's in export format
    if ((gc as any).results) {
      return gc as unknown as DeckExportData;
    }

    // Convert internal format to export format
    return {
      ticker: gc.metadata?.ticker || draft.basics.ticker,
      generated_at: gc.metadata?.generated_at || new Date().toISOString(),
      provider_used: {
        provider: gc.metadata?.provider || draft.config.provider,
        model: gc.metadata?.model || "unknown",
        reasoning_level: draft.config.quality,
      },
      metadata: {
        ticker: gc.metadata?.ticker || draft.basics.ticker,
        company_name: gc.metadata?.company_name || draft.basics.ticker,
        generated_at: gc.metadata?.generated_at || new Date().toISOString(),
        provider: gc.metadata?.provider || draft.config.provider,
        model: gc.metadata?.model || "unknown",
      },
      results: (gc.sections || []).map((section) => ({
        section_id: section.section_id,
        needs_verification:
          section.slides?.some((s) =>
            s.bullets?.some((b) => b.source_needed),
          ) || false,
        slides: section.slides || [],
        citations: section.citations,
      })),
      errors: gc.warnings,
    };
  }, [draft]);

  // Export as JSON (download)
  const handleExportJSON = () => {
    if (!exportData) return;

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${draft?.basics.ticker || "deck"}_pitch_deck.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Export as PDF
  const handleExportPDF = async () => {
    if (!exportData) return;
    const ticker = draft?.basics.ticker || "deck";
    await exportDeckToPDF(exportData, `${ticker}_pitch_deck.pdf`);
  };

  // Export as PPTX
  const handleExportPPTX = async () => {
    if (!exportData) return;
    const ticker = draft?.basics.ticker || "deck";
    await exportDeckToPPTX(exportData, `${ticker}_pitch_deck.pptx`);
  };

  // Computed counts from export data
  const sectionsCount = exportData?.results?.length ?? 0;
  const slidesCount =
    exportData?.results?.reduce((sum, s) => sum + (s.slides?.length ?? 0), 0) ??
    0;

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto pb-8">
        <SectionSkeleton count={5} />
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="max-w-3xl mx-auto">
        <Alert variant="error" title="Draft Not Found">
          <p>The requested draft could not be found.</p>
          <Link
            to="/deck/new"
            className="text-blue-400 hover:text-blue-300 mt-2 inline-block"
          >
            Create a new deck →
          </Link>
        </Alert>
      </div>
    );
  }

  if (!draft.generatedContent) {
    return (
      <div className="max-w-3xl mx-auto">
        <Alert variant="warning" title="Incomplete Draft">
          <p>This draft has not been generated yet.</p>
          <Link
            to="/deck/new"
            state={{ ticker: draft.basics.ticker }}
            className="text-blue-400 hover:text-blue-300 mt-2 inline-block"
          >
            Continue editing →
          </Link>
        </Alert>
      </div>
    );
  }

  // Handle both 'sections' (legacy) and 'results' (current) field names
  const { metadata, sections, warnings, results, computed_inputs } =
    draft.generatedContent;
  const actualSections = sections ?? results ?? [];

  const safeMetadata = metadata ?? {
    ticker: draft.generatedContent?.ticker || draft.basics.ticker,
    company_name:
      draft.generatedContent?.company_name ||
      draft.generatedContent?.metadata?.company_name ||
      draft.basics.ticker,
    generated_at:
      draft.generatedContent?.generated_at || new Date().toISOString(),
    provider:
      draft.generatedContent?.provider_used?.provider || draft.config.provider,
    model: draft.generatedContent?.provider_used?.model || "unknown",
  };

  const safeSections = actualSections;

  return (
    <div className="max-w-6xl mx-auto pb-8">
      {/* Breadcrumbs */}
      <Breadcrumbs>
        <BreadcrumbItem href="/browse">Browse</BreadcrumbItem>
        <BreadcrumbItem href="/deck/new">Generate Deck</BreadcrumbItem>
        <BreadcrumbItem current>
          {safeMetadata.company_name} ({safeMetadata.ticker})
        </BreadcrumbItem>
      </Breadcrumbs>

      {/* Success Banner */}
      <div className="bg-gradient-to-r from-emerald-600/20 to-blue-600/20 border border-emerald-500/30 rounded-lg p-6 mb-6">
        <div className="flex items-start gap-4">
          <div className="bg-emerald-500/20 p-3 rounded-lg">
            <FileCode className="w-6 h-6 text-emerald-400" />
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white mb-2">
              Deck Generated Successfully!
            </h1>
            <p className="text-slate-300">
              Your pitch deck for <strong>{safeMetadata.company_name}</strong> (
              {safeMetadata.ticker}) is ready. Review the sections below and
              regenerate any section if needed.
            </p>
            <div className="flex items-center gap-4 mt-3 text-sm text-slate-400">
              <span>📊 {sectionsCount} sections</span>
              <span>•</span>
              <span>📄 {slidesCount} slides</span>
              <span>•</span>
              <span>🤖 {safeMetadata.provider}</span>
              <span>•</span>
              <span>
                📅 {new Date(safeMetadata.generated_at).toLocaleDateString()}
              </span>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowJsonViewer(true)}
            disabled={!canExport}
            title={!canExport ? "Upgrade to Pro to export decks" : undefined}
          >
            <FileCode className="w-4 h-4 mr-2" />
            View Deck
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPDF}
            disabled={!canExport}
            title={!canExport ? "Upgrade to Pro to export decks" : undefined}
          >
            <FileText className="w-4 h-4 mr-2" />
            PDF
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPPTX}
            disabled={!canExport}
            title={!canExport ? "Upgrade to Pro to export decks" : undefined}
          >
            <Presentation className="w-4 h-4 mr-2" />
            PPTX
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="danger" size="sm" onClick={handleDelete}>
            <Trash2 className="w-4 h-4 mr-2" />
            Delete Draft
          </Button>
        </div>
      </div>

      {/* Warnings */}
      {warnings && warnings.length > 0 && (
        <Alert variant="warning" title="Warnings" className="mb-6">
          <ul className="list-disc list-inside space-y-1">
            {warnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </Alert>
      )}

      {/* Sections */}
      <div className="space-y-4">
        {safeSections.map((section) => (
          <SectionCard
            key={section.section_id}
            section={section}
            expanded={expandedSections.has(section.section_id)}
            onToggle={() => toggleSection(section.section_id)}
            regenerating={regeneratingSection === section.section_id}
            onRegenerate={() => regenerateMutation.mutate(section.section_id)}
            computedInputs={
              computed_inputs || draft?.generatedContent?.computed_inputs
            }
            signalSettings={signalSettings}
          />
        ))}
      </div>

      {/* JSON Viewer Modal */}
      {showJsonViewer && exportData && (
        <JsonViewerModal
          isOpen={showJsonViewer}
          onClose={() => setShowJsonViewer(false)}
          exportData={exportData}
          deckName={safeMetadata.company_name}
          ticker={safeMetadata.ticker}
          onDownload={handleExportJSON}
        />
      )}
    </div>
  );
}

// Section card component
function SectionCard({
  section,
  expanded,
  onToggle,
  regenerating,
  onRegenerate,
  computedInputs,
  signalSettings,
}: {
  section: GeneratedSection;
  expanded: boolean;
  onToggle: () => void;
  regenerating: boolean;
  onRegenerate: () => void;
  computedInputs?: any;
  signalSettings?: any;
}) {
  // Table customization state for relative heatmap
  const [showPerf, setShowPerf] = useState(false);
  const [showDcf, setShowDcf] = useState(false);
  const [perfPeriod, setPerfPeriod] = useState<PerfPeriod>("3mo");
  const [selectedFields, setSelectedFields] = useState<string[]>([
    ...SNAPSHOT_FIELDS,
  ]);
  const [selectedPerfMetrics, setSelectedPerfMetrics] = useState<string[]>([
    ...PERF_METRICS,
  ]);
  const [showColumnPicker, setShowColumnPicker] = useState(false);

  // Signal settings with toggles
  const {
    settings: localSignalSettings,
    toggleEnabled: toggleSignals,
    setGlobalMode: setSignalMode,
    updateRule: updateSignalRule,
    resetToDefaults: resetSignalSettings,
  } = useSignalSettings();
  const [showSignalConfig, setShowSignalConfig] = useState(false);

  const needsVerification = section.slides?.some((s) =>
    s.bullets?.some((b) => b.source_needed),
  );

  // Check if this is the relative_heatmap section with comps data
  const isRelativeHeatmap = section.section_id === "relative_heatmap";
  const compsTableData = computedInputs?.comps_table;

  // Get symbols from comps table
  const symbols = useMemo(() => {
    if (!compsTableData) return [];
    const tickers: string[] = [];
    if (compsTableData.target?.ticker)
      tickers.push(compsTableData.target.ticker);
    if (compsTableData.comparables) {
      compsTableData.comparables.forEach((comp: any) => {
        if (comp.ticker) tickers.push(comp.ticker);
      });
    }
    return tickers;
  }, [compsTableData]);

  // Build query params for live data fetching
  const queryParams = useMemo<FetchRelativeParams | null>(() => {
    if (!isRelativeHeatmap || symbols.length === 0) return null;

    const params: FetchRelativeParams = {
      symbols,
      fields: selectedFields,
    };

    if (showPerf && selectedPerfMetrics.length > 0) {
      params.perf = selectedPerfMetrics;
      params.perfPeriod = perfPeriod;
    }

    if (showDcf) {
      params.dcf = true;
    }

    return params;
  }, [
    isRelativeHeatmap,
    symbols,
    selectedFields,
    showPerf,
    selectedPerfMetrics,
    perfPeriod,
    showDcf,
  ]);

  // Fetch live data with performance/DCF when toggled
  const { data: liveTableData, isLoading: isLoadingTable } =
    useRelativeTable(queryParams);

  // Use live data if available, otherwise fallback to static converted data
  const relativeTableData =
    liveTableData ||
    (compsTableData ? convertCompsToRelativeTable(compsTableData) : null);

  // Debug logging
  if (isRelativeHeatmap) {
    console.log("🔍 Relative Heatmap Debug:", {
      isRelativeHeatmap,
      hasComputedInputs: !!computedInputs,
      hasCompsTable: !!compsTableData,
      hasRelativeTableData: !!relativeTableData,
      computedInputsKeys: computedInputs ? Object.keys(computedInputs) : [],
      compsTableData: compsTableData,
      relativeTableData: relativeTableData,
    });
  }

  return (
    <Card padding="none" className="overflow-hidden">
      {/* Section Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-5 hover:bg-slate-800/50 transition-colors group"
      >
        <div className="flex items-center gap-4">
          <div
            className={`p-2 rounded-lg transition-colors ${
              expanded
                ? "bg-blue-600/20"
                : "bg-slate-700/50 group-hover:bg-slate-700"
            }`}
          >
            {expanded ? (
              <ChevronDown className="w-5 h-5 text-blue-400" />
            ) : (
              <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-slate-300" />
            )}
          </div>
          <div className="text-left">
            <h3 className="text-lg font-semibold text-white group-hover:text-blue-400 transition-colors">
              {section.section_name}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm text-slate-400">
                {section.slides.length}{" "}
                {section.slides.length === 1 ? "slide" : "slides"}
              </span>
              {needsVerification && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="flex items-center gap-1 text-xs text-yellow-500">
                    <AlertTriangle className="w-3 h-3" />
                    Needs verification
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            onRegenerate();
          }}
          disabled={regenerating}
          className="opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <RefreshCw
            className={`w-4 h-4 mr-2 ${regenerating ? "animate-spin" : ""}`}
          />
          {regenerating ? "Regenerating..." : "Regenerate"}
        </Button>
      </button>

      {/* Section Content */}
      {expanded && (
        <div className="border-t border-slate-800">
          {regenerating ? (
            <div className="flex flex-col items-center justify-center py-12 px-4">
              <Spinner size="lg" />
              <span className="mt-4 text-slate-400 text-sm">
                Regenerating section with fresh content...
              </span>
            </div>
          ) : (
            <div className="p-5 space-y-5 bg-slate-900/30">
              {section.slides.map((slide, slideIndex) => (
                <SlideContent
                  key={slideIndex}
                  slide={slide}
                  index={slideIndex}
                />
              ))}

              {/* Render comparison table for relative_heatmap section */}
              {isRelativeHeatmap && relativeTableData && (
                <div className="mt-6 p-4 bg-slate-950 rounded-lg border border-slate-800">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h4 className="text-sm font-semibold text-slate-300">
                        📊 Comparative Analysis
                      </h4>
                      <p className="text-xs text-slate-500 mt-1">
                        Interactive comparison table with customizable metrics
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <SignalControls
                        settings={localSignalSettings}
                        onToggle={toggleSignals}
                        onModeChange={setSignalMode}
                        onConfigure={() => setShowSignalConfig(true)}
                      />
                    </div>
                  </div>

                  {/* Table Controls */}
                  <Card className="mb-3 bg-slate-900/50">
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-4">
                        {/* Performance Toggle */}
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={showPerf}
                            onChange={(e) => setShowPerf(e.target.checked)}
                            className="w-4 h-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500"
                          />
                          <span className="text-sm text-slate-300">
                            Performance
                          </span>
                        </label>

                        {/* Performance Period */}
                        {showPerf && (
                          <select
                            value={perfPeriod}
                            onChange={(e) =>
                              setPerfPeriod(e.target.value as PerfPeriod)
                            }
                            className="text-sm bg-slate-800 border border-slate-700 rounded px-3 py-1.5 text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="1mo">1 Month</option>
                            <option value="3mo">3 Months</option>
                            <option value="6mo">6 Months</option>
                            <option value="1y">1 Year</option>
                            <option value="3y">3 Years</option>
                            <option value="5y">5 Years</option>
                          </select>
                        )}

                        {/* DCF Toggle */}
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={showDcf}
                            onChange={(e) => setShowDcf(e.target.checked)}
                            className="w-4 h-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500"
                          />
                          <span className="text-sm text-slate-300">
                            DCF Valuation
                          </span>
                        </label>

                        {/* Column Picker Toggle */}
                        <button
                          onClick={() => setShowColumnPicker(!showColumnPicker)}
                          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-300 transition-colors"
                        >
                          <Settings className="w-4 h-4" />
                          {showColumnPicker ? "Hide" : "Show"} Columns
                        </button>

                        {isLoadingTable && (
                          <span className="text-xs text-blue-400 flex items-center gap-1">
                            <Spinner size="sm" />
                            Loading...
                          </span>
                        )}
                      </div>

                      {/* Help Text for Signals */}
                      <div className="text-xs text-slate-500 bg-slate-800/50 rounded p-2">
                        💡 <strong>Signals</strong> highlight values based on
                        comparison to peers (green = better, red = worse).
                        Toggle between <strong>Absolute</strong> (direct values)
                        and <strong>Percentile</strong> (rank) modes using the
                        dropdown above.
                      </div>
                    </div>

                    {/* Column Picker */}
                    {showColumnPicker && (
                      <div className="mt-4 pt-4 border-t border-slate-800">
                        <ColumnPicker
                          selectedFields={selectedFields}
                          onFieldsChange={setSelectedFields}
                          selectedPerfMetrics={selectedPerfMetrics}
                          onPerfMetricsChange={setSelectedPerfMetrics}
                          showPerf={showPerf}
                        />
                      </div>
                    )}
                  </Card>

                  {/* Table */}
                  <div className="rounded-lg overflow-hidden bg-slate-900 border border-slate-800">
                    <RelativeTable
                      data={relativeTableData}
                      visibleFields={selectedFields}
                      visiblePerfMetrics={selectedPerfMetrics}
                      showPerf={showPerf}
                      showDcf={showDcf}
                      signalSettings={localSignalSettings}
                    />
                  </div>

                  {/* Signal Config Drawer */}
                  <SignalConfigDrawer
                    isOpen={showSignalConfig}
                    onClose={() => setShowSignalConfig(false)}
                    settings={localSignalSettings}
                    onUpdateRule={updateSignalRule}
                    onReset={resetSignalSettings}
                  />
                </div>
              )}

              {/* Citations */}
              {section.citations && section.citations.length > 0 && (
                <div className="border-t border-slate-800 pt-5 mt-5">
                  <div className="flex items-center gap-2 mb-3">
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                    <h5 className="text-sm font-semibold text-slate-300">
                      Sources & Citations
                    </h5>
                  </div>
                  <ul className="space-y-2">
                    {section.citations.map((citation, i) => (
                      <li
                        key={i}
                        className="text-sm text-slate-400 flex items-start gap-2 pl-6"
                      >
                        <span className="text-blue-500 font-mono">
                          [{i + 1}]
                        </span>
                        <span>{citation}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// Slide content component
function SlideContent({ slide, index }: { slide: Slide; index: number }) {
  const [notesExpanded, setNotesExpanded] = useState(false);

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5 hover:border-slate-600/50 transition-colors">
      <div className="flex items-start justify-between mb-4">
        <h4 className="text-base font-semibold text-white flex-1">
          {slide.title}
        </h4>
        <span className="text-xs font-mono text-slate-500 bg-slate-900/50 px-2 py-1 rounded">
          #{index + 1}
        </span>
      </div>

      <ul className="space-y-2.5 mb-4">
        {slide.bullets.map((bullet, bulletIndex) => (
          <BulletItem key={bulletIndex} bullet={bullet} />
        ))}
      </ul>

      {slide.speaker_notes && (
        <div className="mt-4 pt-4 border-t border-slate-700/50">
          <button
            onClick={() => setNotesExpanded(!notesExpanded)}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-300 transition-colors mb-2"
          >
            {notesExpanded ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
            <span className="uppercase tracking-wide font-medium">
              Speaker Notes
            </span>
          </button>
          {notesExpanded && (
            <p className="text-sm text-slate-400 leading-relaxed pl-5">
              {slide.speaker_notes}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// Bullet point component
function BulletItem({ bullet }: { bullet: BulletPoint }) {
  return (
    <li className="flex items-start gap-3 text-slate-200">
      <span className="text-blue-400 mt-1.5 text-lg leading-none">•</span>
      <div className="flex-1">
        <span className="leading-relaxed">{bullet.text}</span>
        {bullet.source_needed && (
          <span className="inline-flex items-center gap-1.5 ml-2 text-yellow-500 text-xs bg-yellow-500/10 px-2 py-0.5 rounded">
            <AlertTriangle className="w-3 h-3" />
            Needs source
          </span>
        )}
      </div>
    </li>
  );
}
