/**
 * Landing page mocked data: deterministic, no API calls.
 * All numbers match the real product screenshots.
 */

// ─── Hero comp table (matches screenshots exactly) ──────────────────────────

export interface HeroRow {
  symbol: string;
  price: number;
  marketCap: string;
  ev: string;
  forwardPE: number;
  ps: number;
  pb: number;
  evEbitda: number;
  evRevenue: number;
  profitMargin: number;
  roa: number | null;
  roe: number;
  debtEquity: number | null;
  beta: number;
  returnPct: number;
  volatility: number;
  maxDrawdown: number;
  dcfValue: number;
  dcfUpside: number;
  // signal flags
  peOk: boolean;
  psOk: boolean;
  pbOk: boolean;
  evEbitdaWarn: boolean;
  profitMarginWarn: boolean;
  betaOk: boolean;
  debtEquityOk: boolean;
  roeOk: boolean;
}

export const HERO_TIMESTAMP = "Feb 7, 2026, 02:14 PM CST";
export const HERO_TICKER_COUNT = 5;

export const heroRows: HeroRow[] = [
  {
    symbol: "JNJ",
    price: 239.99,
    marketCap: "$578.21B",
    ev: "$605.44B",
    forwardPE: 19.13,
    ps: 6.14,
    pb: 7.28,
    evEbitda: 18.31,
    evRevenue: 6.43,
    profitMargin: 28.46,
    roa: null,
    roe: 35.56,
    debtEquity: 57.77,
    beta: 0.35,
    returnPct: 29.45,
    volatility: 16.74,
    maxDrawdown: -4.6,
    dcfValue: 129.48,
    dcfUpside: -46.05,
    peOk: true,
    psOk: false,
    pbOk: false,
    evEbitdaWarn: false,
    profitMarginWarn: false,
    betaOk: true,
    debtEquityOk: true,
    roeOk: true,
  },
  {
    symbol: "PFE",
    price: 27.22,
    marketCap: "$154.76B",
    ev: "$202.01B",
    forwardPE: 9.64,
    ps: 2.47,
    pb: 1.67,
    evEbitda: 7.86,
    evRevenue: 3.23,
    profitMargin: 12.42,
    roa: null,
    roe: 8.58,
    debtEquity: 66.53,
    beta: 0.44,
    returnPct: 13.29,
    volatility: 25.3,
    maxDrawdown: -5.86,
    dcfValue: 16.39,
    dcfUpside: -39.78,
    peOk: true,
    psOk: true,
    pbOk: true,
    evEbitdaWarn: false,
    profitMarginWarn: false,
    betaOk: true,
    debtEquityOk: true,
    roeOk: false,
  },
  {
    symbol: "UNH",
    price: 276.65,
    marketCap: "$250.60B",
    ev: "$303.63B",
    forwardPE: 13.81,
    ps: 0.56,
    pb: 2.52,
    evEbitda: 13.02,
    evRevenue: 0.68,
    profitMargin: 2.69,
    roa: 3.9,
    roe: 12.54,
    debtEquity: 77.08,
    beta: 0.41,
    returnPct: -14.1,
    volatility: 49.38,
    maxDrawdown: -24.62,
    dcfValue: 303.13,
    dcfUpside: 9.57,
    peOk: true,
    psOk: false,
    pbOk: false,
    evEbitdaWarn: false,
    profitMarginWarn: true,
    betaOk: true,
    debtEquityOk: true,
    roeOk: false,
  },
  {
    symbol: "ABBV",
    price: 223.43,
    marketCap: "$394.89B",
    ev: "$458.11B",
    forwardPE: 13.97,
    ps: 6.46,
    pb: -149.45,
    evEbitda: 15.57,
    evRevenue: 7.49,
    profitMargin: 6.91,
    roa: null,
    roe: 1106.67,
    debtEquity: null,
    beta: 0.33,
    returnPct: 2.77,
    volatility: 26.28,
    maxDrawdown: -8.68,
    dcfValue: 158.23,
    dcfUpside: -29.18,
    peOk: true,
    psOk: false,
    pbOk: false,
    evEbitdaWarn: false,
    profitMarginWarn: false,
    betaOk: true,
    debtEquityOk: false,
    roeOk: true,
  },
  {
    symbol: "TMO",
    price: 542.83,
    marketCap: "$203.95B",
    ev: "$233.51B",
    forwardPE: 20.16,
    ps: 4.58,
    pb: 3.82,
    evEbitda: 20.94,
    evRevenue: 5.24,
    profitMargin: 15.05,
    roa: 5.04,
    roe: 13.02,
    debtEquity: 73.57,
    beta: 0.95,
    returnPct: -5.1,
    volatility: 23.14,
    maxDrawdown: -15.18,
    dcfValue: 129.7,
    dcfUpside: -76.11,
    peOk: false,
    psOk: false,
    pbOk: false,
    evEbitdaWarn: true,
    profitMarginWarn: false,
    betaOk: true,
    debtEquityOk: true,
    roeOk: false,
  },
];

