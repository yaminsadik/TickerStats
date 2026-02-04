/**
 * DCF Valuation API Client
 */

import type { DCFRequest, DCFResult, DCFInputsResponse } from '../types/dcf';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

/**
 * Calculate DCF valuation for a ticker
 */
export async function calculateDCF(request: DCFRequest): Promise<DCFResult> {
  const response = await fetch(`${API_BASE}/api/v1/valuation/dcf`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.error || error.message || 'DCF calculation failed');
  }

  return response.json();
}

/**
 * Get DCF inputs for a ticker without calculating valuation
 * Useful for pre-populating the form
 */
export async function getDCFInputs(ticker: string): Promise<DCFInputsResponse> {
  const response = await fetch(
    `${API_BASE}/api/v1/valuation/dcf/inputs/${encodeURIComponent(ticker.toUpperCase())}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.error || error.message || 'Failed to fetch DCF inputs');
  }

  return response.json();
}
