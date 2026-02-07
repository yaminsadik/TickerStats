import type { RelativeTableResponse, PerfPeriod } from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5000';

export interface FetchRelativeParams {
  symbols: string[];
  fields?: string[];
  perf?: string[];
  perfPeriod?: PerfPeriod;
  dcf?: boolean;
}

export async function fetchRelativeTable(
  params: FetchRelativeParams
): Promise<RelativeTableResponse> {
  const url = new URL(`${API_BASE}/api/relative`);

  url.searchParams.set('symbols', params.symbols.join(','));

  if (params.fields && params.fields.length > 0) {
    url.searchParams.set('fields', params.fields.join(','));
  }

  if (params.perf && params.perf.length > 0 && params.perfPeriod) {
    url.searchParams.set('perf', params.perf.join(','));
    url.searchParams.set('perfPeriod', params.perfPeriod);
  }

  if (params.dcf) {
    url.searchParams.set('dcf', 'true');
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

export async function fetchRelativeTableAuthed(
  authFetch: (url: string, options?: RequestInit) => Promise<Response>,
  params: FetchRelativeParams
): Promise<RelativeTableResponse> {
  const url = new URL(`${API_BASE}/api/relative`);

  url.searchParams.set('symbols', params.symbols.join(','));

  if (params.fields && params.fields.length > 0) {
    url.searchParams.set('fields', params.fields.join(','));
  }

  if (params.perf && params.perf.length > 0 && params.perfPeriod) {
    url.searchParams.set('perf', params.perf.join(','));
    url.searchParams.set('perfPeriod', params.perfPeriod);
  }

  if (params.dcf) {
    url.searchParams.set('dcf', 'true');
  }

  const response = await authFetch(url.toString());

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error ${response.status}`);
  }

  return response.json();
}

export type ExportFormat = 'csv' | 'xlsx' | 'pdf';

export function getExportUrl(params: FetchRelativeParams, format: ExportFormat = 'csv'): string {
  const url = new URL(`${API_BASE}/api/relative/export`);

  url.searchParams.set('symbols', params.symbols.join(','));
  url.searchParams.set('format', format);

  if (params.fields && params.fields.length > 0) {
    url.searchParams.set('fields', params.fields.join(','));
  }

  if (params.perf && params.perf.length > 0 && params.perfPeriod) {
    url.searchParams.set('perf', params.perf.join(','));
    url.searchParams.set('perfPeriod', params.perfPeriod);
  }

  if (params.dcf) {
    url.searchParams.set('dcf', 'true');
  }

  return url.toString();
}
