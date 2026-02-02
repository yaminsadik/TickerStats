/**
 * Signal computation utilities.
 * 
 * Percentile calculation uses linear interpolation method:
 * - Sort values ascending
 * - For percentile p, compute index = (n-1) * p / 100
 * - Interpolate between floor and ceil indices
 * 
 * This is equivalent to NumPy's "linear" interpolation method.
 */

import type {
  SignalRule,
  SignalLevel,
  SignalMode,
  ComputedSignal,
  SignalSettings,
} from '../types/signals';
import type { RowData } from '../types/api';

/**
 * Compute percentile using linear interpolation.
 * 
 * @param sortedValues - Array of numbers, must be sorted ascending
 * @param percentile - Percentile to compute (0-100)
 * @returns The interpolated percentile value
 */
export function computePercentile(sortedValues: number[], percentile: number): number {
  if (sortedValues.length === 0) return 0;
  if (sortedValues.length === 1) return sortedValues[0];
  
  const index = (sortedValues.length - 1) * (percentile / 100);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  
  if (lower === upper) {
    return sortedValues[lower];
  }
  
  const fraction = index - lower;
  return sortedValues[lower] + fraction * (sortedValues[upper] - sortedValues[lower]);
}

/**
 * Extract all non-null values for a specific metric from rows.
 */
export function extractMetricValues(
  rows: RowData[],
  metricKey: string
): number[] {
  const values: number[] = [];
  
  for (const row of rows) {
    // Check snapshot first
    if (row.snapshot[metricKey] !== undefined && row.snapshot[metricKey] !== null) {
      values.push(row.snapshot[metricKey] as number);
    }
    // Check performance
    else if (row.performance && row.performance[metricKey] !== undefined && row.performance[metricKey] !== null) {
      values.push(row.performance[metricKey] as number);
    }
  }
  
  return values;
}

/**
 * Precompute percentile thresholds for all metrics.
 */
export function computePercentileThresholds(
  rows: RowData[],
  metrics: string[],
  settings: SignalSettings
): Record<string, { p25: number; p75: number; pGood: number; pWarn: number }> {
  const thresholds: Record<string, { p25: number; p75: number; pGood: number; pWarn: number }> = {};
  
  for (const metric of metrics) {
    const values = extractMetricValues(rows, metric);
    if (values.length < 2) {
      // Not enough data for meaningful percentiles
      thresholds[metric] = { p25: 0, p75: 0, pGood: 0, pWarn: 0 };
      continue;
    }
    
    const sorted = [...values].sort((a, b) => a - b);
    const rule = settings.rules[metric];
    
    const goodPct = rule?.percentile.good ?? 25;
    const warnPct = rule?.percentile.warn ?? 75;
    
    thresholds[metric] = {
      p25: computePercentile(sorted, 25),
      p75: computePercentile(sorted, 75),
      pGood: computePercentile(sorted, goodPct),
      pWarn: computePercentile(sorted, warnPct),
    };
  }
  
  return thresholds;
}

/**
 * Determine signal level for a value given a rule.
 */
export function computeSignalLevel(
  value: number | null,
  rule: SignalRule,
  mode: SignalMode,
  percentileThresholds?: { pGood: number; pWarn: number }
): SignalLevel {
  if (value === null || value === undefined) {
    return 'missing';
  }
  
  if (!rule.enabled) {
    return 'neutral';
  }
  
  const effectiveMode = mode;
  
  if (effectiveMode === 'absolute') {
    return computeAbsoluteLevel(value, rule);
  } else {
    if (!percentileThresholds) {
      return 'neutral';
    }
    return computePercentileLevel(value, rule, percentileThresholds);
  }
}

function computeAbsoluteLevel(value: number, rule: SignalRule): SignalLevel {
  const { good, warn } = rule.absolute;
  
  if (rule.direction === 'lower_better') {
    // Lower is better: good if <= good threshold, warn if >= warn threshold
    if (value <= good) return 'good';
    if (value >= warn) return 'warn';
    return 'neutral';
  } else {
    // Higher is better: good if >= good threshold, warn if <= warn threshold
    if (value >= good) return 'good';
    if (value <= warn) return 'warn';
    return 'neutral';
  }
}

