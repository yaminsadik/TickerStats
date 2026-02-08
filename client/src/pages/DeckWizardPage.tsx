import { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import Breadcrumbs, { BreadcrumbItem } from "../components/Breadcrumbs";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Users,
} from "lucide-react";
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
  type Section,
  type GenerateDeckResponse,
} from "../api/deckApi";
import { queryKeys } from "../lib/queryKeys";
import { sectionSchema } from "../schemas/deck";
import { useSaveDeck } from "../queries/useDeckQueries";
import { z } from "zod";
import {
  createDraft,
  updateDraftBasics,
  updateDraftConfig,
  saveDraftContent,
  markDraftGenerating,
  markDraftError,
  type DeckDraft,
  type DeckDraftBasics,
  type DeckDraftConfig,
  type FundConstraints,
} from "../stores/deckDraft";

type WizardStep =
  | "basics"
  | "comparables"
  | "sections"
  | "provider"
  | "generate"
  | "save";

const STEPS: { id: WizardStep; label: string }[] = [
  { id: "basics", label: "Basics" },
  { id: "comparables", label: "Comparables" },
  { id: "sections", label: "Sections" },
  { id: "provider", label: "Provider" },
  { id: "generate", label: "Generate" },
  { id: "save", label: "Save" },
];

export default function DeckWizardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { authenticatedFetch } = useAuthenticatedFetch();
  const { tier, deckCount, deckLimit } = useUserProfile();
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

  // Form state for basics
  const [basics, setBasics] = useState<DeckDraftBasics>({
    ticker: initialTicker,
    companyName: "",
    sector: "",
    companyContext: "",
    investmentThesis: "",
  });

  // Fund constraints state
  const [fundConstraints, setFundConstraints] = useState<FundConstraints>({
    time_horizon: "12-24 months",
    risk_profile: "moderate",
    portfolio_context: "",
    style: "student investment fund pitch deck",
  });

  // Config state
  const [config, setConfig] = useState<DeckDraftConfig>({
    sections: [],
    provider: "openai",
    quality: "medium",
  });

  // Comparable companies state
  const [compTickers, setCompTickers] = useState<string[]>(initialComparables);
  const [showCompsPreview, setShowCompsPreview] = useState(false);
  const [compsShowPerf, setCompsShowPerf] = useState(false);
  const [compsShowDcf, setCompsShowDcf] = useState(false);

  // Preview query for comparables (only fetch when preview is requested)
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
    queryKey: queryKeys.sections,
    queryFn: async () => {
      const raw = await fetchSections();
      return z.array(sectionSchema).parse(raw) as Section[];
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Set default sections when loaded
  useEffect(() => {
    if (availableSections && config.sections.length === 0) {
      const defaultSections = availableSections
        .filter((s) => s.default)
        .map((s) => s.id);
      setConfig((prev) => ({ ...prev, sections: defaultSections }));
    }
  }, [availableSections, config.sections.length]);

  // Save deck to DB mutation
  const saveDeckMutation = useSaveDeck();

  // Generate deck mutation
  const generateMutation = useMutation({
    mutationFn: (payload: import("../api/deckApi").GenerateDeckRequest) =>
      generateDeckAuthed(authenticatedFetch, payload),
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

        // Persist to DB if authenticated, then navigate to DB-backed view
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
          // Fallback to local draft view if DB save fails
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
        // Only ticker is required now - company name and sector auto-fetch from backend
        return basics.ticker.trim().length > 0;
      case "comparables":
        // Comparables are optional - always valid
        return true;
      case "sections":
        return config.sections.length > 0;
      case "provider":
        return true;
      case "generate":
        return generatedDeck !== null;
      case "save":
        return true;
      default:
        return false;
    }
  }, [
    currentStep,
    basics.ticker,
    basics.companyName,
    basics.sector,
    config.sections.length,
    generatedDeck,
  ]);

  // Create draft when moving past basics
  const handleBasicsNext = () => {
    if (!isStepValid()) return;

    if (!draft) {
      const newDraft = createDraft(basics, config);
      setDraft(newDraft);
    } else {
      updateDraftBasics(draft.id, basics);
    }
    goNext();
  };

  // Save config when moving past config steps
  const handleConfigNext = () => {
    if (!isStepValid()) return;

    if (draft) {
      updateDraftConfig(draft.id, config);
    }
    goNext();
  };

  // Generate deck
  const handleGenerate = () => {
    if (atDeckLimit) {
      setLimitError(
        `You have reached your monthly deck limit (${deckCount}/${deckLimit}). Upgrade to Pro for more.`,
      );
      return;
    }
    setLimitError(null);
    if (draft) {
      updateDraftConfig(draft.id, config);
    }

    generateMutation.mutate({
      ticker: basics.ticker,
      ...(basics.companyName.trim() && { company_name: basics.companyName }),
      ...(basics.sector.trim() && { sector: basics.sector }),
      fund_constraints: fundConstraints,
      sections: config.sections.length > 0 ? config.sections : undefined,
      provider: config.provider,
      plan_tier: tier,
      model_mode: "auto",
      analysis_depth: config.quality,
      reasoning_level: config.quality,
      include_comps: true,
      ...(compTickers.length > 0 && { comp_tickers: compTickers }),
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
                    className={`mt-2 text-sm font-medium ${
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
                    style={{ minWidth: "40px" }}
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
        {/* Step 1: Basics */}
        {currentStep === "basics" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Basic Information
              </h2>
              <p className="text-slate-400">
                Enter the ticker symbol. Company name and sector will be
                auto-fetched if not provided.
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
              helperText="Enter the stock ticker symbol for the company"
            />

            <Input
              label="Company Name (Optional)"
              placeholder="e.g., Apple Inc., Microsoft Corporation"
              value={basics.companyName}
              onChange={(e) =>
                setBasics((prev) => ({
                  ...prev,
                  companyName: e.target.value,
                }))
              }
              helperText="Leave blank to auto-fetch from ticker"
            />

            <Input
              label="Sector (Optional)"
              placeholder="e.g., Technology, Healthcare, Finance"
              value={basics.sector}
              onChange={(e) =>
                setBasics((prev) => ({
                  ...prev,
                  sector: e.target.value,
                }))
              }
              helperText="Leave blank to auto-fetch from ticker"
            />

            <Select
              label="Investment Time Horizon"
              value={fundConstraints.time_horizon}
              onChange={(e) =>
                setFundConstraints((prev) => ({
                  ...prev,
                  time_horizon: e.target.value,
                }))
              }
              options={[
                { value: "6-12 months", label: "6-12 months" },
                { value: "12-24 months", label: "12-24 months (Recommended)" },
                { value: "2-5 years", label: "2-5 years" },
                { value: "5+ years", label: "5+ years" },
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
                { value: "moderate", label: "Moderate (Recommended)" },
                { value: "aggressive", label: "Aggressive" },
              ]}
            />

            <TextArea
              label="Company Context (Optional)"
              placeholder="Additional context about the company or industry..."
              value={basics.companyContext || ""}
              onChange={(e) =>
                setBasics((prev) => ({
                  ...prev,
                  companyContext: e.target.value,
                }))
              }
              helperText="Provide any specific context to tailor the analysis"
            />

            <TextArea
              label="Investment Thesis (Optional)"
              placeholder="Your investment thesis or key points to highlight..."
              value={basics.investmentThesis || ""}
              onChange={(e) =>
                setBasics((prev) => ({
                  ...prev,
                  investmentThesis: e.target.value,
                }))
              }
              helperText="Outline the main investment thesis you want to support"
            />

            <TextArea
              label="Portfolio Context (Optional)"
              placeholder="Context about your portfolio or fund strategy..."
              value={fundConstraints.portfolio_context || ""}
              onChange={(e) =>
                setFundConstraints((prev) => ({
                  ...prev,
                  portfolio_context: e.target.value,
                }))
              }
              helperText="Provide context about your fund or portfolio strategy"
            />
          </div>
        )}

        {/* Step 2: Comparables */}
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

            {/* Ticker Input */}
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
                NVDA). Add as many peers as needed for comprehensive analysis.
              </p>
            </div>

            {/* Preview Options */}
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

            {/* Preview Table */}
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

            {/* Loading State */}
            {showCompsPreview && compsLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                <span className="ml-2 text-slate-400">Loading preview...</span>
              </div>
            )}

            {/* Info Alert */}
            <Alert variant="info" title="Auto-Selection">
              If you don't specify comparables, the system will automatically
              select peer companies based on the sector.
            </Alert>
          </div>
        )}

        {/* Step 3: Sections */}
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
                      : "Unable to fetch available sections. This might be a temporary network issue."}
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
                  <p className="text-xs text-slate-400">
                    If the problem persists, please{" "}
                    <a
                      href="/contact"
                      className="text-blue-400 hover:underline"
                    >
                      contact support
                    </a>
                  </p>
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
                    sections:
                      availableSections
                        ?.filter((s) => s.default)
                        .map((s) => s.id) || [],
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
          </div>
        )}

        {/* Step 4: Provider */}
        {currentStep === "provider" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                AI Provider & Quality
              </h2>
              <p className="text-slate-400">
                Select the AI provider and output quality level.
              </p>
            </div>

            <Select
              label="AI Provider"
              value={config.provider}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  provider: e.target.value as "openai" | "gemini",
                }))
              }
              options={[
                { value: "openai", label: "OpenAI (GPT-5)" },
                { value: "gemini", label: "Google Gemini 3 Flash" },
              ]}
            />

            <Select
              label="Quality Level"
              value={config.quality}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  quality: e.target.value as "low" | "medium" | "high",
                }))
              }
              options={[
                { value: "low", label: "Low (Fastest, budget-friendly)" },
                { value: "medium", label: "Medium (Balanced)" },
                { value: "high", label: "High (Best quality, slower)" },
              ]}
            />

            <Alert variant="info" title="Pricing Note">
              Higher quality settings use more advanced models and may take
              longer to generate.
            </Alert>
          </div>
        )}

        {/* Step 5: Generate */}
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
              <div className="flex justify-between">
                <span className="text-slate-400">Sections:</span>
                <span className="text-white">
                  {config.sections.length} selected
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Provider:</span>
                <span className="text-white">
                  {config.provider === "openai" ? "OpenAI" : "Gemini"}
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
                  {config.quality}
                </Badge>
              </div>
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
                  <p className="text-xs text-slate-400">
                    💡 <strong>Tip:</strong> Try reducing the number of sections
                    or changing the AI provider
                  </p>
                </div>
              </Alert>
            )}

            {/* Success State */}
            {generatedDeck && generatedDeck.metadata && (
              <Alert variant="success" title="Deck Generated Successfully!">
                <p>
                  Generated{" "}
                  {(generatedDeck.sections || generatedDeck.results)?.length ||
                    0}{" "}
                  sections for {generatedDeck.metadata.company_name} (
                  {generatedDeck.metadata.ticker})
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

        {/* Step 6: Save */}
        {currentStep === "save" && generatedDeck && generatedDeck.metadata && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Deck Ready!
              </h2>
              <p className="text-slate-400">
                Your pitch deck has been generated and saved as a draft.
              </p>
            </div>

            {/* Preview Summary */}
            <div className="bg-slate-800 rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-white">
                  {generatedDeck.metadata.company_name}
                </h3>
                <Badge>{generatedDeck.metadata.ticker}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-400">Sections:</span>
                  <span className="ml-2 text-white">
                    {(generatedDeck.sections || generatedDeck.results)
                      ?.length || 0}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Provider:</span>
                  <span className="ml-2 text-white">
                    {generatedDeck.metadata.provider}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Model:</span>
                  <span className="ml-2 text-white">
                    {generatedDeck.metadata.model}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Generated:</span>
                  <span className="ml-2 text-white">
                    {new Date(
                      generatedDeck.metadata.generated_at,
                    ).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Section List */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-slate-300">
                Generated Sections:
              </h4>
              <div className="grid gap-2">
                {(generatedDeck.sections || generatedDeck.results || []).map(
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

        {/* Save Draft button - only show during active editing steps */}
        {(currentStep === "basics" ||
          currentStep === "comparables" ||
          currentStep === "sections" ||
          currentStep === "provider") &&
          draft && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                // Save current progress to localStorage (already handled by draft store)
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

        {(currentStep === "comparables" ||
          currentStep === "sections" ||
          currentStep === "provider") && (
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
