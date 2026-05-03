import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import Breadcrumbs, { BreadcrumbItem } from "../components/Breadcrumbs";
import {
  ArrowLeft,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  ExternalLink,
  FileCode,
  FileText,
  Presentation,
} from "lucide-react";
import {
  Button,
  Card,
  Alert,
  Spinner,
  JsonViewerModal,
  SectionSkeleton,
  type DeckExportData,
} from "../components/ui";
import { exportDeckToPDF, exportDeckToPPTX } from "../utils/deckExport";
import { fetchPptxDesignSpec } from "../utils/geminiDeckExport";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import { useUserProfile } from "../hooks/useUserProfile";
import {
  getDraft,
  deleteDraft,
  mergeSectionIntoDraft,
  type DeckDraft,
} from "../stores/deckDraft";
import { resolveModelForRequest } from "../config/modelConfig";
import {
  regenerateSection,
  type GeneratedSection,
  type Slide,
  type BulletPoint,
} from "../api/deckApi";

export default function DeckDraftPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { canExport } = useUserProfile();
  const { authenticatedFetch } = useAuthenticatedFetch();

  const [draft, setDraft] = useState<DeckDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(
    null,
  );
  const [showJsonViewer, setShowJsonViewer] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<"pdf" | "pptx" | null>(
    null,
  );
  const [exportNotice, setExportNotice] = useState<{
    variant: "info" | "warning";
    title?: string;
    message: string;
  } | null>(null);

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
      const resolvedModel = resolveModelForRequest(
        draft.config.provider,
        draft.config.model,
        draft.config.quality,
      );
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
        ...(resolvedModel && { model: resolvedModel }),
        model_mode: resolvedModel ? "specific" : "auto",
        analysis_depth: draft.config.quality,
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
    const filename = `${ticker}_pitch_deck.pdf`;
    setExportingFormat("pdf");
    setExportNotice({
      variant: "info",
      message: "Creating local PDF export.",
    });
    try {
      await exportDeckToPDF(exportData, filename);
      setExportNotice(null);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "PDF export failed.";
      console.warn("PDF export failed.", error);
      setExportNotice({
        variant: "warning",
        title: "PDF export failed",
        message,
      });
    } finally {
      setExportingFormat(null);
    }
  };

  // Export as PPTX
  const handleExportPPTX = async () => {
    if (!exportData) return;
    const ticker = draft?.basics.ticker || "deck";
    const filename = `${ticker}_pitch_deck.pptx`;
    setExportingFormat("pptx");
    setExportNotice({
      variant: "info",
      message: "Creating PPTX with Gemini styling and the local renderer.",
    });
    try {
      try {
        const designSpec = await fetchPptxDesignSpec(
          authenticatedFetch,
          exportData,
          filename,
        );
        await exportDeckToPPTX(exportData, filename, { designSpec });
        setExportNotice(null);
      } catch (designError) {
        console.warn("Gemini PPTX design spec failed; using standard PPTX layout.", designError);
        await exportDeckToPPTX(exportData, filename);
        setExportNotice({
          variant: "warning",
          title: "Exported with standard layout",
          message: "Gemini styling was unavailable, so the PPTX was exported with the standard local renderer.",
        });
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "PPTX export failed.";
      console.warn("PPTX export failed.", error);
      setExportNotice({
        variant: "warning",
        title: "PPTX export failed",
        message,
      });
    } finally {
      setExportingFormat(null);
    }
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
  const { metadata, sections, warnings, results } = draft.generatedContent;
  const actualSections = sections ?? results ?? [];
  const generationErrors = Array.isArray((draft.generatedContent as any).errors)
    ? ((draft.generatedContent as any).errors as Array<{
        section_id?: string;
        message?: string;
      }>)
    : [];

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
            title={!canExport ? "Unlock export from the saved deck page" : undefined}
          >
            <FileCode className="w-4 h-4 mr-2" />
            View Deck
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPDF}
            disabled={!canExport || exportingFormat !== null}
            title={!canExport ? "Unlock export from the saved deck page" : undefined}
          >
            {exportingFormat === "pdf" ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <FileText className="w-4 h-4 mr-2" />
            )}
            {exportingFormat === "pdf" ? "Creating PDF..." : "PDF"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportPPTX}
            disabled={!canExport || exportingFormat !== null}
            title={!canExport ? "Unlock export from the saved deck page" : undefined}
          >
            {exportingFormat === "pptx" ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <Presentation className="w-4 h-4 mr-2" />
            )}
            {exportingFormat === "pptx" ? "Creating PPTX..." : "PPTX"}
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="danger" size="sm" onClick={handleDelete}>
            <Trash2 className="w-4 h-4 mr-2" />
            Delete Draft
          </Button>
        </div>
      </div>

      {exportNotice && (
        <Alert
          variant={exportNotice.variant === "warning" ? "warning" : "info"}
          title={
            exportNotice.title ||
            (exportNotice.variant === "warning" ? "Export warning" : "Creating export")
          }
          className="mb-6"
        >
          {exportNotice.message}
        </Alert>
      )}

      {generationErrors.length > 0 && (
        <Alert variant="warning" title="Deck generated with missing sections" className="mb-6">
          <p className="mb-2">
            Some sections failed during JSON generation, so export can only include the sections that exist in this draft.
          </p>
          <ul className="list-disc list-inside space-y-1">
            {generationErrors.slice(0, 5).map((error, i) => (
              <li key={i}>
                {error.section_id || "section"}: {error.message || "generation failed"}
              </li>
            ))}
          </ul>
        </Alert>
      )}

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
          _onDownload={handleExportJSON}
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
}: {
  section: GeneratedSection;
  expanded: boolean;
  onToggle: () => void;
  regenerating: boolean;
  onRegenerate: () => void;
}) {
  const needsVerification = section.slides?.some((s) =>
    s.bullets?.some((b) => b.source_needed),
  );

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
