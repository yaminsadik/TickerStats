import { useState, useEffect, useMemo } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileCode,
  X,
} from "lucide-react";
import Modal from "./Modal";
import Badge from "./Badge";
import Spinner from "./Spinner";
import { cn } from "../../utils/cn";

// Types matching the export schema
interface ExportBullet {
  text: string;
  source_needed?: boolean;
  citations?: string[];
}

interface ExportSlide {
  slide_id?: string;
  title: string;
  bullets: ExportBullet[];
  speaker_notes?: string;
  layout_hints?: {
    style?: string;
    suggested_visual?: string;
    max_bullets?: number;
  };
  flags?: {
    contains_numbers?: boolean;
    is_draft?: boolean;
    needs_sources?: boolean;
  };
}

interface ExportSection {
  section_id: string;
  slides: ExportSlide[];
  needs_verification?: boolean;
  citations?: string[];
  verification_notes?: string[];
  generation_metadata?: {
    latency_ms?: number;
    model?: string;
    retries?: number;
    tokens?: {
      completion_tokens?: number;
      prompt_tokens?: number;
      reasoning_tokens?: number;
      total_tokens?: number;
    };
  };
}

export interface DeckExportData {
  ticker: string;
  company_name?: string;
  generated_at: string;
  request_id?: string;
  provider_used?: {
    provider: string;
    model: string;
    reasoning_level?: string;
  };
  computed_inputs?: {
    comps_table?: unknown;
  };
  results: ExportSection[];
  errors?: string[];
  // Also support the internal GenerateDeckResponse format
  metadata?: {
    ticker: string;
    company_name: string;
    generated_at: string;
    provider: string;
    model: string;
  };
  sections?: Array<{
    section_id: string;
    section_name: string;
    slides: ExportSlide[];
    citations?: string[];
  }>;
}

interface JsonViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  exportData: DeckExportData | null;
  deckName: string;
  ticker: string;
  _onDownload: () => void;
  inline?: boolean;
}

type TabId = "rendered" | "raw";

export default function JsonViewerModal({
  isOpen,
  onClose,
  exportData,
  deckName,
  ticker,
  _onDownload,
  inline = false,
}: JsonViewerModalProps) {
  void _onDownload;
  const [activeTab, setActiveTab] = useState<TabId>("rendered");
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(
    null,
  );
  const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());
  const [rawJson, setRawJson] = useState<string>("");
  const [isStringifying, setIsStringifying] = useState(false);

  // Normalize the export data to always use results format
  const normalizedSections = useMemo(() => {
    if (!exportData) return [];

    // If results array exists, use it
    if (exportData.results && exportData.results.length > 0) {
      return exportData.results;
    }

    // Fall back to sections (internal format) and convert
    if (exportData.sections && exportData.sections.length > 0) {
      return exportData.sections.map((s) => ({
        section_id: s.section_id,
        slides: s.slides,
        needs_verification: false,
        citations: s.citations,
      }));
    }

    return [];
  }, [exportData]);

  // Get metadata
  const exportMetadata = useMemo(() => {
    if (!exportData) return null;

    if (exportData.provider_used) {
      return {
        provider: exportData.provider_used.provider,
        model: exportData.provider_used.model,
        generated_at: exportData.generated_at,
      };
    }

    if (exportData.metadata) {
      return {
        provider: exportData.metadata.provider,
        model: exportData.metadata.model,
        generated_at: exportData.metadata.generated_at,
      };
    }

    return {
      provider: "unknown",
      model: "unknown",
      generated_at: exportData.generated_at || new Date().toISOString(),
    };
  }, [exportData]);

  // Select first section by default
  useEffect(() => {
    if (isOpen && normalizedSections.length > 0 && !selectedSectionId) {
      setSelectedSectionId(normalizedSections[0].section_id);
    }
  }, [isOpen, normalizedSections, selectedSectionId]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedSectionId(null);
      setActiveTab("rendered");
      setExpandedNotes(new Set());
    }
  }, [isOpen]);

  // Stringify JSON in a deferred task to avoid freezing
  useEffect(() => {
    if (isOpen && exportData && activeTab === "raw") {
      setIsStringifying(true);
      const hasIdleCallback = typeof requestIdleCallback !== "undefined";
      const handle = hasIdleCallback
        ? requestIdleCallback(() => {
            setRawJson(JSON.stringify(exportData, null, 2));
            setIsStringifying(false);
          })
        : setTimeout(() => {
            setRawJson(JSON.stringify(exportData, null, 2));
            setIsStringifying(false);
          }, 0);

      return () => {
        if (hasIdleCallback) {
          cancelIdleCallback(handle as number);
        } else {
          clearTimeout(handle as ReturnType<typeof setTimeout>);
        }
      };
    }
  }, [isOpen, exportData, activeTab]);

  // Toggle speaker notes
  const toggleNotes = (slideId: string) => {
    setExpandedNotes((prev) => {
      const next = new Set(prev);
      if (next.has(slideId)) {
        next.delete(slideId);
      } else {
        next.add(slideId);
      }
      return next;
    });
  };

  // Convert section_id to title case
  const toTitleCase = (str: string) =>
    str.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

  // Get selected section
  const selectedSection = normalizedSections.find(
    (s) => s.section_id === selectedSectionId,
  );

  // Compute total slides
  const totalSlides = normalizedSections.reduce(
    (sum, s) => sum + (s.slides?.length ?? 0),
    0,
  );

  const content = (
    <div className="flex flex-col h-[calc(90vh-120px)] max-md:h-[calc(100vh-120px)]">
      {/* Tabs */}
      <div className="flex border-b border-slate-700 px-4 shrink-0">
        <button
          onClick={() => setActiveTab("rendered")}
          className={cn(
            "px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
            activeTab === "rendered"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-slate-400 hover:text-white",
          )}
        >
          Slides
        </button>
        {import.meta.env.DEV && (
          <button
            onClick={() => setActiveTab("raw")}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center gap-2",
              activeTab === "raw"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-white",
            )}
          >
            <FileCode className="w-4 h-4" />
            Raw JSON
          </button>
        )}
      </div>

      {/* Tab Content */}
      <div className="flex-1 min-h-0 overflow-auto">
        {activeTab === "rendered" ? (
          <RenderedView
            sections={normalizedSections}
            selectedSectionId={selectedSectionId}
            onSelectSection={setSelectedSectionId}
            selectedSection={selectedSection}
            expandedNotes={expandedNotes}
            toggleNotes={toggleNotes}
            toTitleCase={toTitleCase}
            totalSlides={totalSlides}
            metadata={exportMetadata}
          />
        ) : (
          <RawJsonView json={rawJson} isLoading={isStringifying} />
        )}
      </div>
    </div>
  );

  if (inline) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-lg shadow-xl">
        <div className="flex items-start justify-between p-4 border-b border-slate-700">
          <div>
            <h2 className="text-lg font-semibold text-white">Deck Details</h2>
            <p className="text-sm text-slate-400 mt-0.5">
              {deckName} ({ticker})
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            aria-label="Close deck details"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 min-h-0">{content}</div>
      </div>
    );
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Deck Details"
      subtitle={`${deckName} (${ticker})`}
      size="xl"
      fullScreenOnMobile
    >
      {content}
    </Modal>
  );
}

