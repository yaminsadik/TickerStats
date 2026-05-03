import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import Breadcrumbs, { BreadcrumbItem } from "../components/Breadcrumbs";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Users,
  Plus,
  Trash2,
} from "lucide-react";
import ModelReasoningBar from "../components/ModelReasoningBar";
import {
  FREE_MODEL_OPTIONS,
  PRO_MODEL_OPTIONS,
  PROVIDER_LABELS,
  getQualityOptions,
  resolveModelForRequest,
} from "../config/modelConfig";
import {
  Button,
  Card,
  Input,
  TextArea,
  Select,
  Alert,
  Badge,
  CardSkeleton,
} from "../components/ui";
import { TickerInput } from "../components/TickerInput";
import { RelativeTable } from "../components/RelativeTable";
import { useRelativeTable } from "../hooks/useRelativeTable";
import { SNAPSHOT_FIELDS } from "../types/api";
import type { FetchRelativeParams } from "../api/client";
import { useSignalSettings } from "../hooks/useSignalSettings";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import { useUserProfile } from "../hooks/useUserProfile";
import {
  fetchSections,
  generateDeckAuthed,
  normalizeAvailableSections,
  type Section,
  type GenerateDeckResponse,
  type ThesisInput,
  type CatalystInput,
  type ValuationMethodInput,
  type RiskInput,
  type DataBlocks,
  type UserConstraints,
  type Position,
  type DeckLength,
  type DataTrustMode,
} from "../api/deckApi";
import { queryKeys } from "../lib/queryKeys";
import { sectionSchema } from "../schemas/deck";
import { useSaveDeck } from "../queries/useDeckQueries";
import { parseOrThrow } from "../lib/parse";
import { z } from "zod";
import {
  createDraft,
  updateDraftBasics,
  updateDraftConfig,
  updateDraftIntake,
  saveDraftContent,
  markDraftGenerating,
  markDraftError,
  type DeckDraft,
  type DeckDraftBasics,
  type DeckDraftConfig,
  type DeckDraftIntake,
  type FundConstraints,
} from "../stores/deckDraft";

type WizardStep =
  | "basics"
  | "thesis"
  | "comparables"
  | "sections"
  | "generate"
  | "save";

const STEPS: { id: WizardStep; label: string }[] = [
  { id: "basics", label: "Shape" },
  { id: "thesis", label: "Thesis" },
  { id: "comparables", label: "Comps" },
  { id: "sections", label: "Sections" },
  { id: "generate", label: "Generate" },
  { id: "save", label: "Save" },
];

const EXPECTED_SECTION_COUNT = 14;

function hasMeaningfulGeneratedContent(data: GenerateDeckResponse): boolean {
  const sections = data.results?.length ? data.results : (data.sections ?? []);
  return sections.some((section) =>
    (section.slides ?? []).some((slide) =>
      (slide.bullets ?? []).some((bullet) => bullet.text.trim().length > 0),
    ),
  );
}

function formatGenerationErrors(data: GenerateDeckResponse): string {
  const errors = data.errors ?? [];
  if (errors.length === 0) return "";
  return errors
    .slice(0, 3)
    .map((err) => `${err.section_id}: ${err.error_type} - ${err.message}`)
    .join("; ");
}

