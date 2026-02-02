export interface DeckDraftBasics {
  ticker: string;
  companyName: string;
  sector: string;
  companyContext?: string;
  investmentThesis?: string;
}

export interface FundConstraints {
  time_horizon: string;
  risk_profile: string;
  portfolio_context?: string;
  style?: string;
}

export interface DeckDraftConfig {
  sections: string[];
  provider: 'openai' | 'gemini';
  quality: 'low' | 'medium' | 'high';
}

export interface DeckDraft {
  id: string;
  createdAt: string;
  updatedAt: string;
  basics: DeckDraftBasics;
  config: DeckDraftConfig;
  // Generated content stored after generation
  generatedContent?: import('../api/deckApi').GenerateDeckResponse;
  status: 'draft' | 'generating' | 'complete' | 'error';
  error?: string;
}

/**
 * Clear all drafts from localStorage
 */
export function clearAllDrafts(): void {
  localStorage.removeItem(STORAGE_KEY);
}

const STORAGE_KEY = 'deck-drafts';

/**
 * Generate a unique draft ID
 */
function generateDraftId(): string {
  return `draft-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Get all drafts from localStorage
 */
export function getDrafts(): DeckDraft[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) return [];
    
    const drafts = JSON.parse(data);
    // Migrate old drafts to new schema
    return drafts.map((draft: any) => migrateDraft(draft));
  } catch {
    return [];
  }
}

/**
 * Migrate old draft format to new schema
 */
function migrateDraft(draft: any): DeckDraft {
  // If draft already has new fields, return as is
  if (draft.basics?.companyName && draft.basics?.sector) {
    return draft as DeckDraft;
  }
  
  // Migrate old draft format
  return {
    ...draft,
    basics: {
      ticker: draft.basics?.ticker || '',
      companyName: draft.generatedContent?.metadata?.company_name || draft.basics?.ticker || '',
      sector: draft.basics?.sector || 'Technology',
      companyContext: draft.basics?.companyContext,
      investmentThesis: draft.basics?.investmentThesis,
    },
  };
}

/**
 * Get a specific draft by ID
 */
export function getDraft(id: string): DeckDraft | null {
  const drafts = getDrafts();
  return drafts.find((d) => d.id === id) || null;
}

/**
 * Save all drafts to localStorage
 */
function saveDrafts(drafts: DeckDraft[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
}

/**
 * Create a new draft
 */
export function createDraft(
  basics: DeckDraftBasics,
  config?: Partial<DeckDraftConfig>
): DeckDraft {
  const now = new Date().toISOString();
  const draft: DeckDraft = {
    id: generateDraftId(),
    createdAt: now,
    updatedAt: now,
    basics,
    config: {
      sections: config?.sections || [],
      provider: config?.provider || 'openai',
      quality: config?.quality || 'medium',
    },
    status: 'draft',
  };

  const drafts = getDrafts();
  drafts.unshift(draft); // Add to beginning
  saveDrafts(drafts);

  return draft;
}

/**
 * Update an existing draft
 */
export function updateDraft(id: string, updates: Partial<Omit<DeckDraft, 'id' | 'createdAt'>>): DeckDraft | null {
  const drafts = getDrafts();
  const index = drafts.findIndex((d) => d.id === id);

  if (index === -1) return null;

  drafts[index] = {
    ...drafts[index],
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  saveDrafts(drafts);
  return drafts[index];
}

/**
 * Update draft basics
 */
export function updateDraftBasics(id: string, basics: Partial<DeckDraftBasics>): DeckDraft | null {
  const draft = getDraft(id);
  if (!draft) return null;

  return updateDraft(id, {
    basics: { ...draft.basics, ...basics },
  });
}

/**
 * Update draft config
 */
export function updateDraftConfig(id: string, config: Partial<DeckDraftConfig>): DeckDraft | null {
  const draft = getDraft(id);
  if (!draft) return null;

  return updateDraft(id, {
    config: { ...draft.config, ...config },
  });
}

/**
 * Delete a draft
 */
export function deleteDraft(id: string): boolean {
  const drafts = getDrafts();
  const filtered = drafts.filter((d) => d.id !== id);

  if (filtered.length === drafts.length) return false;

  saveDrafts(filtered);
  return true;
}

/**
 * Mark draft as generating
 */
export function markDraftGenerating(id: string): DeckDraft | null {
  return updateDraft(id, { status: 'generating', error: undefined });
}

/**
 * Save generated content to draft
 */
export function saveDraftContent(
  id: string,
  content: import('../api/deckApi').GenerateDeckResponse
): DeckDraft | null {
  return updateDraft(id, {
    status: 'complete',
    generatedContent: content,
    error: undefined,
  });
}

/**
 * Mark draft as errored
 */
export function markDraftError(id: string, error: string): DeckDraft | null {
  return updateDraft(id, { status: 'error', error });
}

/**
 * Merge a regenerated section into existing draft content
 */
export function mergeSectionIntoDraft(
  id: string,
  section: import('../api/deckApi').GeneratedSection
): DeckDraft | null {
  const draft = getDraft(id);
  if (!draft || !draft.generatedContent) return null;

  const updatedSections = draft.generatedContent.sections.map((s) =>
    s.section_id === section.section_id ? section : s
  );

  return updateDraft(id, {
    generatedContent: {
      ...draft.generatedContent,
      sections: updatedSections,
    },
  });
}