// Rendered View Component
function RenderedView({
  sections,
  selectedSectionId,
  onSelectSection,
  selectedSection,
  expandedNotes,
  toggleNotes,
  toTitleCase,
  totalSlides,
  metadata,
}: {
  sections: ExportSection[];
  selectedSectionId: string | null;
  onSelectSection: (id: string) => void;
  selectedSection: ExportSection | undefined;
  expandedNotes: Set<string>;
  toggleNotes: (id: string) => void;
  toTitleCase: (str: string) => string;
  totalSlides: number;
  metadata: { provider: string; model: string; generated_at: string } | null;
}) {
  if (sections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4">
          <AlertTriangle className="w-8 h-8 text-yellow-500" />
        </div>
        <h3 className="text-lg font-medium text-white mb-2">
          No sections generated yet
        </h3>
        <p className="text-slate-400 max-w-md">
          This deck doesn't have any generated content. Try regenerating the
          deck to see results here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left Sidebar - Section List */}
      <div className="w-64 border-r border-slate-700 flex flex-col shrink-0 max-md:hidden overflow-hidden">
        {/* Summary */}
        <div className="p-3 border-b border-slate-700 bg-slate-800/50 shrink-0">
          <div className="text-xs text-slate-400 space-y-1">
            <div className="flex justify-between">
              <span>Sections:</span>
              <span className="text-white font-medium">{sections.length}</span>
            </div>
            <div className="flex justify-between">
              <span>Total Slides:</span>
              <span className="text-white font-medium">{totalSlides}</span>
            </div>
            {metadata && (
              <div className="flex justify-between">
                <span>Model:</span>
                <span className="text-white font-medium truncate ml-2">
                  {metadata.model}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Section List */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {sections.map((section) => (
            <button
              key={section.section_id}
              onClick={() => onSelectSection(section.section_id)}
              className={cn(
                "w-full text-left px-3 py-2.5 border-b border-slate-800 transition-colors",
                selectedSectionId === section.section_id
                  ? "bg-blue-600/20 border-l-2 border-l-blue-500"
                  : "hover:bg-slate-800/50",
              )}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "text-sm font-medium",
                    selectedSectionId === section.section_id
                      ? "text-blue-400"
                      : "text-white",
                  )}
                >
                  {toTitleCase(section.section_id)}
                </span>
                {section.needs_verification && (
                  <Badge variant="warning" className="text-xs py-0">
                    Verify
                  </Badge>
                )}
              </div>
              <span className="text-xs text-slate-500">
                {section.slides?.length ?? 0} slide
                {(section.slides?.length ?? 0) !== 1 ? "s" : ""}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Mobile Section Selector */}
      <div className="md:hidden border-b border-slate-700 p-2 shrink-0">
        <select
          value={selectedSectionId || ""}
          onChange={(e) => onSelectSection(e.target.value)}
          className="w-full bg-slate-800 text-white rounded-lg px-3 py-2 text-sm border border-slate-600"
        >
          {sections.map((section) => (
            <option key={section.section_id} value={section.section_id}>
              {toTitleCase(section.section_id)} ({section.slides?.length ?? 0}{" "}
              slides)
              {section.needs_verification ? " ⚠️" : ""}
            </option>
          ))}
        </select>
      </div>

      {/* Right Content - Selected Section */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4">
        {selectedSection ? (
          <div className="space-y-4">
            {/* Section Header */}
            <div className="flex items-center gap-3 mb-4">
              <h3 className="text-xl font-semibold text-white">
                {toTitleCase(selectedSection.section_id)}
              </h3>
              {selectedSection.needs_verification && (
                <Badge variant="warning">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Needs Verification
                </Badge>
              )}
            </div>

            {/* Verification Notes */}
            {selectedSection.verification_notes &&
              selectedSection.verification_notes.length > 0 && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mb-4">
                  <h4 className="text-sm font-medium text-yellow-400 mb-2">
                    Verification Notes
                  </h4>
                  <ul className="text-sm text-yellow-300/80 space-y-1 list-disc list-inside">
                    {selectedSection.verification_notes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* Slides */}
            {selectedSection.slides?.map((slide, slideIndex) => {
              const slideId = slide.slide_id || `slide-${slideIndex}`;
              const isNotesExpanded = expandedNotes.has(slideId);

              return (
                <div
                  key={slideId}
                  className="bg-slate-800/50 rounded-lg border border-slate-700 overflow-hidden"
                >
                  {/* Slide Header */}
                  <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-500 font-mono">
                        #{slideIndex + 1}
                      </span>
                      <h4 className="font-medium text-white">{slide.title}</h4>
                    </div>
                    {slide.layout_hints?.style && (
                      <span className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">
                        {slide.layout_hints.style}
                      </span>
                    )}
                  </div>

                  {/* Bullets */}
                  <div className="p-4">
                    <ul className="space-y-2">
                      {slide.bullets?.map((bullet, bulletIndex) => (
                        <li
                          key={bulletIndex}
                          className="flex items-start gap-2 text-slate-300"
                        >
                          <span className="text-blue-500 mt-1">•</span>
                          <span className="flex-1">{bullet.text}</span>
                          {bullet.source_needed && (
                            <span className="text-yellow-500 text-xs flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />
                              Source
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Speaker Notes (Collapsible) */}
                  {slide.speaker_notes && (
                    <div className="border-t border-slate-700">
                      <button
                        onClick={() => toggleNotes(slideId)}
                        className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-400 hover:bg-slate-700/50 transition-colors"
                      >
                        {isNotesExpanded ? (
                          <ChevronDown className="w-4 h-4" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                        Speaker Notes
                      </button>
                      {isNotesExpanded && (
                        <div className="px-4 pb-3">
                          <p className="text-sm text-slate-400 italic whitespace-pre-wrap">
                            {slide.speaker_notes}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Citations */}
            {selectedSection.citations &&
              selectedSection.citations.length > 0 && (
                <div className="mt-6 pt-4 border-t border-slate-700">
                  <h4 className="text-sm font-medium text-slate-300 mb-2">
                    Citations
                  </h4>
                  <ul className="text-sm text-slate-400 space-y-1">
                    {selectedSection.citations.map((citation, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-slate-500">[{i + 1}]</span>
                        <span>{citation}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-400">
            Select a section to view its content
          </div>
        )}
      </div>
    </div>
  );
}

// Raw JSON View Component
function RawJsonView({
  json,
  isLoading,
}: {
  json: string;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="md" />
        <span className="ml-3 text-slate-400">Preparing JSON...</span>
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 overflow-auto p-4">
      <pre className="text-sm font-mono text-slate-300 whitespace-pre-wrap break-words">
        {json}
      </pre>
    </div>
  );
}
