const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

interface ApiError {
  message: string;
  code?: string;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      message: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.message || 'An error occurred');
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

export interface GenerateDeckResponse {
  ticker: string;
  company_name: string;
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
  errors?: string[];
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
  provider?: 'openai' | 'gemini';
  reasoning_level?: 'low' | 'medium' | 'high';
  include_comps?: boolean;
  comp_tickers?: string[];
}

// ----- API Calls -----

/**
 * Fetch available deck sections
 */
export async function fetchSections(): Promise<Section[]> {
  const response = await fetch(`${API_BASE}/api/v1/sections`);
  const data = await handleResponse<SectionsResponse>(response);
  return data.sections;
}

/**
 * Generate a pitch deck
 */
export async function generateDeck(request: GenerateDeckRequest): Promise<GenerateDeckResponse> {
  const response = await fetch(`${API_BASE}/api/v1/deck/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return handleResponse<GenerateDeckResponse>(response);
}

/**
 * Regenerate a single section
 */
export async function regenerateSection(
  request: GenerateDeckRequest & { section_id: string }
): Promise<GeneratedSection> {
  const response = await fetch(`${API_BASE}/api/v1/deck/section/regenerate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  return handleResponse<GeneratedSection>(response);
}
