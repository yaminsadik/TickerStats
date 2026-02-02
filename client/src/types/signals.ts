/**
 * Signal Layer Types and Default Configuration
 */

export type SignalDirection = 'higher_better' | 'lower_better';
export type SignalMode = 'percentile' | 'absolute';
export type SignalLevel = 'good' | 'warn' | 'neutral' | 'missing';

export interface PercentileThresholds {
  good: number; // 0-100 percentile
  warn: number; // 0-100 percentile
}

export interface AbsoluteThresholds {
  good: number;
  warn: number;
}

export interface SignalRule {
  label: string;
  enabled: boolean;
  direction: SignalDirection;
  mode: SignalMode;
  percentile: PercentileThresholds;
  absolute: AbsoluteThresholds;
}

export interface SignalSettings {
  enabled: boolean;
  globalMode: SignalMode;
  rules: Record<string, SignalRule>;
}

export interface ComputedSignal {
  level: SignalLevel;
  rule: SignalRule;
  value: number | null;
  thresholdInfo: {
    mode: SignalMode;
    goodThreshold: number;
    warnThreshold: number;
  };
}

// Metric categories for organization in the UI
export interface MetricCategory {
  id: string;
  label: string;
  metrics: string[];
}

export const METRIC_CATEGORIES: MetricCategory[] = [
  { id: 'valuation', label: 'Valuation', metrics: ['forwardPE', 'priceSales', 'priceBook', 'evEbitda', 'evRevenue'] },
  { id: 'profitability', label: 'Profitability', metrics: ['profitMargin', 'roa', 'roe'] },
  { id: 'leverage', label: 'Leverage & Risk', metrics: ['debtEquity', 'beta'] },
];

// Human-readable labels for directions
export const DIRECTION_LABELS: Record<SignalDirection, string> = {
  higher_better: 'Higher is better',
  lower_better: 'Lower is better',
};

/**
 * Default signal rules for all supported metrics.
 * 
 * Absolute thresholds are rule-of-thumb values for quick assessment.
 * Percentile mode uses relative comparison within the current data set.
 */
export const DEFAULT_SIGNAL_RULES: Record<string, SignalRule> = {
  // Price is not typically signaled
  sharePrice: {
    label: 'Share Price',
    enabled: false,
    direction: 'higher_better',
    mode: 'percentile',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0, warn: 0 },
  },
  // Market cap - usually not signaled, just informational
  marketCap: {
    label: 'Market Cap',
    enabled: false,
    direction: 'higher_better',
    mode: 'percentile',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0, warn: 0 },
  },
  // Enterprise value - usually not signaled
  enterpriseValue: {
    label: 'Enterprise Value',
    enabled: false,
    direction: 'higher_better',
    mode: 'percentile',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0, warn: 0 },
  },
  // Forward P/E: Lower is better (cheaper valuation)
  forwardPE: {
    label: 'Forward P/E',
    enabled: true,
    direction: 'lower_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 20, warn: 30 },
  },
  // Price/Sales: Lower is better
  priceSales: {
    label: 'Price/Sales',
    enabled: true,
    direction: 'lower_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 3, warn: 10 },
  },
  // Price/Book: Lower is better
  priceBook: {
    label: 'Price/Book',
    enabled: true,
    direction: 'lower_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 3, warn: 10 },
  },
  // EV/EBITDA: Lower is better
  evEbitda: {
    label: 'EV/EBITDA',
    enabled: true,
    direction: 'lower_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 12, warn: 20 },
  },
  // EV/Revenue: Sector-specific, use percentile by default
  evRevenue: {
    label: 'EV/Revenue',
    enabled: true,
    direction: 'lower_better',
    mode: 'percentile',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 3, warn: 8 },
  },
  // Profit Margin: Higher is better
  profitMargin: {
    label: 'Profit Margin',
    enabled: true,
    direction: 'higher_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0.20, warn: 0.05 },
  },
  // ROA: Higher is better
  roa: {
    label: 'ROA',
    enabled: true,
    direction: 'higher_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0.05, warn: 0.02 },
  },
  // ROE: Higher is better
  roe: {
    label: 'ROE',
    enabled: true,
    direction: 'higher_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0.15, warn: 0.08 },
  },
  // Debt/Equity: Lower is better (Yahoo returns percent-ish like 152.4)
  debtEquity: {
    label: 'Debt/Equity',
    enabled: true,
    direction: 'lower_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 100, warn: 200 },
  },
  // Beta: Lower is better (less volatile than market)
  beta: {
    label: 'Beta',
    enabled: true,
    direction: 'lower_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 1.0, warn: 1.5 },
  },
  // Performance: Return - Higher is better
  return: {
    label: 'Return',
    enabled: true,
    direction: 'higher_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0.10, warn: -0.05 },
  },
  // Volatility: Lower is better
  volatility: {
    label: 'Volatility',
    enabled: true,
    direction: 'lower_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0.20, warn: 0.40 },
  },
  // Max Drawdown: Higher (less negative) is better
  maxDrawdown: {
    label: 'Max Drawdown',
    enabled: true,
    direction: 'higher_better',
    mode: 'absolute',
    percentile: { good: 25, warn: 75 },
    absolute: { good: -0.10, warn: -0.30 },
  },
  // Generic perf rule
  perf: {
    label: 'Performance',
    enabled: true,
    direction: 'higher_better',
    mode: 'percentile',
    percentile: { good: 75, warn: 25 },
    absolute: { good: 0.10, warn: -0.05 },
  },
};

export const DEFAULT_SIGNAL_SETTINGS: SignalSettings = {
  enabled: true,
  globalMode: 'percentile',
  rules: DEFAULT_SIGNAL_RULES,
};

export const STORAGE_KEY = 'signalRules:v1';