function computePercentileLevel(
  value: number,
  rule: SignalRule,
  thresholds: { pGood: number; pWarn: number }
): SignalLevel {
  const { pGood, pWarn } = thresholds;
  
  if (rule.direction === 'lower_better') {
    // Lower is better: good if in low percentiles, warn if in high percentiles
    if (value <= pGood) return 'good';
    if (value >= pWarn) return 'warn';
    return 'neutral';
  } else {
    // Higher is better: good if in high percentiles, warn if in low percentiles
    // For higher_better, we flip: good is high values (>= pWarn), warn is low values (<= pGood)
    if (value >= pWarn) return 'good';
    if (value <= pGood) return 'warn';
    return 'neutral';
  }
}

/**
 * Compute full signal info for a cell.
 */
export function computeSignal(
  value: number | null,
  metricKey: string,
  settings: SignalSettings,
  percentileThresholds?: Record<string, { pGood: number; pWarn: number }>
): ComputedSignal {
  const rule = settings.rules[metricKey] ?? {
    label: metricKey,
    enabled: false,
    direction: 'higher_better' as const,
    mode: 'percentile' as const,
    percentile: { good: 25, warn: 75 },
    absolute: { good: 0, warn: 0 },
  };
  
  const effectiveMode = settings.globalMode;
  const pThresholds = percentileThresholds?.[metricKey];
  
  const level = computeSignalLevel(value, rule, effectiveMode, pThresholds);
  
  // Determine threshold info for tooltip
  let goodThreshold: number;
  let warnThreshold: number;
  
  if (effectiveMode === 'absolute') {
    goodThreshold = rule.absolute.good;
    warnThreshold = rule.absolute.warn;
  } else {
    goodThreshold = pThresholds?.pGood ?? 0;
    warnThreshold = pThresholds?.pWarn ?? 0;
  }
  
  return {
    level,
    rule,
    value,
    thresholdInfo: {
      mode: effectiveMode,
      goodThreshold,
      warnThreshold,
    },
  };
}

/**
 * Format threshold value for display in tooltip.
 */
export function formatThresholdValue(value: number, _metricKey: string, unit?: string): string {
  if (unit === 'decimal') {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (unit === 'currency') {
    return value.toFixed(2);
  }
  return value.toFixed(2);
}

/**
 * Generate tooltip text for a signal.
 */
export function getSignalTooltip(
  metricKey: string,
  settings: SignalSettings,
  level: SignalLevel
): string {
  if (level === 'missing') {
    return 'No data available';
  }

  const rule = settings.rules[metricKey];
  if (!rule || !rule.enabled) {
    return 'Signal disabled for this metric';
  }

  const mode = settings.globalMode;
  const direction = rule.direction;

  if (mode === 'percentile') {
    const pctGood = rule.percentile.good;
    const pctWarn = rule.percentile.warn;

    if (direction === 'lower_better') {
      return `Percentile mode • Good: ≤ p${pctGood} • Warn: ≥ p${pctWarn}`;
    } else {
      return `Percentile mode • Good: ≥ p${pctWarn} • Warn: ≤ p${pctGood}`;
    }
  } else {
    const goodThreshold = rule.absolute.good;
    const warnThreshold = rule.absolute.warn;

    if (direction === 'lower_better') {
      return `Absolute mode • Good: ≤ ${goodThreshold} • Warn: ≥ ${warnThreshold}`;
    } else {
      return `Absolute mode • Good: ≥ ${goodThreshold} • Warn: ≤ ${warnThreshold}`;
    }
  }
}

/**
 * Compute signals for all cells in a table.
 * Returns a Map with keys like "SYMBOL:metric" and values as SignalLevel.
 */
export function computeSignalMap(
  rows: RowData[],
  columns: string[],
  settings: SignalSettings
): Map<string, SignalLevel> {
  const signalMap = new Map<string, SignalLevel>();

  if (!settings.enabled) {
    return signalMap;
  }

  // Pre-compute percentile thresholds for all columns
  const pctThresholds = computePercentileThresholds(rows, columns, settings);

  for (const row of rows) {
    for (const col of columns) {
      const rule = settings.rules[col];
      if (!rule || !rule.enabled) {
        continue;
      }

      // Get value from snapshot or performance
      let value: number | null = null;
      if (row.snapshot[col] !== undefined && row.snapshot[col] !== null) {
        value = row.snapshot[col] as number;
      } else if (row.performance && row.performance[col] !== undefined && row.performance[col] !== null) {
        value = row.performance[col] as number;
      }

      const level = computeSignalLevel(
        value,
        rule,
        settings.globalMode,
        pctThresholds[col]
      );

      if (level !== 'neutral') {
        signalMap.set(`${row.symbol}:${col}`, level);
      }
    }
  }

  return signalMap;
}