// ─── Interactive comp demo (8 tickers × 4 time windows) ────────────────────

export const DEMO_TICKERS = [
  "AAPL",
  "MSFT",
  "GOOGL",
  "AMZN",
  "META",
  "NVDA",
  "TSLA",
  "JPM",
] as const;

export type DemoTicker = (typeof DEMO_TICKERS)[number];

export interface DemoRow {
  symbol: string;
  price: number;
  marketCap: string;
  forwardPE: number;
  ps: number;
  profitMargin: number;
  roe: number;
  debtEquity: number;
  returnPct: number;
  volatility: number;
  maxDrawdown: number;
  dcfValue: number;
  dcfUpside: number;
}

type TimeWindow = "1D" | "1W" | "1M" | "1Y";

// Deterministic mocked data per ticker per time window
const baseData: Record<
  DemoTicker,
  Omit<DemoRow, "symbol" | "returnPct" | "volatility" | "maxDrawdown">
> = {
  AAPL: {
    price: 237.42,
    marketCap: "$3.58T",
    forwardPE: 31.2,
    ps: 9.1,
    profitMargin: 26.3,
    roe: 157.4,
    debtEquity: 151.86,
    dcfValue: 192.1,
    dcfUpside: -19.08,
  },
  MSFT: {
    price: 432.18,
    marketCap: "$3.21T",
    forwardPE: 33.8,
    ps: 14.3,
    profitMargin: 35.6,
    roe: 37.1,
    debtEquity: 42.16,
    dcfValue: 385.5,
    dcfUpside: -10.79,
  },
  GOOGL: {
    price: 196.54,
    marketCap: "$2.41T",
    forwardPE: 22.4,
    ps: 7.8,
    profitMargin: 28.1,
    roe: 31.2,
    debtEquity: 10.91,
    dcfValue: 210.3,
    dcfUpside: 7.0,
  },
  AMZN: {
    price: 228.67,
    marketCap: "$2.39T",
    forwardPE: 37.6,
    ps: 3.7,
    profitMargin: 8.2,
    roe: 22.8,
    debtEquity: 55.04,
    dcfValue: 195.0,
    dcfUpside: -14.72,
  },
  META: {
    price: 612.3,
    marketCap: "$1.55T",
    forwardPE: 24.1,
    ps: 10.5,
    profitMargin: 35.9,
    roe: 33.9,
    debtEquity: 26.78,
    dcfValue: 580.0,
    dcfUpside: -5.27,
  },
  NVDA: {
    price: 128.91,
    marketCap: "$3.16T",
    forwardPE: 30.6,
    ps: 27.8,
    profitMargin: 55.8,
    roe: 115.6,
    debtEquity: 17.22,
    dcfValue: 95.4,
    dcfUpside: -26.0,
  },
  TSLA: {
    price: 376.44,
    marketCap: "$1.21T",
    forwardPE: 142.3,
    ps: 18.2,
    profitMargin: 7.3,
    roe: 20.5,
    debtEquity: 11.17,
    dcfValue: 88.5,
    dcfUpside: -76.5,
  },
  JPM: {
    price: 262.79,
    marketCap: "$742.6B",
    forwardPE: 14.1,
    ps: 4.8,
    profitMargin: 33.8,
    roe: 17.2,
    debtEquity: 188.64,
    dcfValue: 245.0,
    dcfUpside: -6.77,
  },
};

