/**
 * View a deck stored in the database (by numeric ID).
 * Loads from /api/user/decks/:id and renders the same content
 * that DeckDraftPage shows for localStorage drafts.
 */
import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  Trash2,
  ChevronDown,
  ChevronRight,
  FileCode,
  FileText,
  Loader2,
  Presentation,
} from "lucide-react";
import { Button, Card, Badge, Alert, JsonViewerModal } from "../components/ui";
import { RelativeTable } from "../components/RelativeTable";
import { useSignalSettings } from "../hooks/useSignalSettings";
import { exportDeckToPDF, exportDeckToPPTX } from "../utils/deckExport";
import { SNAPSHOT_FIELDS } from "../types/api";
import type { RelativeTableResponse, RowData } from "../types/api";
import { useUserProfile } from "../hooks/useUserProfile";
import { useDeckDetail, useDeleteDeck } from "../queries/useDeckQueries";
import type { GeneratedSection, Slide, BulletPoint } from "../api/deckApi";

function convertCompsToRelativeTable(
  compsTable: any,
): RelativeTableResponse | null {
  if (!compsTable || !compsTable.target || !compsTable.comparables) return null;
  const rows: RowData[] = [];
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
    units: {},
    requested: {
      symbols: rows.map((r) => r.symbol),
      fields: compsTable.metrics_included?.snapshot || [...SNAPSHOT_FIELDS],
      perf: null,
      dcf: false,
    },
    rows,
  };
}

export default function DeckViewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { canExport } = useUserProfile();

  const {
    data: deck,
    isLoading: loading,
    error: queryError,
  } = useDeckDetail(id ? Number(id) : undefined);
  const error = queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null;

  const deleteMutation = useDeleteDeck();

  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const [showJsonViewer, setShowJsonViewer] = useState(false);
  const { settings: signalSettings } = useSignalSettings();

  // Expand all sections when deck loads
  useEffect(() => {
    if (!deck) return;
    const sections =
      (deck.content as any)?.results ||
      (deck.content as any)?.sections ||
      [];
    setExpandedSections(new Set(sections.map((s: any) => s.section_id)));
  }, [deck]);

  const toggleSection = (sectionId: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  };

  const handleDelete = () => {
    if (!id || !confirm("Delete this deck permanently?")) return;
    deleteMutation.mutate(Number(id), {
      onSuccess: () => navigate("/decks"),
    });
  };

  const content = deck?.content as any;
  const sections: GeneratedSection[] =
    content?.results || content?.sections || [];
  const compsTable = content?.computed_inputs?.comps_table;
  const compsData = useMemo(
    () => convertCompsToRelativeTable(compsTable),
    [compsTable],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (error || !deck) {
    return (
      <div className="space-y-4">
        <Alert variant="error" title="Error">
          {error || "Deck not found"}
        </Alert>
        <Button variant="outline" onClick={() => navigate("/decks")}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Decks
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            to="/decks"
            className="text-sm text-slate-400 hover:text-white flex items-center gap-1 mb-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Deck History
          </Link>
          <h1 className="text-2xl font-bold text-white">{deck.title}</h1>
          <div className="flex items-center gap-3 mt-1">
            <Badge variant="info">{deck.ticker}</Badge>
            {deck.llm_provider && (
              <Badge variant="default">{deck.llm_provider}</Badge>
            )}
            <span className="text-xs text-slate-500">
              {new Date(deck.created_at).toLocaleString()}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowJsonViewer(true)}
            disabled={!canExport}
            title={!canExport ? "Upgrade to Pro to export decks" : undefined}
          >
            <FileCode className="w-4 h-4 mr-1" />
            JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (deck?.content) {
                exportDeckToPDF(deck.content as any, `${deck.ticker}_deck.pdf`);
              }
            }}
            disabled={!canExport}
            title={!canExport ? "Upgrade to Pro to export decks" : undefined}
          >
            <FileText className="w-4 h-4 mr-1" />
            PDF
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (deck?.content) {
                exportDeckToPPTX(
                  deck.content as any,
                  `${deck.ticker}_deck.pptx`,
                );
              }
            }}
            disabled={!canExport}
            title={!canExport ? "Upgrade to Pro to export decks" : undefined}
          >
            <Presentation className="w-4 h-4 mr-1" />
            PPTX
          </Button>
          <Button variant="outline" size="sm" onClick={handleDelete}>
            <Trash2 className="w-4 h-4 text-red-400" />
          </Button>
        </div>
      </div>

      {/* Comps table */}
      {compsData && (
        <Card>
          <h2 className="text-lg font-semibold text-white mb-3">
            Comparable Companies
          </h2>
          <RelativeTable
            data={compsData}
            visibleFields={[...SNAPSHOT_FIELDS]}
            visiblePerfMetrics={[]}
            showPerf={false}
            showDcf={false}
            signalSettings={signalSettings}
          />
        </Card>
      )}

      {/* Sections */}
      {sections.map((section) => (
        <Card key={section.section_id}>
          <button
            className="w-full flex items-center justify-between text-left"
            onClick={() => toggleSection(section.section_id)}
          >
            <h2 className="text-lg font-semibold text-white">
              {section.section_name}
            </h2>
            {expandedSections.has(section.section_id) ? (
              <ChevronDown className="w-5 h-5 text-slate-400" />
            ) : (
              <ChevronRight className="w-5 h-5 text-slate-400" />
            )}
          </button>
          {expandedSections.has(section.section_id) && (
            <div className="mt-4 space-y-6">
              {section.slides?.map((slide: Slide, si: number) => (
                <div key={si}>
                  <h3 className="text-base font-medium text-blue-300 mb-2">
                    {slide.title}
                  </h3>
                  <ul className="space-y-1.5 pl-4">
                    {slide.bullets?.map((b: BulletPoint, bi: number) => (
                      <li key={bi} className="text-sm text-slate-300 list-disc">
                        {b.text}
                      </li>
                    ))}
                  </ul>
                  {slide.speaker_notes && (
                    <p className="mt-2 text-xs text-slate-500 italic">
                      {slide.speaker_notes}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      ))}

      {showJsonViewer && (
        <JsonViewerModal
          isOpen={showJsonViewer}
          onClose={() => setShowJsonViewer(false)}
          exportData={deck.content as any}
          deckName={deck.title}
          ticker={deck.ticker}
          _onDownload={() => {
            const blob = new Blob([JSON.stringify(deck.content, null, 2)], {
              type: "application/json",
            });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${deck.ticker}_deck.json`;
            a.click();
            URL.revokeObjectURL(url);
          }}
        />
      )}
    </div>
  );
}
