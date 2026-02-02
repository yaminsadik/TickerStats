import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
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
} from "lucide-react";
import {
  Button,
  Card,
  Badge,
  Alert,
  Spinner,
  JsonViewerModal,
  type DeckExportData,
} from "../components/ui";
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
  type SectionResult,
} from "../api/deckApi";

export default function DeckDraftPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [draft, setDraft] = useState<DeckDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(
    null,
  );
  const [showJsonViewer, setShowJsonViewer] = useState(false);

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
      } else if ((loadedDraft?.generatedContent as any)?.results) {
        const results = (loadedDraft?.generatedContent as any)
          ?.results as SectionResult[];
        setExpandedSections(new Set(results.map((r) => r.section_id)));
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
    if (Array.isArray(gc.results) && gc.results.length > 0) {
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

  // Computed counts from export data
  const sectionsCount = exportData?.results?.length ?? 0;
  const slidesCount =
    exportData?.results?.reduce((sum, s) => sum + (s.slides?.length ?? 0), 0) ??
    0;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
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

  const { metadata, sections, warnings, results, provider_used, generated_at } =
    draft.generatedContent as any;

  const safeMetadata = metadata ?? {
    ticker: draft.basics.ticker,
    company_name:
      draft.basics.companyName ||
      draft.generatedContent?.metadata?.company_name ||
      draft.basics.ticker,
    generated_at: generated_at || new Date().toISOString(),
    provider: provider_used?.provider || draft.config.provider,
    model: provider_used?.model || "unknown",
  };

  const toTitleCase = (value: string) =>
    value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

  const safeSections: GeneratedSection[] = sections
    ? sections
    : (results || []).map((r: SectionResult) => ({
        section_id: r.section_id,
        section_name: toTitleCase(r.section_id),
        slides: r.slides || [],
        citations: r.citations,
      }));

  const rawWarnings: string[] | undefined = warnings
    ? warnings.map((w: any) =>
        typeof w === "string"
          ? w
          : w?.message || JSON.stringify(w, null, 2),
      )
    : Array.isArray((draft.generatedContent as any)?.errors)
      ? (draft.generatedContent as any).errors.map((e: any) =>
          typeof e === "string"
            ? e
            : e?.message || JSON.stringify(e, null, 2),
        )
      : undefined;

  const safeWarnings = rawWarnings
    ? rawWarnings.filter((w) => w !== "unhashable type: 'list'")
    : undefined;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="mb-2"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <h1 className="text-2xl font-bold text-white">
            {safeMetadata.company_name}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <Badge>{safeMetadata.ticker}</Badge>
            <span className="text-slate-400 text-sm">
              Generated{" "}
              {new Date(safeMetadata.generated_at).toLocaleDateString()}
            </span>
            <span className="text-slate-500 text-sm">
              • {safeMetadata.provider}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowJsonViewer(true)}
          >
            <FileCode className="w-4 h-4 mr-2" />
            View JSON
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportJSON}>
            <Download className="w-4 h-4 mr-2" />
            Export JSON
          </Button>
          <Button variant="danger" size="sm" onClick={handleDelete}>
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {/* Warnings */}
      {safeWarnings && safeWarnings.length > 0 && (
        <Alert variant="warning" title="Warnings" className="mb-6">
          <ul className="list-disc list-inside space-y-1">
            {safeWarnings.map((warning, i) => (
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

      {/* Metadata Footer */}
      <Card className="mt-8">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-slate-400">Model:</span>
            <span className="ml-2 text-white">{safeMetadata.model}</span>
          </div>
          <div>
            <span className="text-slate-400">Provider:</span>
            <span className="ml-2 text-white">{safeMetadata.provider}</span>
          </div>
          <div>
            <span className="text-slate-400">Generated:</span>
            <span className="ml-2 text-white">
              {new Date(safeMetadata.generated_at).toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Sections:</span>
            <span className="ml-2 text-white">{sectionsCount}</span>
          </div>
          <div>
            <span className="text-slate-400">Total Slides:</span>
            <span className="ml-2 text-white">{slidesCount}</span>
          </div>
        </div>
      </Card>

      {/* JSON Viewer Modal */}
      <JsonViewerModal
        isOpen={showJsonViewer}
        onClose={() => setShowJsonViewer(false)}
        exportData={exportData}
        deckName={safeMetadata.company_name}
        ticker={safeMetadata.ticker}
        onDownload={handleExportJSON}
        fallbackSections={safeSections}
      />
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
  return (
    <Card padding="none">
      {/* Section Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="w-5 h-5 text-slate-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-slate-400" />
          )}
          <h3 className="text-lg font-medium text-white">
            {section.section_name}
          </h3>
          <Badge variant="default">{section.slides.length} slides</Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            onRegenerate();
          }}
          disabled={regenerating}
        >
          <RefreshCw
            className={`w-4 h-4 mr-2 ${regenerating ? "animate-spin" : ""}`}
          />
          Regenerate
        </Button>
      </button>

      {/* Section Content */}
      {expanded && (
        <div className="border-t border-slate-800 p-4 space-y-6">
          {regenerating ? (
            <div className="flex items-center justify-center py-8">
              <Spinner size="md" />
              <span className="ml-3 text-slate-400">
                Regenerating section...
              </span>
            </div>
          ) : (
            section.slides.map((slide, slideIndex) => (
              <SlideContent key={slideIndex} slide={slide} index={slideIndex} />
            ))
          )}

          {/* Citations */}
          {section.citations && section.citations.length > 0 && (
            <div className="border-t border-slate-800 pt-4">
              <h5 className="text-sm font-medium text-slate-300 mb-2">
                Citations
              </h5>
              <ul className="space-y-1">
                {section.citations.map((citation, i) => (
                  <li
                    key={i}
                    className="text-sm text-slate-400 flex items-start gap-2"
                  >
                    <ExternalLink className="w-3 h-3 mt-1 flex-shrink-0" />
                    <span>{citation}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// Slide content component
function SlideContent({ slide, index }: { slide: Slide; index: number }) {
  return (
    <div className="bg-slate-800/30 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-white">{slide.title}</h4>
        <span className="text-xs text-slate-500">Slide {index + 1}</span>
      </div>

      <ul className="space-y-2">
        {slide.bullets.map((bullet, bulletIndex) => (
          <BulletItem key={bulletIndex} bullet={bullet} />
        ))}
      </ul>

      {slide.speaker_notes && (
        <div className="mt-4 pt-3 border-t border-slate-700">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">
            Speaker Notes
          </p>
          <p className="text-sm text-slate-400 italic">{slide.speaker_notes}</p>
        </div>
      )}
    </div>
  );
}

// Bullet point component
function BulletItem({ bullet }: { bullet: BulletPoint }) {
  return (
    <li className="flex items-start gap-2 text-slate-300">
      <span className="text-blue-500 mt-1.5">•</span>
      <span>{bullet.text}</span>
      {bullet.source_needed && (
        <span className="inline-flex items-center gap-1 text-yellow-500 text-xs">
          <AlertTriangle className="w-3 h-3" />
          <span>Needs verification</span>
        </span>
      )}
    </li>
  );
}
