import type { UnitType } from '../types/api';

/**
 * Format a number based on its unit type from the API
 */
export function formatValue(
  value: number | null | undefined,
  unit: UnitType | string | undefined,
  field?: string
): string {
  if (value === null || value === undefined) {
    return '—';
  }

  switch (unit) {
    case 'currency':
      return formatCurrency(value, field);
    case 'decimal':
      return formatDecimal(value);
    case 'ratio':
      return formatRatio(value, field);
    default:
      return formatGeneric(value);
  }
}

/**
 * Format currency values
 * - sharePrice: $123.45
 * - marketCap/enterpriseValue: 3.82T or 382B
 */
function formatCurrency(value: number, field?: string): string {
  if (field === 'sharePrice') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  // For large values like marketCap, enterpriseValue
  const absValue = Math.abs(value);
  if (absValue >= 1e12) {
    return `$${(value / 1e12).toFixed(2)}T`;
  } else if (absValue >= 1e9) {
    return `$${(value / 1e9).toFixed(2)}B`;
  } else if (absValue >= 1e6) {
    return `$${(value / 1e6).toFixed(2)}M`;
  } else {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }
}

/**
 * Format decimal values as percentages
 * - profitMargin, roa, roe: 12.34%
 * - return, volatility, maxDrawdown: 12.34%
 */
function formatDecimal(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

/**
 * Format ratio values with up to 2 decimals
 */
function formatRatio(value: number, field?: string): string {
  // Special case: dcfUpside is already a percentage value
  if (field === 'dcfUpside') {
    return `${value.toFixed(2)}%`;
  }
  return value.toFixed(2);
}

/**
 * Generic number formatting fallback
 */
function formatGeneric(value: number): string {
  if (Math.abs(value) >= 1e9) {
    return `${(value / 1e9).toFixed(2)}B`;
  } else if (Math.abs(value) >= 1e6) {
    return `${(value / 1e6).toFixed(2)}M`;
  } else if (Math.abs(value) >= 1000) {
    return new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 2,
    }).format(value);
  } else {
    return value.toFixed(2);
  }
}

/**
 * Format ISO timestamp to readable date/time
 */
export function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(date);
}
