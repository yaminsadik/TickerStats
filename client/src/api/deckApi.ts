import { API_BASE } from '../config/apiBase';

interface ApiError {
  message?: string;
  error?: string;
  code?: string;
  request_id?: string;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return String(error);
}

function isLikelyNetworkError(error: unknown): boolean {
  const message = getErrorMessage(error).toLowerCase();
  return (
    error instanceof TypeError ||
    message.includes('failed to fetch') ||
    message.includes('networkerror') ||
    message.includes('load failed')
  );
}

function buildNetworkError(url: string, error: unknown): Error {
  return new Error(
    `Network error while contacting ${url}. ` +
      'Check VITE_API_BASE/VITE_API_BASE_URL, backend reachability, HTTPS, and ALLOWED_ORIGINS. ' +
      `Original error: ${getErrorMessage(error)}`
  );
}

async function requestJson(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    throw buildNetworkError(url, error);
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      message: `HTTP ${response.status}: ${response.statusText}`,
    }));
    const message = error.message || error.error || `HTTP ${response.status}: ${response.statusText}`;
    const requestId = error.request_id ? ` (request_id: ${error.request_id})` : '';
    throw new Error(`${message}${requestId}`);
  }
  return response.json();
}

// ----- Types -----

export interface Section {
  id: string;
  name: string;
  description: string;
  default: boolean;
}

export interface SectionsResponse {
  sections: Section[];
}

const CANONICAL_SECTION_ORDER = [
  "company_snapshot",
  "overview",
  "history",
  "business_model_segments",
  "industry_competitive_landscape",
  "historical_performance_current_setup",
  "management_ownership_governance",
  "capital_structure_financial_health",
  "swot",
  "key_drivers_kpis",
  "sector_invariants",
  "investment_thesis_variant_view",
  "risks_underwriting",
  "valuation_summary",
  "investment_thesis",
  "catalysts_timeline",
  "valuation",
] as const;

const CANONICAL_SECTION_METADATA: Record<
  (typeof CANONICAL_SECTION_ORDER)[number],
  Omit<Section, "id"> & { requires_user_input?: boolean }
> = {
  company_snapshot: {
    name: "Company Snapshot",
    description:
      "Institutional-quality identity slide with positioning, segments, money model, customers, footprint, and proof points",
    default: true,
  },
  overview: {
    name: "Company Overview",
    description:
      "Core business, why now thesis, and near/medium-term catalysts",
    default: true,
  },
  history: {
    name: "Company History (Draft)",
    description:
      "Key company milestones and timeline context (requires verification)",
    default: true,
  },
  business_model_segments: {
    name: "Business Model & Segments",
    description:
      "What they sell, who they sell to, revenue flow, segment breakdown with mix, and unit economics where disclosed",
    default: true,
  },
  industry_competitive_landscape: {
    name: "Industry & Competitive Landscape",
    description:
      "Market definition, sizing, growth drivers, competitive set, positioning, moat drivers, and Porter's Five Forces",
    default: true,
  },
  historical_performance_current_setup: {
    name: "Historical Performance & Current Setup",
    description:
      "3-5 year revenue, profitability, and cash flow trends plus current stock vs benchmark and/or valuation rerating context with recent event timeline",
    default: true,
  },
  management_ownership_governance: {
    name: "Management & Ownership",
    description:
      "Management track record and incentives, ownership overview, and governance flags",
    default: true,
  },
  capital_structure_financial_health: {
    name: "Capital Structure & Financial Health",
    description:
      "Leverage, maturities, liquidity, and share-count/dilution dynamics with risk takeaways",
    default: true,
  },
  swot: {
    name: "SWOT Analysis",
    description:
      "Internal strengths/weaknesses and external opportunities/threats with investor relevance",
    default: true,
  },
  key_drivers_kpis: {
    name: "Key Drivers & KPIs",
    description:
      "Value-driving metrics, definitions, and where they are disclosed",
    default: false,
  },
  sector_invariants: {
    name: "Sector Invariants",
    description:
      "Sector-specific value drivers, dependencies, and failure modes",
    default: false,
  },
  investment_thesis: {
    name: "Generated Thesis Framework",
    description:
      "AI-assisted thesis, market consensus vs variant view, and supporting pillars",
    default: false,
    requires_user_input: true,
  },
  investment_thesis_variant_view: {
    name: "User Thesis & Variant View",
    description:
      "Strictly uses the user's thesis sentence, market vs. we believe inputs, pillars, and flip conditions",
    default: false,
    requires_user_input: true,
  },
  risks_underwriting: {
    name: "Risks & Underwriting",
    description:
      "Ranked user-provided risks with leading indicators, mitigants, and thesis break conditions",
    default: false,
    requires_user_input: true,
  },
  valuation_summary: {
    name: "Valuation Summary",
    description:
      "Deterministic summary of selected valuation methods, peer set, user targets, and DCF output",
    default: false,
    requires_user_input: true,
  },
  catalysts_timeline: {
    name: "Catalysts & Timeline",
    description:
      "Specific catalysts with timing windows, mechanisms, and evidence",
    default: false,
    requires_user_input: true,
  },
  valuation: {
    name: "Valuation",
    description:
      "Valuation framework with user-selected methods, comparables, and price target",
    default: false,
    requires_user_input: true,
  },
};

