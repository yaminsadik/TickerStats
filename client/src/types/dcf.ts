/**
 * DCF Valuation Types
 * 
 * Type definitions for the deterministic DCF calculator API.
 */

export interface DCFAssumptions {
  forecastYears: number;
  fcfGrowthRate: number;
  terminalGrowthRate: number;
  wacc: number;
}

export interface DCFOverrides {
  sharesOutstanding?: number | null;
  cash?: number | null;
  debt?: number | null;
  fcf0?: number | null;
  marketPrice?: number | null;
}

export interface DCFInputs {
  market_price: number | null;
  shares_outstanding: number | null;
  cash: number | null;
  debt: number | null;
  fcf_0: number | null;
  beta: number | null;
  currency: string;
}

export interface DCFSources {
  market_price: string;
  shares_outstanding: string;
  cash: string;
  debt: string;
  fcf_0: string;
  beta: string;
}

export interface DCFYearForecast {
  year: number;
  fcf: number;
  pvFcf: number;
}

export interface DCFCalculationBreakdown {
  fcf0: number;
  forecastYears: number;
  fcfGrowthRate: number;
  terminalGrowthRate: number;
  wacc: number;
  fcfForecast: DCFYearForecast[];
  fcfNPlus1: number;
  terminalValue: number;
  pvTerminal: number;
  sumPvFcf: number;
  enterpriseValue: number;
  cash: number;
  debt: number;
  equityValue: number;
  sharesOutstanding: number;
  targetPrice: number;
  marketPrice: number;
  upsidePct: number;
}

export interface DCFValuation {
  targetPrice: number;
  marketPrice: number;
  upsidePct: number;
}

export interface DCFMeta {
  ticker: string;
  asOf: string;
  currency: string;
  provider: string;
}

export interface DCFResult {
  meta: DCFMeta;
  inputs: DCFInputs;
  assumptions: DCFAssumptions;
  valuation: DCFValuation;
  calculationBreakdown: DCFCalculationBreakdown;
  warnings: string[];
  sources: DCFSources;
  error: string | null;
}

export interface DCFRequest {
  ticker: string;
  assumptions?: Partial<DCFAssumptions>;
  overrides?: DCFOverrides;
}

export interface DCFInputsResponse {
  ticker: string;
  inputs: DCFInputs;
  sources: DCFSources;
  warnings: string[];
}

// Default assumptions
export const DEFAULT_DCF_ASSUMPTIONS: DCFAssumptions = {
  forecastYears: 5,
  fcfGrowthRate: 0.08,
  terminalGrowthRate: 0.025,
  wacc: 0.09,
};