const perfByWindow: Record<
  TimeWindow,
  Record<DemoTicker, { returnPct: number; volatility: number; maxDrawdown: number }>
> = {
  "1D": {
    AAPL: { returnPct: 0.82, volatility: 1.1, maxDrawdown: -0.4 },
    MSFT: { returnPct: -0.34, volatility: 0.9, maxDrawdown: -0.7 },
    GOOGL: { returnPct: 1.21, volatility: 1.3, maxDrawdown: -0.2 },
    AMZN: { returnPct: 0.56, volatility: 1.2, maxDrawdown: -0.5 },
    META: { returnPct: -0.91, volatility: 1.5, maxDrawdown: -1.1 },
    NVDA: { returnPct: 2.14, volatility: 2.8, maxDrawdown: -0.8 },
    TSLA: { returnPct: -1.67, volatility: 3.2, maxDrawdown: -2.1 },
    JPM: { returnPct: 0.22, volatility: 0.7, maxDrawdown: -0.3 },
  },
  "1W": {
    AAPL: { returnPct: 2.15, volatility: 3.4, maxDrawdown: -1.2 },
    MSFT: { returnPct: 1.08, volatility: 2.8, maxDrawdown: -1.5 },
    GOOGL: { returnPct: 3.44, volatility: 4.1, maxDrawdown: -0.8 },
    AMZN: { returnPct: -0.72, volatility: 3.6, maxDrawdown: -2.3 },
    META: { returnPct: 1.89, volatility: 4.5, maxDrawdown: -1.9 },
    NVDA: { returnPct: 5.31, volatility: 7.2, maxDrawdown: -2.6 },
    TSLA: { returnPct: -3.28, volatility: 8.1, maxDrawdown: -5.4 },
    JPM: { returnPct: 0.94, volatility: 2.1, maxDrawdown: -0.9 },
  },
  "1M": {
    AAPL: { returnPct: 5.32, volatility: 18.4, maxDrawdown: -3.8 },
    MSFT: { returnPct: 3.71, volatility: 16.2, maxDrawdown: -4.1 },
    GOOGL: { returnPct: 8.14, volatility: 21.3, maxDrawdown: -2.9 },
    AMZN: { returnPct: -2.45, volatility: 22.8, maxDrawdown: -7.6 },
    META: { returnPct: 6.23, volatility: 24.1, maxDrawdown: -5.2 },
    NVDA: { returnPct: 12.67, volatility: 42.5, maxDrawdown: -8.4 },
    TSLA: { returnPct: -8.91, volatility: 58.3, maxDrawdown: -14.7 },
    JPM: { returnPct: 2.18, volatility: 14.6, maxDrawdown: -3.2 },
  },
  "1Y": {
    AAPL: { returnPct: 24.56, volatility: 22.1, maxDrawdown: -12.4 },
    MSFT: { returnPct: 18.32, volatility: 20.5, maxDrawdown: -15.8 },
    GOOGL: { returnPct: 32.41, volatility: 25.8, maxDrawdown: -10.2 },
    AMZN: { returnPct: 28.14, volatility: 28.3, maxDrawdown: -18.5 },
    META: { returnPct: 42.67, volatility: 30.2, maxDrawdown: -14.1 },
    NVDA: { returnPct: 85.23, volatility: 52.4, maxDrawdown: -22.8 },
    TSLA: { returnPct: 62.18, volatility: 68.7, maxDrawdown: -35.2 },
    JPM: { returnPct: 14.53, volatility: 18.4, maxDrawdown: -8.6 },
  },
};