export function normalizeAvailableSections(sections: Section[]): Section[] {
  const fromApi = new Map(sections.map((section) => [section.id, section]));

  return CANONICAL_SECTION_ORDER.flatMap((sectionId) => {
    const apiSection = fromApi.get(sectionId);
    if (!apiSection) return [];
    const canonical = CANONICAL_SECTION_METADATA[sectionId];

    return [
      {
        id: sectionId,
        name: canonical.name,
        description: canonical.description,
        // Allow server to override defaults if provided.
        default: apiSection.default ?? canonical.default,
      },
    ];
  });
}

export interface BulletPoint {
  text: string;
  source_needed: boolean;
}

export interface Slide {
  title: string;
  bullets: BulletPoint[];
  speaker_notes?: string;
}

export interface GeneratedSection {
  section_id: string;
  section_name: string;
  slides: Slide[];
  citations?: string[];
}

export interface DeckMetadata {
  ticker: string;
  company_name: string;
  generated_at: string;
  provider: string;
  model: string;
}

export interface GenerationError {
  section_id: string;
  error_type: string;
  message: string;
  retries_attempted?: number;
}

export interface GenerateDeckResponse {
  ticker: string;
  company_name: string;
  plan_tier?: 'free' | 'pro' | 'enterprise';
  model_mode?: 'auto' | 'specific';
  analysis_depth?: 'low' | 'medium' | 'high';
  generated_at: string;
  provider_used: {
    provider: string;
    model: string;
    reasoning_level: string;
  };
  computed_inputs?: {
    comps_table?: unknown;
  };
  results: GeneratedSection[];
  errors?: GenerationError[];
  request_id?: string;
  // Legacy format support
  metadata?: {
    ticker: string;
    company_name: string;
    generated_at: string;
    provider: string;
    model: string;
  };
  sections?: GeneratedSection[];
  warnings?: string[];
}

// --- Intake redesign types ---

export type Position = 'long' | 'short';
export type DeckLength = 'short' | 'standard' | 'deep';
export type DataTrustMode = 'user_only' | 'user_auto_fetch' | 'narrative_only';
export type WorkflowMode = 'auto' | 'guided';
export type VisualPreference =
  | 'auto'
  | 'bullets'
  | 'table'
  | 'timeline'
  | 'two_column'
  | 'swot'
  | 'valuation'
  | 'chart';
export type NarrativeTone =
  | 'balanced'
  | 'bullish'
  | 'bearish'
  | 'risk_focused'
  | 'catalyst_focused';
export type AnalystConfidence = 'low' | 'medium' | 'high';

export interface ThesisInput {
  thesis_sentence?: string;
  market_believes?: string;
  we_believe?: string;
  pillars?: string[];
  what_changes_mind?: string[];
}

export interface CatalystInput {
  name: string;
  timing_window?: string;
  mechanism?: string;
  evidence?: string;
}

export interface ValuationMethodInput {
  methods?: string[];
  peer_tickers?: string[];
  target_multiple_range?: string;
  dcf_assumptions?: string;
  price_target?: string;
}

export interface RiskInput {
  risk: string;
  leading_indicator?: string;
  mitigant?: string;
}

export interface DataBlocks {
  kpi_table?: string;
  segment_mix?: string;
  debt_maturities?: string;
  ownership_notes?: string;
  filing_excerpts?: string;
}

export interface UserConstraints {
  liquidity_floor?: string;
  leverage_ceiling?: string;
  esg_constraints?: string;
  exclude_peers?: string[];
}

