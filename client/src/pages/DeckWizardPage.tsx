import { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import {
  Button,
  Card,
  Input,
  TextArea,
  Select,
  Alert,
  Badge,
} from "../components/ui";
import {
  fetchSections,
  generateDeck,
  type Section,
  type GenerateDeckResponse,
} from "../api/deckApi";
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

type WizardStep = "basics" | "sections" | "provider" | "generate" | "save";

const STEPS: { id: WizardStep; label: string }[] = [
  { id: "basics", label: "Basics" },
  { id: "sections", label: "Sections" },
  { id: "provider", label: "Provider" },
  { id: "generate", label: "Generate" },
  { id: "save", label: "Save" },
];

export default function DeckWizardPage() {
  const navigate = useNavigate();
  const location = useLocation();

  // Get pre-filled ticker from navigation state
  const initialTicker =
    (location.state as { ticker?: string } | null)?.ticker || "";

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

  // Generated content
  const [generatedDeck, setGeneratedDeck] =
    useState<GenerateDeckResponse | null>(null);

  // Fetch sections
  const {
    data: availableSections,
    isLoading: sectionsLoading,
    error: sectionsError,
  } = useQuery({
    queryKey: ["sections"],
    queryFn: fetchSections,
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

  // Generate deck mutation
  const generateMutation = useMutation({
    mutationFn: generateDeck,
    onMutate: () => {
      if (draft) {
        markDraftGenerating(draft.id);
      }
    },
    onSuccess: (data) => {
      setGeneratedDeck(data);
      if (draft) {
        saveDraftContent(draft.id, data);
        setDraft({ ...draft, status: "complete", generatedContent: data });
        // Navigate directly to deck view after successful generation
        navigate(`/deck/${draft.id}`);
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
      reasoning_level: config.quality,
      include_comps: true,
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
      {/* Progress Steps */}
      <nav className="mb-8">
        <ol className="flex items-center justify-between">
          {STEPS.map((step, index) => {
            const isActive = step.id === currentStep;
            const isCompleted = index < currentStepIndex;

            return (
              <li key={step.id} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors ${
                      isCompleted
                        ? "bg-blue-600 border-blue-600 text-white"
                        : isActive
                          ? "border-blue-500 text-blue-500 bg-slate-900"
                          : "border-slate-700 text-slate-500 bg-slate-900"
                    }`}
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
                </div>
                {index < STEPS.length - 1 && (
                  <div
                    className={`w-full h-0.5 mx-2 ${
                      isCompleted ? "bg-blue-600" : "bg-slate-700"
                    }`}
                    style={{ minWidth: "40px" }}
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

        {/* Step 2: Sections */}
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

            {sectionsLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                <span className="ml-2 text-slate-400">Loading sections...</span>
              </div>
            )}

            {sectionsError && (
              <Alert variant="error" title="Failed to load sections">
                {sectionsError instanceof Error
                  ? sectionsError.message
                  : "Unable to fetch available sections"}
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

        {/* Step 3: Provider */}
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

        {/* Step 4: Generate */}
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
                <div className="space-y-2">
                  <p>
                    {generateMutation.error instanceof Error
                      ? generateMutation.error.message
                      : "An error occurred during generation"}
                  </p>
                  <Button variant="outline" size="sm" onClick={handleGenerate}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Retry
                  </Button>
                </div>
              </Alert>
            )}

            {/* Success State */}
            {generatedDeck && generatedDeck.metadata && (
              <Alert variant="success" title="Deck Generated Successfully!">
                <p>
                  Generated {generatedDeck.sections.length} sections for{" "}
                  {generatedDeck.metadata.company_name} (
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
                disabled={generateMutation.isPending}
              >
                Generate Pitch Deck
              </Button>
            )}
          </div>
        )}

        {/* Step 5: Save */}
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
                    {generatedDeck.sections.length}
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
                {generatedDeck.sections.map((section) => (
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
                ))}
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Navigation Buttons */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={goBack}
          disabled={!canGoBack}
          className={!canGoBack ? "invisible" : ""}
        >
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>

        {currentStep === "basics" && (
          <Button onClick={handleBasicsNext} disabled={!isStepValid()}>
            Next
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        )}

        {(currentStep === "sections" || currentStep === "provider") && (
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