export function getDemoRows(
  tickers: DemoTicker[],
  window: TimeWindow,
): DemoRow[] {
  return tickers.map((t) => ({
    symbol: t,
    ...baseData[t],
    ...perfByWindow[window][t],
  }));
}

// ─── Metric groups for interactive demo ─────────────────────────────────────

export type MetricGroup = "valuation" | "profitability" | "performance";

export const metricGroups: Record<
  MetricGroup,
  { label: string; columns: { key: keyof DemoRow; label: string; fmt: string }[] }
> = {
  valuation: {
    label: "Valuation",
    columns: [
      { key: "forwardPE", label: "Fwd P/E", fmt: "x" },
      { key: "ps", label: "P/S", fmt: "x" },
      { key: "dcfValue", label: "DCF Value", fmt: "$" },
      { key: "dcfUpside", label: "DCF Upside", fmt: "%" },
    ],
  },
  profitability: {
    label: "Profitability",
    columns: [
      { key: "profitMargin", label: "Profit Margin", fmt: "%" },
      { key: "roe", label: "ROE", fmt: "%" },
      { key: "debtEquity", label: "Debt/Equity", fmt: "x" },
    ],
  },
  performance: {
    label: "Performance + Risk",
    columns: [
      { key: "returnPct", label: "Return", fmt: "%" },
      { key: "volatility", label: "Volatility", fmt: "%" },
      { key: "maxDrawdown", label: "Max Drawdown", fmt: "%" },
    ],
  },
};

// ─── Deck section mock content (2-3 variations each) ────────────────────────

export interface DeckSectionContent {
  title: string;
  bullets: string[];
  speakerNotes: string;
  claims: { text: string; verified: boolean; timestamp: string }[];
}

export interface DeckSection {
  id: string;
  label: string;
  icon: string;
  variations: DeckSectionContent[];
}