// --- Collapsible section helper ---
function CollapsibleSection({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-700 rounded-lg">
      <button
        type="button"
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/50 transition-colors rounded-lg"
        onClick={() => setOpen(!open)}
      >
        <div>
          <span className="text-white font-medium">{title}</span>
          {subtitle && (
            <span className="text-slate-400 text-sm ml-2">{subtitle}</span>
          )}
        </div>
        <ChevronDown
          className={`w-5 h-5 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="px-4 pb-4 space-y-4">{children}</div>}
    </div>
  );
}

// --- Valuation method options ---
const VALUATION_METHODS = [
  { value: "relative", label: "Relative Valuation" },
  { value: "dcf", label: "DCF" },
  { value: "sotp", label: "Sum-of-Parts" },
  { value: "nav", label: "NAV" },
  { value: "unit_econ", label: "Unit Economics" },
  { value: "yield", label: "Yield Lens" },
];

export default function DeckWizardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { authenticatedFetch } = useAuthenticatedFetch();
  const { tier, deckCount, deckLimit, loading: profileLoading } =
    useUserProfile();
  const atDeckLimit = deckLimit !== null && deckCount >= deckLimit;

  // Get pre-filled ticker and comparables from navigation state
  const locationState = location.state as {
    ticker?: string;
    comparables?: string[];
  } | null;
  const initialTicker = locationState?.ticker || "";
  const initialComparables = locationState?.comparables || [];

  // Current step
  const [currentStep, setCurrentStep] = useState<WizardStep>("basics");

  // Draft state
  const [draft, setDraft] = useState<DeckDraft | null>(null);

  // ===== Phase 1: Shape the pitch =====
  const [basics, setBasics] = useState<DeckDraftBasics>({
    ticker: initialTicker,
    companyName: "",
    sector: "",
    companyContext: "",
    investmentThesis: "",
    position: undefined,
    deckLength: "standard",
    dataTrustMode: "user_auto_fetch",
  });

  const [fundConstraints, setFundConstraints] = useState<FundConstraints>({
    time_horizon: "12-24 months",
    risk_profile: "moderate",
    portfolio_context: "",
    style: "student investment fund pitch deck",
  });

  // ===== Phase 2: Thesis =====
  const [thesis, setThesis] = useState<ThesisInput>({
    thesis_sentence: "",
    market_believes: "",
    we_believe: "",
    pillars: [],
    what_changes_mind: [],
  });
  const [pillarDraft, setPillarDraft] = useState("");
  const [wcmDraft, setWcmDraft] = useState("");

  // ===== Phase 3: Catalysts =====
  const [catalysts, setCatalysts] = useState<CatalystInput[]>([]);

  // ===== Phase 4: Valuation =====
  const [valuationInput, setValuationInput] = useState<ValuationMethodInput>({
    methods: [],
    peer_tickers: [],
    target_multiple_range: "",
    dcf_assumptions: "",
    price_target: "",
  });

  // ===== Phase 5: Risks =====
  const [risks, setRisks] = useState<RiskInput[]>([]);

  // ===== Phase 6: Data Blocks =====
  const [dataBlocks, setDataBlocks] = useState<DataBlocks>({});

  // ===== Phase 7: Constraints =====
  const [userConstraints, setUserConstraints] = useState<UserConstraints>({
    exclude_peers: [],
  });

  // ===== Config state =====
  const [config, setConfig] = useState<DeckDraftConfig>({
    sections: [],
    provider: "gemini",
    model: "gemini-3.1-pro-preview",
    quality: "high",
  });

  // Comparable companies state
  const [compTickers, setCompTickers] = useState<string[]>(initialComparables);
  const [showCompsPreview, setShowCompsPreview] = useState(false);
  const [compsShowPerf, setCompsShowPerf] = useState(false);
  const [compsShowDcf, setCompsShowDcf] = useState(false);

  // Preview query for comparables
  const [previewParams, setPreviewParams] =
    useState<FetchRelativeParams | null>(null);
  const { data: compsPreview, isLoading: compsLoading } =
    useRelativeTable(previewParams);
  const { settings: signalSettings } = useSignalSettings();

  // Generated content
  const [generatedDeck, setGeneratedDeck] =
    useState<GenerateDeckResponse | null>(null);
  const [limitError, setLimitError] = useState<string | null>(null);

  // Fetch sections (with Zod validation)
  const {
    data: availableSections,
    isLoading: sectionsLoading,
    error: sectionsError,
  } = useQuery({
    queryKey: [...queryKeys.sections, "canonical-v4"],
    queryFn: async () => {
      const raw = await fetchSections();
      const parsed = parseOrThrow(
        z.array(sectionSchema),
        raw,
        "sections",
      ) as Section[];
      return normalizeAvailableSections(parsed);
    },
    staleTime: 5 * 60 * 1000,
  });

  const missingSectionCount = useMemo(() => {
    if (!availableSections) return 0;
    return Math.max(0, EXPECTED_SECTION_COUNT - availableSections.length);
  }, [availableSections]);

  // Prune stale section IDs if backend-supported section list changes.
  useEffect(() => {
    if (!availableSections) return;
    const validSectionIds = new Set(availableSections.map((s) => s.id));
    setConfig((prev) => {
      const filtered = prev.sections.filter((id) => validSectionIds.has(id));
      if (filtered.length === prev.sections.length) return prev;
      return { ...prev, sections: filtered };
    });
  }, [availableSections]);

  // Derived model info
  const modelOptions = useMemo(() => {
    if (tier === "pro" || tier === "enterprise") {
      return [...PRO_MODEL_OPTIONS, ...FREE_MODEL_OPTIONS];
    }
    return FREE_MODEL_OPTIONS;
  }, [tier]);

  const selectedModel = useMemo(
    () => modelOptions.find((m) => m.value === config.model),
    [modelOptions, config.model],
  );

  const qualityOptions = useMemo(
    () => getQualityOptions(config.provider, config.model || ""),
    [config.provider, config.model],
  );

  const qualityLabel = useMemo(() => {
    const match = qualityOptions.find((o) => o.value === config.quality);
    return match?.label ?? config.quality;
  }, [qualityOptions, config.quality]);

  // Keep selected model/provider valid for current tier.
  // Skip until profile is resolved; tier defaults to "free" while loading and
  // would incorrectly downgrade Pro users from 3.1 Pro to Flash.
  useEffect(() => {
    if (profileLoading) return;
    const current = modelOptions.find(
      (option) => option.value === config.model,
    );
    if (!current) {
      const fallback = modelOptions[0];
      setConfig((prev) => ({
        ...prev,
        model: fallback.value,
        provider: fallback.provider,
      }));
      return;
    }
    if (config.provider !== current.provider) {
      setConfig((prev) => ({ ...prev, provider: current.provider }));
    }
  }, [
    profileLoading,
    modelOptions,
    config.model,
    config.provider,
  ]);

  // Save deck to DB mutation
  const saveDeckMutation = useSaveDeck();

  // Generate deck mutation
  const generateMutation = useMutation({
    mutationFn: async (
      payload: import("../api/deckApi").GenerateDeckRequest,
    ) => {
      const data = await generateDeckAuthed(authenticatedFetch, payload);
      if (!hasMeaningfulGeneratedContent(data)) {
        const details = formatGenerationErrors(data);
        const requestId = data.request_id
          ? ` (request_id: ${data.request_id})`
          : "";
        const suffix = details ? ` Details: ${details}` : "";
        throw new Error(
          `Generation returned empty section content${requestId}.${suffix}`,
        );
      }
      return data;
    },
    onMutate: () => {
      if (draft) {
        markDraftGenerating(draft.id);
      }
    },
    onSuccess: async (data) => {
      setGeneratedDeck(data);
      if (draft) {
        saveDraftContent(draft.id, data);
        setDraft({ ...draft, status: "complete", generatedContent: data });

        try {
          const dbDeck = await saveDeckMutation.mutateAsync({
            ticker: basics.ticker,
            title: data.company_name
              ? `${data.company_name} Pitch Deck`
              : `${basics.ticker} Pitch Deck`,
            content: data as unknown as Record<string, unknown>,
            llm_provider: config.provider,
          });
          navigate(`/deck/db/${dbDeck.id}`);
        } catch {
          navigate(`/deck/${draft.id}`);
        }
      }
    },
    onError: (error: Error) => {
      if (draft) {
        markDraftError(draft.id, error.message);
      }
    },
  });

  // Get current step index
  const currentStepIndex = STEPS.findIndex((s) => s.id === currentStep);

  // Navigation
  const canGoBack = currentStepIndex > 0 && !generateMutation.isPending;
  const canGoNext = currentStepIndex < STEPS.length - 1;

  const goBack = () => {
    if (canGoBack) {
      setCurrentStep(STEPS[currentStepIndex - 1].id);
    }
  };

  const goNext = () => {
    if (canGoNext) {
      setCurrentStep(STEPS[currentStepIndex + 1].id);
    }
  };

  // Validate current step
  const isStepValid = useCallback((): boolean => {
    switch (currentStep) {
      case "basics":
        return basics.ticker.trim().length > 0;
      case "thesis":
        return true; // thesis is recommended but optional
      case "comparables":
        return true;
      case "sections":
        return config.sections.length > 0;
      case "generate":
        return generatedDeck !== null;
      case "save":
        return true;
      default:
        return false;
    }
  }, [currentStep, basics.ticker, config.sections.length, generatedDeck]);

  // Create/update draft on step transitions
  const handleBasicsNext = () => {
    if (!isStepValid()) return;
    if (!draft) {
      const intakeData: DeckDraftIntake = {
        thesis,
        catalysts,
        valuationInput,
        risks,
        dataBlocks,
        userConstraints,
      };
      const newDraft = createDraft(basics, config, intakeData);
      setDraft(newDraft);
    } else {
      updateDraftBasics(draft.id, basics);
    }
    goNext();
  };

  const handleThesisNext = () => {
    if (draft) {
      updateDraftIntake(draft.id, {
        thesis,
        catalysts,
        valuationInput,
        risks,
        dataBlocks,
        userConstraints,
      });
    }
    goNext();
  };

  const handleConfigNext = () => {
    if (!isStepValid()) return;
    if (draft) {
      updateDraftConfig(draft.id, config);
    }
    goNext();
  };

  // Generate deck - wire up ALL intake fields
  const handleGenerate = () => {
    if (atDeckLimit) {
      setLimitError(
        `You have reached your free deck limit (${deckCount}/${deckLimit}). Export is available after you unlock a finished deck.`,
      );
      return;
    }
    setLimitError(null);
    if (draft) {
      updateDraftConfig(draft.id, config);
      updateDraftIntake(draft.id, {
        thesis,
        catalysts,
        valuationInput,
        risks,
        dataBlocks,
        userConstraints,
      });
    }

    const providerToUse = selectedModel?.provider || config.provider;
    const modelToUse = resolveModelForRequest(
      providerToUse,
      config.model,
      config.quality,
    );

    // Build thesis only if user provided any field
    const hasThesis =
      thesis.thesis_sentence?.trim() ||
      thesis.market_believes?.trim() ||
      thesis.we_believe?.trim() ||
      (thesis.pillars && thesis.pillars.length > 0);

    // Build valuation only if user selected methods
    const hasValuation =
      valuationInput.methods && valuationInput.methods.length > 0;

    // Filter empty catalyst/risk entries
    const validCatalysts = catalysts.filter((c) => c.name.trim());
    const validRisks = risks.filter((r) => r.risk.trim());

    // Build data_blocks only if any field is non-empty
    const hasDataBlocks = Object.values(dataBlocks).some(
      (v) => typeof v === "string" && v.trim(),
    );

    // Build user_constraints only if any field is non-empty
    const hasConstraints =
      userConstraints.liquidity_floor?.trim() ||
      userConstraints.leverage_ceiling?.trim() ||
      userConstraints.esg_constraints?.trim() ||
      (userConstraints.exclude_peers && userConstraints.exclude_peers.length > 0);

    generateMutation.mutate({
      ticker: basics.ticker,
      ...(basics.companyName.trim() && { company_name: basics.companyName }),
      ...(basics.sector.trim() && { sector: basics.sector }),
      fund_constraints: fundConstraints,
      sections: config.sections.length > 0 ? config.sections : undefined,
      provider: providerToUse,
      model: modelToUse,
      plan_tier: tier,
      model_mode: "specific",
      analysis_depth: config.quality,
      reasoning_level: config.quality,
      include_comps: true,
      ...(compTickers.length > 0 && { comp_tickers: compTickers }),
      // Intake redesign fields
      ...(basics.position && { position: basics.position }),
      ...(basics.deckLength && { deck_length: basics.deckLength }),
      ...(basics.dataTrustMode && { data_trust_mode: basics.dataTrustMode }),
      ...(hasThesis && { thesis }),
      ...(validCatalysts.length > 0 && { catalysts: validCatalysts }),
      ...(hasValuation && { valuation_input: valuationInput }),
      ...(validRisks.length > 0 && { risks: validRisks }),
      ...(hasDataBlocks && { data_blocks: dataBlocks }),
      ...(hasConstraints && { user_constraints: userConstraints }),
    });
  };

  // Save and view
  const handleSave = () => {
    if (draft) {
      navigate(`/deck/${draft.id}`);
    }
  };

  // Toggle section selection
  const toggleSection = (sectionId: string) => {
    setConfig((prev) => ({
      ...prev,
      sections: prev.sections.includes(sectionId)
        ? prev.sections.filter((id) => id !== sectionId)
        : [...prev.sections, sectionId],
    }));
  };

  // --- Catalyst helpers ---
  const addCatalyst = () => {
    if (catalysts.length >= 6) return;
    setCatalysts((prev) => [...prev, { name: "", timing_window: "", mechanism: "" }]);
  };
  const removeCatalyst = (index: number) => {
    setCatalysts((prev) => prev.filter((_, i) => i !== index));
  };
  const updateCatalyst = (index: number, field: keyof CatalystInput, value: string) => {
    setCatalysts((prev) =>
      prev.map((c, i) => (i === index ? { ...c, [field]: value } : c)),
    );
  };

  // --- Risk helpers ---
  const addRisk = () => {
    if (risks.length >= 6) return;
    setRisks((prev) => [...prev, { risk: "", leading_indicator: "", mitigant: "" }]);
  };
  const removeRisk = (index: number) => {
    setRisks((prev) => prev.filter((_, i) => i !== index));
  };
  const updateRisk = (index: number, field: keyof RiskInput, value: string) => {
    setRisks((prev) =>
      prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)),
    );
  };

  // --- Pillar / WCM helpers ---
  const addPillar = () => {
    const trimmed = pillarDraft.trim();
    if (!trimmed || (thesis.pillars?.length ?? 0) >= 5) return;
    setThesis((prev) => ({ ...prev, pillars: [...(prev.pillars ?? []), trimmed] }));
    setPillarDraft("");
  };
  const removePillar = (index: number) => {
    setThesis((prev) => ({
      ...prev,
      pillars: (prev.pillars ?? []).filter((_, i) => i !== index),
    }));
  };
  const addWcm = () => {
    const trimmed = wcmDraft.trim();
    if (!trimmed || (thesis.what_changes_mind?.length ?? 0) >= 2) return;
    setThesis((prev) => ({
      ...prev,
      what_changes_mind: [...(prev.what_changes_mind ?? []), trimmed],
    }));
    setWcmDraft("");
  };
  const removeWcm = (index: number) => {
    setThesis((prev) => ({
      ...prev,
      what_changes_mind: (prev.what_changes_mind ?? []).filter((_, i) => i !== index),
    }));
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Breadcrumbs */}
      <Breadcrumbs>
        <BreadcrumbItem href="/browse">Browse</BreadcrumbItem>
        <BreadcrumbItem current>Generate Deck</BreadcrumbItem>
      </Breadcrumbs>

      {/* Mobile Step Indicator */}
      <div className="md:hidden mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-slate-400">
            Step {currentStepIndex + 1} of {STEPS.length}
          </span>
          <span className="text-sm font-medium text-white">
            {STEPS[currentStepIndex].label}
          </span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{
              width: `${((currentStepIndex + 1) / STEPS.length) * 100}%`,
            }}
            role="progressbar"
            aria-valuenow={currentStepIndex + 1}
            aria-valuemin={1}
            aria-valuemax={STEPS.length}
            aria-label={`Step ${currentStepIndex + 1} of ${STEPS.length}`}
          />
        </div>
      </div>

      {/* Desktop Progress Steps */}
      <nav className="mb-8 hidden md:block" aria-label="Progress">
        <ol className="flex items-center justify-between">
          {STEPS.map((step, index) => {
            const isActive = step.id === currentStep;
            const isCompleted = index < currentStepIndex;
            const isClickable = isCompleted;

            return (
              <li key={step.id} className="flex items-center">
                <button
                  onClick={() => isClickable && setCurrentStep(step.id)}
                  disabled={!isClickable}
                  className={`flex flex-col items-center ${
                    isClickable
                      ? "cursor-pointer hover:opacity-80"
                      : "cursor-default"
                  } transition-opacity`}
                  aria-label={`${step.label} - ${isCompleted ? "Completed" : isActive ? "Current" : "Upcoming"}`}
                >
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors ${
                      isCompleted
                        ? "bg-blue-600 border-blue-600 text-white"
                        : isActive
                          ? "border-blue-500 text-blue-500 bg-slate-900"
                          : "border-slate-700 text-slate-500 bg-slate-900"
                    }`}
                    aria-current={isActive ? "step" : undefined}
                  >
                    {isCompleted ? <Check className="w-5 h-5" /> : index + 1}
                  </div>
                  <span
                    className={`mt-2 text-xs font-medium ${
                      isActive ? "text-white" : "text-slate-500"
                    }`}
                  >
                    {step.label}
                  </span>
                </button>
                {index < STEPS.length - 1 && (
                  <div
                    className={`w-full h-0.5 mx-2 ${
                      isCompleted ? "bg-blue-600" : "bg-slate-700"
                    }`}
                    style={{ minWidth: "24px" }}
                    aria-hidden="true"
                  />
                )}
              </li>
            );
          })}
        </ol>
      </nav>

      {/* Step Content */}
      <Card className="mb-6">
        {/* ================================================================ */}
        {/* Step 1: Shape the Pitch (Phase 1) */}
        {/* ================================================================ */}
        {currentStep === "basics" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Shape the Pitch
              </h2>
              <p className="text-slate-400">
                Enter the ticker and key parameters. Company name and sector
                auto-fetch if not provided.
              </p>
            </div>

            {limitError && (
              <Alert variant="error" title="Deck Limit">
                {limitError}
              </Alert>
            )}

            <Input
              label="Ticker Symbol"
              placeholder="e.g., AAPL, MSFT, GOOGL"
              value={basics.ticker}
              onChange={(e) =>
                setBasics((prev) => ({
                  ...prev,
                  ticker: e.target.value.toUpperCase(),
                }))
              }
              helperText="Required"
            />

            <div className="grid grid-cols-2 gap-4">
              <Select
                label="Position"
                value={basics.position ?? ""}
                onChange={(e) =>
                  setBasics((prev) => ({
                    ...prev,
                    position: (e.target.value || undefined) as Position | undefined,
                  }))
                }
                options={[
                  { value: "", label: "Not specified" },
                  { value: "long", label: "Long" },
                  { value: "short", label: "Short" },
                ]}
              />
              <Select
                label="Deck Length"
                value={basics.deckLength ?? "standard"}
                onChange={(e) =>
                  setBasics((prev) => ({
                    ...prev,
                    deckLength: e.target.value as DeckLength,
                  }))
                }
                options={[
                  { value: "short", label: "Short (6-8 slides)" },
                  { value: "standard", label: "Standard (10-14 slides)" },
                  { value: "deep", label: "Deep (15-20 slides)" },
                ]}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Select
                label="Time Horizon"
                value={fundConstraints.time_horizon}
                onChange={(e) =>
                  setFundConstraints((prev) => ({
                    ...prev,
                    time_horizon: e.target.value,
                  }))
                }
                options={[
                  { value: "6-12 months", label: "6-12 months" },
                  { value: "12-24 months", label: "12-24 months" },
                  { value: "24-36 months", label: "24-36 months" },
                ]}
              />
              <Select
                label="Risk Profile"
                value={fundConstraints.risk_profile}
                onChange={(e) =>
                  setFundConstraints((prev) => ({
                    ...prev,
                    risk_profile: e.target.value,
                  }))
                }
                options={[
                  { value: "conservative", label: "Conservative" },
                  { value: "moderate", label: "Moderate" },
                  { value: "aggressive", label: "Aggressive" },
                ]}
              />
            </div>

            <Select
              label="Data Trust Mode"
              value={basics.dataTrustMode ?? "user_auto_fetch"}
              onChange={(e) =>
                setBasics((prev) => ({
                  ...prev,
                  dataTrustMode: e.target.value as DataTrustMode,
                }))
              }
              options={[
                {
                  value: "user_only",
                  label: "User-Only Numbers",
                },
                {
                  value: "user_auto_fetch",
                  label: "User + Auto-Fetch (Recommended)",
                },
                {
                  value: "narrative_only",
                  label: "Narrative-Only (No Numbers)",
                },
              ]}
            />
            <p className="text-xs text-slate-500 -mt-4">
              {basics.dataTrustMode === "user_only"
                ? "Model will only use numbers you provide. Everything else is qualitative."
                : basics.dataTrustMode === "narrative_only"
                  ? "No financial numbers in the deck. Everything is qualitative narrative."
                  : "Numbers from your data + auto-fetched sources. Unverified numbers are flagged."}
            </p>

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Company Name (Optional)"
                placeholder="e.g., Apple Inc."
                value={basics.companyName}
                onChange={(e) =>
                  setBasics((prev) => ({
                    ...prev,
                    companyName: e.target.value,
                  }))
                }
              />
              <Input
                label="Sector (Optional)"
                placeholder="e.g., Technology"
                value={basics.sector}
                onChange={(e) =>
                  setBasics((prev) => ({
                    ...prev,
                    sector: e.target.value,
                  }))
                }
              />
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* Step 2: Thesis + Catalysts + Valuation + Risks + Data + Constraints */}
        {/* ================================================================ */}
        {currentStep === "thesis" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Your Edge
              </h2>
              <p className="text-slate-400">
                Lock in your thesis, catalysts, valuation, and risks. Expand
                sections as needed. All optional.
              </p>
            </div>

            {/* Phase 2: Thesis */}
            <CollapsibleSection
              title="Investment Thesis"
              subtitle="Recommended"
              defaultOpen={true}
            >
              <TextArea
                label="Thesis Sentence"
                placeholder="Market is wrong because ___; it reprices when ___."
                value={thesis.thesis_sentence ?? ""}
                onChange={(e) =>
                  setThesis((prev) => ({
                    ...prev,
                    thesis_sentence: e.target.value,
                  }))
                }
                rows={2}
              />
              <div className="grid grid-cols-2 gap-4">
                <TextArea
                  label="Market Believes"
                  placeholder="What consensus currently thinks..."
                  value={thesis.market_believes ?? ""}
                  onChange={(e) =>
                    setThesis((prev) => ({
                      ...prev,
                      market_believes: e.target.value,
                    }))
                  }
                  rows={3}
                />
                <TextArea
                  label="We Believe"
                  placeholder="Our variant view..."
                  value={thesis.we_believe ?? ""}
                  onChange={(e) =>
                    setThesis((prev) => ({
                      ...prev,
                      we_believe: e.target.value,
                    }))
                  }
                  rows={3}
                />
              </div>

              {/* Pillars */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Thesis Pillars (2-5)
                </label>
                {(thesis.pillars ?? []).map((p, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 mb-2"
                  >
                    <span className="text-slate-300 text-sm flex-1 bg-slate-800 rounded px-3 py-1.5">
                      {p}
                    </span>
                    <button
                      type="button"
                      onClick={() => removePillar(i)}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                {(thesis.pillars?.length ?? 0) < 5 && (
                  <div className="flex gap-2">
                    <Input
                      placeholder="Add a thesis pillar..."
                      value={pillarDraft}
                      onChange={(e) => setPillarDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addPillar();
                        }
                      }}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={addPillar}
                      disabled={!pillarDraft.trim()}
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>

              {/* What Changes Mind */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  What Would Change My Mind (1-2)
                </label>
                {(thesis.what_changes_mind ?? []).map((w, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 mb-2"
                  >
                    <span className="text-slate-300 text-sm flex-1 bg-slate-800 rounded px-3 py-1.5">
                      {w}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeWcm(i)}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                {(thesis.what_changes_mind?.length ?? 0) < 2 && (
                  <div className="flex gap-2">
                    <Input
                      placeholder="Condition that invalidates the thesis..."
                      value={wcmDraft}
                      onChange={(e) => setWcmDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addWcm();
                        }
                      }}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={addWcm}
                      disabled={!wcmDraft.trim()}
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>
            </CollapsibleSection>

            {/* Phase 3: Catalysts */}
            <CollapsibleSection title="Catalysts" subtitle="Optional">
              <p className="text-xs text-slate-500">
                Add 3-6 catalysts with timing and mechanism.
              </p>
              {catalysts.map((cat, i) => (
                <div
                  key={i}
                  className="bg-slate-800/50 rounded-lg p-3 space-y-3"
                >
                  <div className="flex justify-between items-start">
                    <span className="text-xs text-slate-400 font-medium">
                      Catalyst {i + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeCatalyst(i)}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      placeholder="Catalyst name"
                      value={cat.name}
                      onChange={(e) =>
                        updateCatalyst(i, "name", e.target.value)
                      }
                    />
                    <Input
                      placeholder="Timing (e.g., Q2 2025)"
                      value={cat.timing_window ?? ""}
                      onChange={(e) =>
                        updateCatalyst(i, "timing_window", e.target.value)
                      }
                    />
                  </div>
                  <TextArea
                    placeholder="Mechanism: what changes and why market reacts"
                    value={cat.mechanism ?? ""}
                    onChange={(e) =>
                      updateCatalyst(i, "mechanism", e.target.value)
                    }
                    rows={2}
                  />
                </div>
              ))}
              {catalysts.length < 6 && (
                <Button variant="outline" size="sm" onClick={addCatalyst}>
                  <Plus className="w-4 h-4 mr-1" />
                  Add Catalyst
                </Button>
              )}
            </CollapsibleSection>

            {/* Phase 4: Valuation */}
            <CollapsibleSection title="Valuation Approach" subtitle="Optional">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Select Methods
                </label>
                <div className="flex flex-wrap gap-2">
                  {VALUATION_METHODS.map((m) => {
                    const selected = (valuationInput.methods ?? []).includes(
                      m.value,
                    );
                    return (
                      <button
                        key={m.value}
                        type="button"
                        onClick={() =>
                          setValuationInput((prev) => ({
                            ...prev,
                            methods: selected
                              ? (prev.methods ?? []).filter(
                                  (v) => v !== m.value,
                                )
                              : [...(prev.methods ?? []), m.value],
                          }))
                        }
                        className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                          selected
                            ? "bg-blue-900/30 border-blue-600 text-blue-400"
                            : "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600"
                        }`}
                      >
                        {m.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {(valuationInput.methods ?? []).includes("relative") && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Peer Tickers
                    </label>
                    <TickerInput
                      tickers={valuationInput.peer_tickers ?? []}
                      onTickersChange={(tickers) =>
                        setValuationInput((prev) => ({
                          ...prev,
                          peer_tickers: tickers,
                        }))
                      }
                      disabled={false}
                    />
                  </div>
                  <Input
                    label="Target Multiple Range"
                    placeholder="e.g., 15-18x EV/EBITDA"
                    value={valuationInput.target_multiple_range ?? ""}
                    onChange={(e) =>
                      setValuationInput((prev) => ({
                        ...prev,
                        target_multiple_range: e.target.value,
                      }))
                    }
                  />
                </div>
              )}

              {(valuationInput.methods ?? []).includes("dcf") && (
                <TextArea
                  label="DCF Assumptions"
                  placeholder="WACC, terminal growth, margin path..."
                  value={valuationInput.dcf_assumptions ?? ""}
                  onChange={(e) =>
                    setValuationInput((prev) => ({
                      ...prev,
                      dcf_assumptions: e.target.value,
                    }))
                  }
                  rows={3}
                />
              )}

              <Input
                label="Price Target (Optional)"
                placeholder="e.g., $150-170"
                value={valuationInput.price_target ?? ""}
                onChange={(e) =>
                  setValuationInput((prev) => ({
                    ...prev,
                    price_target: e.target.value,
                  }))
                }
              />
            </CollapsibleSection>

            {/* Phase 5: Risks */}
            <CollapsibleSection title="Risks & Underwriting" subtitle="Optional">
              {risks.map((r, i) => (
                <div
                  key={i}
                  className="bg-slate-800/50 rounded-lg p-3 space-y-3"
                >
                  <div className="flex justify-between items-start">
                    <span className="text-xs text-slate-400 font-medium">
                      Risk {i + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeRisk(i)}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <Input
                    placeholder="Risk description"
                    value={r.risk}
                    onChange={(e) => updateRisk(i, "risk", e.target.value)}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      placeholder="Leading indicator"
                      value={r.leading_indicator ?? ""}
                      onChange={(e) =>
                        updateRisk(i, "leading_indicator", e.target.value)
                      }
                    />
                    <Input
                      placeholder="Mitigant / hedge"
                      value={r.mitigant ?? ""}
                      onChange={(e) =>
                        updateRisk(i, "mitigant", e.target.value)
                      }
                    />
                  </div>
                </div>
              ))}
              {risks.length < 6 && (
                <Button variant="outline" size="sm" onClick={addRisk}>
                  <Plus className="w-4 h-4 mr-1" />
                  Add Risk
                </Button>
              )}
            </CollapsibleSection>

            {/* Phase 6: Data Blocks */}
            <CollapsibleSection title="Paste Data Blocks" subtitle="Optional">
              <p className="text-xs text-slate-500">
                Paste raw data to improve accuracy. The model will reference these
                instead of guessing.
              </p>
              <TextArea
                label="KPI Table"
                placeholder="ARR, NRR, churn, backlog, etc."
                value={dataBlocks.kpi_table ?? ""}
                onChange={(e) =>
                  setDataBlocks((prev) => ({
                    ...prev,
                    kpi_table: e.target.value,
                  }))
                }
                rows={3}
              />
              <TextArea
                label="Segment Mix"
                placeholder="Revenue by segment..."
                value={dataBlocks.segment_mix ?? ""}
                onChange={(e) =>
                  setDataBlocks((prev) => ({
                    ...prev,
                    segment_mix: e.target.value,
                  }))
                }
                rows={3}
              />
              <TextArea
                label="Debt Maturities"
                placeholder="Maturity schedule..."
                value={dataBlocks.debt_maturities ?? ""}
                onChange={(e) =>
                  setDataBlocks((prev) => ({
                    ...prev,
                    debt_maturities: e.target.value,
                  }))
                }
                rows={3}
              />
              <TextArea
                label="Ownership / Governance Notes"
                placeholder="Major holders, insider activity..."
                value={dataBlocks.ownership_notes ?? ""}
                onChange={(e) =>
                  setDataBlocks((prev) => ({
                    ...prev,
                    ownership_notes: e.target.value,
                  }))
                }
                rows={3}
              />
              <TextArea
                label="Filing Excerpts"
                placeholder="10-K/10-Q excerpts, earnings call quotes..."
                value={dataBlocks.filing_excerpts ?? ""}
                onChange={(e) =>
                  setDataBlocks((prev) => ({
                    ...prev,
                    filing_excerpts: e.target.value,
                  }))
                }
                rows={3}
              />
            </CollapsibleSection>

            {/* Phase 7: Constraints */}
            <CollapsibleSection title="Fund Constraints" subtitle="Optional">
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Liquidity Floor"
                  placeholder="e.g., $50M daily volume"
                  value={userConstraints.liquidity_floor ?? ""}
                  onChange={(e) =>
                    setUserConstraints((prev) => ({
                      ...prev,
                      liquidity_floor: e.target.value,
                    }))
                  }
                />
                <Input
                  label="Leverage Ceiling"
                  placeholder="e.g., 4x Net Debt/EBITDA"
                  value={userConstraints.leverage_ceiling ?? ""}
                  onChange={(e) =>
                    setUserConstraints((prev) => ({
                      ...prev,
                      leverage_ceiling: e.target.value,
                    }))
                  }
                />
              </div>
              <TextArea
                label="ESG Constraints"
                placeholder="ESG screens or exclusion criteria..."
                value={userConstraints.esg_constraints ?? ""}
                onChange={(e) =>
                  setUserConstraints((prev) => ({
                    ...prev,
                    esg_constraints: e.target.value,
                  }))
                }
                rows={2}
              />
              <TextArea
                label="Portfolio Context"
                placeholder="Fund strategy, sector allocation context..."
                value={fundConstraints.portfolio_context ?? ""}
                onChange={(e) =>
                  setFundConstraints((prev) => ({
                    ...prev,
                    portfolio_context: e.target.value,
                  }))
                }
                rows={2}
              />
            </CollapsibleSection>
          </div>
        )}

        {/* ================================================================ */}
        {/* Step 3: Comparables */}
        {/* ================================================================ */}
        {currentStep === "comparables" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                <Users className="w-6 h-6 inline mr-2" />
                Comparable Companies
              </h2>
              <p className="text-slate-400">
                Select peer companies for relative valuation analysis. Leave
                empty to use auto-selected defaults based on sector.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Peer Company Tickers
              </label>
              <TickerInput
                tickers={compTickers}
                onTickersChange={setCompTickers}
                disabled={false}
              />
              <p className="text-xs text-slate-500 mt-2">
                Enter comparable company tickers (e.g., AAPL, MSFT, GOOGL, META,
                NVDA).
              </p>
            </div>

            {compTickers.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm text-slate-300">
                    <input
                      type="checkbox"
                      checked={compsShowPerf}
                      onChange={(e) => setCompsShowPerf(e.target.checked)}
                      className="rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-900"
                    />
                    Show Performance
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-300">
                    <input
                      type="checkbox"
                      checked={compsShowDcf}
                      onChange={(e) => setCompsShowDcf(e.target.checked)}
                      className="rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-900"
                    />
                    Show DCF
                  </label>
                </div>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (!showCompsPreview) {
                      const params: FetchRelativeParams = {
                        symbols: [basics.ticker, ...compTickers],
                        fields: [...SNAPSHOT_FIELDS],
                      };
                      if (compsShowPerf) {
                        params.perf = ["return", "volatility"];
                        params.perfPeriod = "3mo";
                      }
                      if (compsShowDcf) {
                        params.dcf = true;
                      }
                      setPreviewParams(params);
                    }
                    setShowCompsPreview(!showCompsPreview);
                  }}
                >
                  {showCompsPreview ? "Hide" : "Show"} Preview
                  <ChevronRight
                    className={`w-4 h-4 ml-2 transition-transform ${
                      showCompsPreview ? "rotate-90" : ""
                    }`}
                  />
                </Button>
              </div>
            )}

            {showCompsPreview && compsPreview && (
              <Card padding="none" className="overflow-hidden">
                <div className="p-4 border-b border-slate-700">
                  <h3 className="text-sm font-medium text-white">
                    Comparison Preview
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    This is how your comparables will appear in the deck
                  </p>
                </div>
                <RelativeTable
                  data={compsPreview}
                  visibleFields={[...SNAPSHOT_FIELDS]}
                  visiblePerfMetrics={
                    compsShowPerf ? ["return", "volatility"] : []
                  }
                  showPerf={compsShowPerf}
                  showDcf={compsShowDcf}
                  signalSettings={signalSettings}
                />
              </Card>
            )}

            {showCompsPreview && compsLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                <span className="ml-2 text-slate-400">Loading preview...</span>
              </div>
            )}

            <Alert variant="info" title="Auto-Selection">
              If you don't specify comparables, the system will automatically
              select peer companies based on the sector.
            </Alert>
          </div>
        )}

        {/* ================================================================ */}
        {/* Step 4: Sections */}
        {/* ================================================================ */}
        {currentStep === "sections" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Select Sections
              </h2>
              <p className="text-slate-400">
                Choose which sections to include in your pitch deck.
              </p>
            </div>

            {sectionsLoading && <CardSkeleton count={6} />}

            {sectionsError && (
              <Alert variant="error" title="Failed to Load Sections">
                <div className="space-y-3">
                  <p className="text-sm">
                    {sectionsError instanceof Error
                      ? sectionsError.message
                      : "Unable to fetch available sections."}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => window.location.reload()}
                      className="text-white"
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      Reload Page
                    </Button>
                  </div>
                </div>
              </Alert>
            )}

            {availableSections && (
              <div className="grid gap-3">
                {availableSections.map((section) => (
                  <SectionCheckbox
                    key={section.id}
                    section={section}
                    checked={config.sections.includes(section.id)}
                    onChange={() => toggleSection(section.id)}
                  />
                ))}
              </div>
            )}

            {availableSections && missingSectionCount > 0 && (
              <Alert variant="warning" title="Backend Section Mismatch">
                <p className="text-sm">
                  Backend currently exposes {availableSections.length}/
                  {EXPECTED_SECTION_COUNT} expected sections.
                </p>
              </Alert>
            )}

            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setConfig((prev) => ({
                    ...prev,
                    sections: availableSections?.map((s) => s.id) || [],
                  }))
                }
              >
                Select All
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setConfig((prev) => ({
                    ...prev,
                    sections: (() => {
                      const defaults =
                        availableSections
                          ?.filter((s) => s.default)
                          .map((s) => s.id) || [];
                      return defaults.length > 0
                        ? defaults
                        : availableSections?.map((s) => s.id) || [];
                    })(),
                  }))
                }
              >
                Reset to Defaults
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfig((prev) => ({ ...prev, sections: [] }))}
              >
                Clear All
              </Button>
            </div>

            {/* AI Model & Reasoning */}
            <div className="pt-2">
              <p className="text-xs text-slate-400 mb-1.5">
                AI Model & Reasoning
              </p>
              <ModelReasoningBar
                config={config}
                setConfig={setConfig}
                tier={tier}
              />
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* Step 5: Generate */}
        {/* ================================================================ */}
        {currentStep === "generate" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Generate Deck
              </h2>
              <p className="text-slate-400">
                Review your settings and generate the pitch deck.
              </p>
            </div>

            {/* Summary */}
            <div className="bg-slate-800 rounded-lg p-4 space-y-3">
              <div className="flex justify-between">
                <span className="text-slate-400">Ticker:</span>
                <span className="text-white font-medium">{basics.ticker}</span>
              </div>
              {basics.position && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Position:</span>
                  <Badge
                    variant={
                      basics.position === "long" ? "success" : "warning"
                    }
                  >
                    {basics.position.toUpperCase()}
                  </Badge>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-400">Data Trust:</span>
                <span className="text-white text-sm">
                  {basics.dataTrustMode === "user_only"
                    ? "User-Only"
                    : basics.dataTrustMode === "narrative_only"
                      ? "Narrative"
                      : "User + Auto"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Sections:</span>
                <span className="text-white">
                  {config.sections.length} selected
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Model:</span>
                <span className="text-white">
                  {selectedModel?.label || config.model || "Unknown"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Provider:</span>
                <span className="text-white">
                  {PROVIDER_LABELS[config.provider]}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Quality:</span>
                <Badge
                  variant={
                    config.quality === "high"
                      ? "success"
                      : config.quality === "medium"
                        ? "info"
                        : "warning"
                  }
                >
                  {qualityLabel}
                </Badge>
              </div>
              {thesis.thesis_sentence?.trim() && (
                <div className="pt-2 border-t border-slate-700">
                  <span className="text-slate-400 text-sm">Thesis:</span>
                  <p className="text-white text-sm mt-1">
                    {thesis.thesis_sentence}
                  </p>
                </div>
              )}
              {catalysts.filter((c) => c.name.trim()).length > 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Catalysts:</span>
                  <span className="text-white">
                    {catalysts.filter((c) => c.name.trim()).length} defined
                  </span>
                </div>
              )}
              {risks.filter((r) => r.risk.trim()).length > 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Risks:</span>
                  <span className="text-white">
                    {risks.filter((r) => r.risk.trim()).length} defined
                  </span>
                </div>
              )}
            </div>

            {/* Generation Progress */}
            {generateMutation.isPending && (
              <div className="text-center py-8">
                <Loader2 className="w-12 h-12 animate-spin text-blue-500 mx-auto" />
                <p className="mt-4 text-white font-medium">
                  Generating your pitch deck...
                </p>
                <p className="text-slate-400 text-sm mt-1">
                  This may take a minute depending on the number of sections.
                </p>
              </div>
            )}

            {/* Error State */}
            {generateMutation.isError && (
              <Alert variant="error" title="Generation Failed">
                <div className="space-y-3">
                  <p className="text-sm">
                    {generateMutation.error instanceof Error
                      ? generateMutation.error.message
                      : "An unexpected error occurred during deck generation."}{" "}
                    This could be due to API limits or connectivity issues.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleGenerate}
                      className="text-white"
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      Retry Generation
                    </Button>
                    <Button variant="ghost" size="sm" onClick={goBack}>
                      Go Back
                    </Button>
                  </div>
                </div>
              </Alert>
            )}

            {/* Success State */}
            {generatedDeck && (
              <Alert variant="success" title="Deck Generated Successfully!">
                <p>
                  Generated{" "}
                  {(generatedDeck.results || generatedDeck.sections)?.length ||
                    0}{" "}
                  sections for {generatedDeck.company_name} (
                  {generatedDeck.ticker})
                </p>
                {generatedDeck.warnings &&
                  generatedDeck.warnings.length > 0 && (
                    <div className="mt-2 flex items-start gap-2 text-yellow-400">
                      <AlertTriangle className="w-4 h-4 mt-0.5" />
                      <span className="text-sm">
                        {generatedDeck.warnings.join(", ")}
                      </span>
                    </div>
                  )}
              </Alert>
            )}

            {/* Generate Button */}
            {!generatedDeck && !generateMutation.isPending && (
              <Button
                onClick={handleGenerate}
                size="lg"
                className="w-full"
                disabled={generateMutation.isPending || atDeckLimit}
              >
                Generate Pitch Deck
              </Button>
            )}
          </div>
        )}

        {/* ================================================================ */}
        {/* Step 6: Save */}
        {/* ================================================================ */}
        {currentStep === "save" && generatedDeck && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Deck Ready!
              </h2>
              <p className="text-slate-400">
                Your pitch deck has been generated and saved.
              </p>
            </div>

            <div className="bg-slate-800 rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-white">
                  {generatedDeck.company_name}
                </h3>
                <Badge>{generatedDeck.ticker}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-400">Sections:</span>
                  <span className="ml-2 text-white">
                    {(generatedDeck.results || generatedDeck.sections)
                      ?.length || 0}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Provider:</span>
                  <span className="ml-2 text-white">
                    {generatedDeck.provider_used?.provider}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Model:</span>
                  <span className="ml-2 text-white">
                    {generatedDeck.provider_used?.model}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Generated:</span>
                  <span className="ml-2 text-white">
                    {new Date(generatedDeck.generated_at).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-medium text-slate-300">
                Generated Sections:
              </h4>
              <div className="grid gap-2">
                {(generatedDeck.results || generatedDeck.sections || []).map(
                  (section) => (
                    <div
                      key={section.section_id}
                      className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg"
                    >
                      <span className="text-white">{section.section_name}</span>
                      <span className="text-slate-400 text-sm">
                        {section.slides.length} slide
                        {section.slides.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                  ),
                )}
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Navigation Buttons */}
      <div className="flex justify-between items-center">
        <Button
          variant="outline"
          onClick={goBack}
          disabled={!canGoBack}
          className={!canGoBack ? "invisible" : ""}
        >
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>

        {/* Save Draft button */}
        {(currentStep === "basics" ||
          currentStep === "thesis" ||
          currentStep === "comparables" ||
          currentStep === "sections") &&
          draft && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                alert("Draft saved! You can return to this draft later.");
              }}
            >
              Save Draft
            </Button>
          )}

        {currentStep === "basics" && (
          <Button onClick={handleBasicsNext} disabled={!isStepValid()}>
            Next
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        )}

        {currentStep === "thesis" && (
          <Button onClick={handleThesisNext}>
            Next
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        )}

        {(currentStep === "comparables" || currentStep === "sections") && (
          <Button onClick={handleConfigNext} disabled={!isStepValid()}>
            Next
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        )}

        {currentStep === "generate" && generatedDeck && (
          <Button onClick={goNext}>
            Continue
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        )}

        {currentStep === "save" && (
          <Button onClick={handleSave}>View Deck</Button>
        )}
      </div>
    </div>
  );
}

// Section checkbox component
function SectionCheckbox({
  section,
  checked,
  onChange,
}: {
  section: Section;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className={`flex items-start p-4 rounded-lg border cursor-pointer transition-colors ${
        checked
          ? "bg-blue-900/20 border-blue-700"
          : "bg-slate-800/50 border-slate-700 hover:border-slate-600"
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="mt-1 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-900"
      />
      <div className="ml-3">
        <div className="flex items-center gap-2">
          <span className="text-white font-medium">{section.name}</span>
          {section.default && (
            <Badge variant="info" className="text-xs">
              Default
            </Badge>
          )}
        </div>
        <p className="text-slate-400 text-sm mt-1">{section.description}</p>
      </div>
    </label>
  );
}