export interface SectionControl {
  section_id: string;
  approved?: boolean;
  lock_key_metrics?: boolean;
  locked_metrics?: string[];
  visual_preference?: VisualPreference;
  narrative_tone?: NarrativeTone;
  include_talking_points?: string[];
  exclude_talking_points?: string[];
  analyst_notes?: string;
  confidence?: AnalystConfidence;
}

export interface SectionAnalysisInput {
  section_id: string;
  section_name?: string;
  key_findings?: string[];
  supporting_data_points?: string[];
  risks_or_gaps?: string[];
  recommended_storyline?: string;
  suggested_visual?: string;
}

export interface SectionAnalysisResult extends SectionAnalysisInput {
  section_name: string;
  key_findings: string[];
  supporting_data_points: string[];
  risks_or_gaps: string[];
  recommended_storyline: string;
  suggested_controls: Omit<SectionControl, 'section_id' | 'approved'>;
}

export interface AnalyzeSectionsResponse {
  ticker: string;
  company_name: string;
  plan_tier?: 'free' | 'pro' | 'enterprise';
  model_mode?: 'auto' | 'specific';
  analysis_depth?: 'low' | 'medium' | 'high';
  analyzed_at: string;
  provider_used: {
    provider: string;
    model: string;
    reasoning_level: string;
  };
  analyses: SectionAnalysisResult[];
  errors?: GenerationError[];
  request_id?: string;
}

export interface GenerateDeckRequest {
  ticker: string;
  company_name?: string;
  sector?: string;
  fund_constraints: {
    time_horizon: string;
    risk_profile: string;
    portfolio_context?: string;
    style?: string;
  };
  sections?: string[];
  provider?: 'gemini';
  model?: string;
  plan_tier?: 'free' | 'pro' | 'enterprise';
  model_mode?: 'auto' | 'specific';
  analysis_depth?: 'low' | 'medium' | 'high';
  reasoning_level?: 'low' | 'medium' | 'high';
  include_comps?: boolean;
  comp_tickers?: string[];
  // Intake redesign fields
  position?: Position;
  deck_length?: DeckLength;
  data_trust_mode?: DataTrustMode;
  thesis?: ThesisInput;
  catalysts?: CatalystInput[];
  valuation_input?: ValuationMethodInput;
  risks?: RiskInput[];
  data_blocks?: DataBlocks;
  user_constraints?: UserConstraints;
  workflow_mode?: WorkflowMode;
  section_controls?: SectionControl[];
  section_analyses?: SectionAnalysisInput[];
}

// ----- API Calls -----

/**
 * Fetch available deck sections
 */
export async function fetchSections(): Promise<Section[]> {
  const response = await requestJson(`${API_BASE}/api/v1/sections`);
  const data = await handleResponse<SectionsResponse>(response);
  return data.sections;
}

/**
 * Generate a pitch deck
 */
export async function generateDeck(request: GenerateDeckRequest): Promise<GenerateDeckResponse> {
  const url = `${API_BASE}/api/v1/deck/generate`;
  const response = await requestJson(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return handleResponse<GenerateDeckResponse>(response);
}

export async function generateDeckAuthed(
  authFetch: (url: string, options?: RequestInit) => Promise<Response>,
  request: GenerateDeckRequest
): Promise<GenerateDeckResponse> {
  const url = `${API_BASE}/api/v1/deck/generate`;
  let response: Response;
  try {
    response = await authFetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
  } catch (error) {
    if (isLikelyNetworkError(error)) {
      throw buildNetworkError(url, error);
    }
    throw new Error(getErrorMessage(error));
  }
  return handleResponse<GenerateDeckResponse>(response);
}

export async function analyzeSectionsAuthed(
  authFetch: (url: string, options?: RequestInit) => Promise<Response>,
  request: GenerateDeckRequest
): Promise<AnalyzeSectionsResponse> {
  const url = `${API_BASE}/api/v1/deck/sections/analyze`;
  let response: Response;
  try {
    response = await authFetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
  } catch (error) {
    if (isLikelyNetworkError(error)) {
      throw buildNetworkError(url, error);
    }
    throw new Error(getErrorMessage(error));
  }
  return handleResponse<AnalyzeSectionsResponse>(response);
}

/**
 * Regenerate a single section
 */
export async function regenerateSection(
  request: GenerateDeckRequest & { section_id: string }
): Promise<GeneratedSection> {
  const url = `${API_BASE}/api/v1/deck/section/regenerate`;
  const response = await requestJson(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return handleResponse<GeneratedSection>(response);
}