export const deckSections: DeckSection[] = [
  {
    id: "overview",
    label: "Overview + Catalysts",
    icon: "overview",
    variations: [
      {
        title: "Apple Inc. (AAPL): Overview & Near-Term Catalysts",
        bullets: [
          "Apple's Services revenue reached $24.2B in Q4 2025, growing 14% YoY and now representing 26% of total revenue.",
          "iPhone 17 cycle expected to drive a multi-quarter upgrade supercycle with on-device AI features.",
          "Margin expansion driven by Services mix shift. Gross margin improved 180bps YoY to 46.9%.",
          "Catalyst: Vision Pro 2 launch in Q2 2026 could open a new $50B+ spatial computing TAM.",
        ],
        speakerNotes:
          "Focus on the services narrative. This is the margin story Wall Street cares about. The hardware cycle is the catalyst, but services is the thesis.",
        claims: [
          { text: "Services revenue $24.2B", verified: true, timestamp: "Q4 2025 10-Q" },
          { text: "14% YoY growth", verified: true, timestamp: "Q4 2025 earnings" },
          { text: "$50B+ spatial computing TAM", verified: false, timestamp: "Analyst estimate" },
        ],
      },
      {
        title: "Apple Inc. (AAPL): Company Profile & Growth Drivers",
        bullets: [
          "World's most valuable company by market cap ($3.58T) with dominant ecosystem lock-in across 2.2B active devices.",
          "Services segment (App Store, iCloud, Apple TV+, Apple Pay) is the highest-margin business at ~71% gross margin.",
          "AI integration across iOS 19 positions Apple to monetize on-device intelligence without cloud dependency.",
          "Geographic diversification: India revenue up 33% YoY as manufacturing shifts accelerate.",
        ],
        speakerNotes:
          "The ecosystem moat is the key point here. 2.2B devices creates a flywheel that's nearly impossible to replicate.",
        claims: [
          { text: "2.2B active devices", verified: true, timestamp: "WWDC 2025 keynote" },
          { text: "~71% Services gross margin", verified: true, timestamp: "Q4 2025 10-Q" },
          { text: "India revenue up 33% YoY", verified: false, timestamp: "Analyst estimate" },
        ],
      },
    ],
  },
  {
    id: "swot",
    label: "SWOT Analysis",
    icon: "swot",
    variations: [
      {
        title: "SWOT: Apple Inc.",
        bullets: [
          "Strengths: Unmatched brand loyalty, ecosystem lock-in, $162B cash position, and leading ASP in smartphones.",
          "Weaknesses: Revenue concentration in iPhone (~52%), limited AI cloud infrastructure vs. peers, China regulatory risk.",
          "Opportunities: Services monetization runway, spatial computing first-mover, healthcare wearables expansion.",
          "Threats: DOJ antitrust case on App Store, EU DMA compliance costs, Huawei resurgence in China market.",
        ],
        speakerNotes:
          "The SWOT is balanced. Don't oversell strengths. The antitrust risk is real and worth addressing in Q&A prep.",
        claims: [
          { text: "$162B cash position", verified: true, timestamp: "Q4 2025 balance sheet" },
          { text: "iPhone ~52% of revenue", verified: true, timestamp: "Q4 2025 10-Q" },
          { text: "DOJ antitrust case", verified: true, timestamp: "Public filing 2025" },
        ],
      },
      {
        title: "SWOT Matrix: AAPL Strategic Position",
        bullets: [
          "Strengths: Best-in-class supply chain (70+ day inventory turns), premium pricing power, and R&D spend of $31B/yr.",
          "Weaknesses: Late to generative AI race, declining China market share (17% → 14%), hardware growth plateauing.",
          "Opportunities: Apple Intelligence monetization, Financial Services expansion (Apple Card, Savings), B2B device management.",
          "Threats: Samsung Galaxy AI competitive response, regulatory fragmentation (EU/US/India), macro consumer weakness.",
        ],
        speakerNotes:
          "Emphasize the supply chain as an underappreciated strength. R&D spend signals commitment to the next platform.",
        claims: [
          { text: "R&D spend of $31B/yr", verified: true, timestamp: "FY2025 10-K" },
          { text: "China share 17% → 14%", verified: false, timestamp: "IDC estimate Q3 2025" },
          { text: "70+ day inventory turns", verified: false, timestamp: "Analyst calculation" },
        ],
      },
    ],
  },
  {
    id: "bull",
    label: "Bull Case",
    icon: "bull",
    variations: [
      {
        title: "Bull Case: Why AAPL Could Reach $280+",
        bullets: [
          "Services revenue growing 14% CAGR reaches $120B by FY2028 at 70%+ margins, driving EPS expansion.",
          "iPhone 17 AI features trigger largest upgrade cycle since iPhone 6, adding $15B+ incremental revenue.",
          "Vision Pro ecosystem matures: 10K+ spatial apps by 2027, enterprise adoption accelerating.",
          "Share buyback machine: $100B+ annual repurchase reduces float, supporting 12-15% EPS growth even with flat revenue.",
        ],
        speakerNotes:
          "The bull case rests on multiple expansion from services mix shift. If Services hits 35% of revenue, the multiple re-rates to 35x+.",
        claims: [
          { text: "$120B Services by FY2028", verified: false, timestamp: "Bull projection" },
          { text: "$100B+ annual buyback", verified: true, timestamp: "FY2025 capital return" },
          { text: "10K+ spatial apps by 2027", verified: false, timestamp: "Projection" },
        ],
      },
      {
        title: "Bull Thesis: AAPL Upside Scenario",
        bullets: [
          "On-device AI creates a new monetization layer: $5-10/month Apple Intelligence Pro subscription (500M+ potential subs).",
          "India becomes the next China-scale growth market: 700M smartphone users, Apple at <5% share today.",
          "Healthcare pivot: Apple Watch FDA-cleared glucose monitoring could unlock $30B+ digital health TAM.",
          "Multiple expansion: market rewards predictable, high-margin recurring revenue, 38-40x forward P/E justified.",
        ],
        speakerNotes:
          "India TAM is the most overlooked bull argument. Start here to differentiate your pitch from consensus.",
        claims: [
          { text: "700M smartphone users in India", verified: true, timestamp: "GSMA 2025" },
          { text: "Apple at <5% India share", verified: true, timestamp: "Counterpoint Q3 2025" },
          { text: "FDA-cleared glucose monitoring", verified: false, timestamp: "Rumor/patent filings" },
        ],
      },
    ],
  },
  {
    id: "bear",
    label: "Bear Case",
    icon: "bear",
    variations: [
      {
        title: "Bear Case: Downside Risks for AAPL",
        bullets: [
          "DOJ antitrust ruling forces App Store fee reduction from 30% to 15%, cutting Services revenue by $8-12B annually.",
          "China revenue (18% of total) at risk from nationalism trends and Huawei's AI-powered smartphone resurgence.",
          "AI strategy lags: Apple Intelligence perceived as inferior to Google/OpenAI, eroding premium positioning.",
          "Consumer spending slowdown: iPhone ASPs at $950+ are vulnerable to trade-down in a recession.",
        ],
        speakerNotes:
          "Quantify the App Store risk. It's the bear case that matters most. Model a 15% fee scenario to show EPS impact.",
        claims: [
          { text: "App Store 30% fee", verified: true, timestamp: "Current policy" },
          { text: "China 18% of revenue", verified: true, timestamp: "Q4 2025 geographic" },
          { text: "iPhone ASPs at $950+", verified: true, timestamp: "Q4 2025 blended" },
        ],
      },
      {
        title: "Bear Thesis: What Could Go Wrong",
        bullets: [
          "Hardware innovation plateau: iPhone, Mac, and iPad cycles elongating, consumers refreshing every 4+ years.",
          "Regulatory cascading: EU DMA + Japan + India all imposing sideloading and payment alternatives, death by a thousand cuts.",
          "Vision Pro disappoints: $3,499 price point limits TAM, developer ecosystem fails to reach escape velocity.",
          "Talent attrition: key AI/ML researchers leaving for startups and competitors offering better equity packages.",
        ],
        speakerNotes:
          "The elongating refresh cycle is subtle but important. It means hardware revenue becomes ex-growth sooner than consensus expects.",
        claims: [
          { text: "4+ year refresh cycle", verified: false, timestamp: "Industry surveys" },
          { text: "Vision Pro $3,499", verified: true, timestamp: "Apple.com pricing" },
          { text: "EU DMA compliance", verified: true, timestamp: "March 2024 enforcement" },
        ],
      },
    ],
  },
  {
    id: "relative",
    label: "Relative Valuation",
    icon: "relative",
    variations: [
      {
        title: "Relative Valuation: AAPL vs. Mega-Cap Tech Peers",
        bullets: [
          "AAPL trades at 31.2x forward P/E vs. peer median of 28.4x, a 10% premium justified by margin stability.",
          "EV/Revenue of 9.1x vs. peer median 8.2x reflects Services mix shift and buyback-enhanced returns.",
          "Peer group: MSFT (33.8x), GOOGL (22.4x), AMZN (37.6x), META (24.1x). AAPL sits mid-range.",
          "Key differentiator: AAPL's 26.3% net margin with 157% ROE vs. peer median 28% margin, 37% ROE.",
        ],
        speakerNotes:
          "The relative val table is your strongest slide. Let the numbers speak. Point out that AAPL's premium is smaller than it looks once you adjust for buyback yield.",
        claims: [
          { text: "31.2x forward P/E", verified: true, timestamp: "Live market data" },
          { text: "Peer median 28.4x", verified: true, timestamp: "Computed from comps" },
          { text: "157% ROE", verified: true, timestamp: "TTM calculation" },
        ],
      },
      {
        title: "Peer Comparison: Valuation Multiples",
        bullets: [
          "On P/S basis, AAPL (9.1x) is cheaper than MSFT (14.3x) and NVDA (27.8x) but pricier than GOOGL (7.8x).",
          "Debt/Equity: AAPL's 151.9% looks high but is intentional leverage for buybacks, net cash positive at $62B.",
          "Beta of 1.08 indicates AAPL trades roughly in line with the market, defensive for mega-cap tech.",
          "DCF intrinsic value of $192.10 suggests 19% downside from current price, consensus still overweight.",
        ],
        speakerNotes:
          "Address the debt/equity concern proactively. Explain that Apple's leverage is a capital allocation choice, not distress.",
        claims: [
          { text: "Net cash $62B", verified: true, timestamp: "Q4 2025 balance sheet" },
          { text: "DCF value $192.10", verified: true, timestamp: "Computed (5yr, 9% WACC)" },
          { text: "Beta 1.08", verified: true, timestamp: "5Y monthly regression" },
        ],
      },
    ],
  },
  {
    id: "dcf",
    label: "DCF Breakdown",
    icon: "dcf",
    variations: [
      {
        title: "DCF Valuation: Base Case Assumptions",
        bullets: [
          "5-year forecast period with 8% FCF growth rate (conservative vs. 12% historical CAGR).",
          "WACC of 9.0% based on CAPM: risk-free 4.2%, equity premium 5.5%, beta 1.08.",
          "Terminal growth rate: 2.5% (GDP+ assumption for platform with recurring revenue).",
          "Implied target price: $192.10/share, represents 19.1% downside from current $237.42.",
        ],
        speakerNotes:
          "Walk through each assumption. The 8% FCF growth is the key lever. Show sensitivity table for 6%/8%/10% scenarios.",
        claims: [
          { text: "8% FCF growth rate", verified: true, timestamp: "Model assumption" },
          { text: "9.0% WACC", verified: true, timestamp: "CAPM computation" },
          { text: "12% historical FCF CAGR", verified: true, timestamp: "5Y FCF history" },
        ],
      },
      {
        title: "Discounted Cash Flow: Sensitivity Analysis",
        bullets: [
          "Base case ($192.10): 8% growth, 9% WACC, 2.5% terminal, 19% downside.",
          "Bull case ($268.50): 12% growth, 8.5% WACC, 3% terminal, 13% upside.",
          "Bear case ($142.30): 5% growth, 10% WACC, 2% terminal, 40% downside.",
          "Terminal value represents 72% of total DCF, typical for mature, high-quality compounder.",
        ],
        speakerNotes:
          "The sensitivity table is critical. Professors will ask about terminal value dominance. Explain it's expected for a mature business.",
        claims: [
          { text: "Terminal value 72% of DCF", verified: true, timestamp: "Model output" },
          { text: "Bull case $268.50", verified: true, timestamp: "Scenario analysis" },
          { text: "Bear case $142.30", verified: true, timestamp: "Scenario analysis" },
        ],
      },
    ],
  },
];

// ─── Pricing tiers (source of truth for landing page) ───────────────────────

export const TIERS = {
  free: {
    name: "Free",
    price: "$0",
    period: "forever",
    comparesPerMonth: 5,
    decksPerMonth: 3,
    features: [
      { text: "5 compares / month", included: true },
      { text: "3 decks / month", included: true },
      { text: "DCF valuation", included: true },
      { text: "Auto model selection", included: true },
      { text: "Export to CSV, XLSX, PDF, PPTX", included: false },
    ],
  },
  pro: {
    name: "Pro",
    price: "$29",
    period: "/month",
    comparesPerMonth: Infinity,
    decksPerMonth: 100,
    features: [
      { text: "Unlimited compares", included: true },
      { text: "100 decks / month", included: true },
      { text: "DCF valuation", included: true },
      { text: "All models: GPT-5.2, Claude Sonnet 4.5, Gemini 3 Pro", included: true },
      { text: "All exports: CSV, XLSX, PDF, PPTX", included: true },
    ],
  },
} as const;

export const MODELS = [
  "GPT-5.2",
  "Claude Sonnet 4.5",
  "Gemini 3 Pro",
] as const;
