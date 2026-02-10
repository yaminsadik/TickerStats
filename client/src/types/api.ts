export interface PerfRequest {
  period: string;
  metrics: string[];
}

export interface RequestedParams {
  symbols: string[];
  fields: string[];
  perf: PerfRequest | null;
  dcf: boolean;
}

export interface RowData {
  symbol: string;
  snapshot: Record<string, number | null>;
  performance: Record<string, number | null> | null;
  dcf: Record<string, number | null> | null;
  missingFields?: string[];
  missingPerf?: string[] | null;
  error: string | null;
}

export interface RelativeTableResponse {
  asOf: string;
  units: Record<string, string>;
  requested: RequestedParams;
  rows: RowData[];
}

export type UnitType = 'currency' | 'decimal' | 'ratio';

export const SNAPSHOT_FIELDS = [
  'sharePrice',
  'marketCap',
  'enterpriseValue',
  'forwardPE',
  'priceSales',
  'priceBook',
  'evEbitda',
  'evRevenue',
  'profitMargin',
  'roa',
  'roe',
  'debtEquity',
  'beta',
] as const;

export const PERF_METRICS = ['return', 'volatility', 'maxDrawdown'] as const;

export const DCF_METRICS = ['dcfPrice', 'dcfUpside'] as const;

export const PERF_PERIODS = [
  '1mo',
  '3mo',
  '6mo',
  'ytd',
  '1y',
  '2y',
  '5y',
  '10y',
  'max',
] as const;

export type SnapshotField = (typeof SNAPSHOT_FIELDS)[number];
export type PerfMetric = (typeof PERF_METRICS)[number];
export type DcfMetric = (typeof DCF_METRICS)[number];
export type PerfPeriod = (typeof PERF_PERIODS)[number];

export const FIELD_LABELS: Record<string, string> = {
  sharePrice: 'Price',
  marketCap: 'Market Cap',
  enterpriseValue: 'Enterprise Value',
  forwardPE: 'Forward P/E',
  priceSales: 'P/S',
  priceBook: 'P/B',
  evEbitda: 'EV/EBITDA',
  evRevenue: 'EV/Revenue',
  profitMargin: 'Profit Margin',
  roa: 'ROA',
  roe: 'ROE',
  debtEquity: 'Debt/Equity',
  beta: 'Beta',
  return: 'Return',
  volatility: 'Volatility',
  maxDrawdown: 'Max Drawdown',
  dcfPrice: 'DCF Value',
  dcfUpside: 'DCF Upside',
};

export const PERIOD_LABELS: Record<PerfPeriod, string> = {
  '1mo': '1 Month',
  '3mo': '3 Months',
  '6mo': '6 Months',
  'ytd': 'YTD',
  '1y': '1 Year',
  '2y': '2 Years',
  '5y': '5 Years',
  '10y': '10 Years',
  'max': 'Max',
};
