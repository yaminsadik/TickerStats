"""
DCF Valuation Service with two implementations:
1. SimpleDCF - Fast, reliable for relative table (never crashes)
2. FullDCF - Comprehensive for deck generation (bulletproof version)

Based on: https://github.com/user/dcf-model with significant improvements
for error handling and reliability.
"""

import logging
import math
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def safe_float(val) -> Optional[float]:
    """Convert value to float safely, returning None for invalid values."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def safe_get(data: dict, *keys, default=None):
    """Safely get dictionary value with multiple fallback keys."""
    if data is None:
        return default
    for key in keys:
        if key in data and data[key] is not None:
            val = safe_float(data[key])
            if val is not None:
                return val
    return default


def safe_loc(df: pd.DataFrame, *row_names) -> Optional[pd.Series]:
    """Safely get row from DataFrame with multiple fallback row names."""
    if df is None or df.empty:
        return None
    for name in row_names:
        if name in df.index:
            try:
                row = df.loc[name]
                # Filter out NaN values
                if isinstance(row, pd.Series):
                    return row.dropna()
                return row
            except Exception:
                continue
    return None


def safe_series_values(series: Optional[pd.Series], count: int = 4) -> List[float]:
    """Get first N non-null values from a series."""
    if series is None:
        return []
    values = []
    for val in series:
        f = safe_float(val)
        if f is not None:
            values.append(f)
            if len(values) >= count:
                break
    return values


def weighted_average(values: List[float], max_weights: int = 4) -> Optional[float]:
    """Calculate weighted average with more recent values weighted higher."""
    if not values:
        return None
    
    n = min(len(values), max_weights)
    if n == 0:
        return None
    
    # Weights: [0.4, 0.3, 0.2, 0.1] for 4 values, adjusted for fewer
    weight_templates = {
        1: [1.0],
        2: [0.6, 0.4],
        3: [0.5, 0.3, 0.2],
        4: [0.4, 0.3, 0.2, 0.1],
    }
    weights = weight_templates.get(n, weight_templates[4][:n])
    
    try:
        return float(np.average(values[:n], weights=weights))
    except Exception:
        return sum(values[:n]) / n if values[:n] else None


# =============================================================================
# SIMPLE DCF - For Relative Table (Fast & Reliable)
# =============================================================================

@dataclass
class SimpleDCFResult:
    """Result from simple DCF calculation."""
    dcf_price: Optional[float] = None
    current_price: Optional[float] = None
    upside: Optional[float] = None  # Percentage upside/downside
    fcf: Optional[float] = None  # Free cash flow used
    growth_rate: Optional[float] = None  # Growth rate used
    wacc: Optional[float] = None  # WACC used
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'dcfPrice': self.dcf_price,
            'currentPrice': self.current_price,
            'dcfUpside': self.upside,
            'fcf': self.fcf,
            'growthRate': self.growth_rate,
            'wacc': self.wacc,
            'dcfError': self.error,
        }


def calculate_simple_dcf(
    ticker: str,
    wacc: float = 0.09,  # Default 9% WACC
    terminal_growth: float = 0.025,  # Default 2.5% terminal growth
    projection_years: int = 5,
) -> SimpleDCFResult:
    """
    Calculate simple DCF valuation using yfinance data.
    
    This is the RELIABLE version for the relative table.
    - Uses pre-calculated FCF from yfinance
    - Falls back to operating cash flow - capex if FCF not available
    - Uses historical revenue growth or defaults to conservative estimate
    - Never crashes - returns None values gracefully
    
    Args:
        ticker: Stock ticker symbol
        wacc: Weighted average cost of capital (default 9%)
        terminal_growth: Terminal growth rate (default 2.5%)
        projection_years: Years to project (default 5)
    
    Returns:
        SimpleDCFResult with DCF price and upside/downside
    """
    result = SimpleDCFResult()
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            result.error = "No data available"
            return result
        
        # Get current price
        result.current_price = safe_get(
            info, 'currentPrice', 'regularMarketPrice', 'previousClose'
        )
        if result.current_price is None:
            result.error = "No price data"
            return result
        
        # Get shares outstanding
        shares = safe_get(info, 'sharesOutstanding')
        if shares is None or shares <= 0:
            result.error = "No shares data"
            return result
        
        # Get Free Cash Flow (try multiple sources)
        fcf = safe_get(info, 'freeCashflow')
        
        # Fallback: Calculate from cash flow statement
        if fcf is None:
            try:
                cashflow = stock.cashflow
                if cashflow is not None and not cashflow.empty:
                    # Try to get operating cash flow
                    ocf_row = safe_loc(
                        cashflow,
                        'Operating Cash Flow',
                        'Total Cash From Operating Activities',
                        'Cash Flow From Operating Activities'
                    )
                    capex_row = safe_loc(
                        cashflow,
                        'Capital Expenditure',
                        'Capital Expenditures'
                    )
                    
                    if ocf_row is not None and len(ocf_row) > 0:
                        ocf = safe_float(ocf_row.iloc[0])
                        capex = 0
                        if capex_row is not None and len(capex_row) > 0:
                            capex = abs(safe_float(capex_row.iloc[0]) or 0)
                        if ocf is not None:
                            fcf = ocf - capex
            except Exception as e:
                logger.debug(f"Could not calculate FCF from statements: {e}")
        
        if fcf is None or fcf <= 0:
            # Last resort: estimate from operating cash flow
            fcf = safe_get(info, 'operatingCashflow')
            if fcf is not None:
                fcf = fcf * 0.7  # Conservative estimate (30% goes to capex)
        
        if fcf is None or fcf <= 0:
            result.error = "No FCF data"
            return result
        
        result.fcf = fcf
        
        # Get growth rate (try multiple sources)
        growth = safe_get(info, 'revenueGrowth', 'earningsGrowth')
        
        # Cap growth rate at reasonable bounds
        if growth is not None:
            growth = max(min(growth, 0.30), -0.10)  # Cap between -10% and 30%
        else:
            # Default to conservative 5% growth
            growth = 0.05
        
        # Decay growth rate over projection period
        # Start at growth, decay to terminal_growth by year 5
        growth_rates = []
        for i in range(projection_years):
            year_growth = growth - (growth - terminal_growth) * (i / projection_years)
            growth_rates.append(year_growth)
        
        result.growth_rate = growth
        result.wacc = wacc
        
        # Calculate projected FCF and discount
        projected_fcf = []
        current_fcf = fcf
        
        for i, g in enumerate(growth_rates):
            current_fcf = current_fcf * (1 + g)
            projected_fcf.append(current_fcf)
        
        # Discount projected FCF
        pv_fcf = sum(
            fcf_val / ((1 + wacc) ** (i + 1))
            for i, fcf_val in enumerate(projected_fcf)
        )
        
        # Terminal value
        terminal_value = projected_fcf[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
        pv_terminal = terminal_value / ((1 + wacc) ** projection_years)
        
        # Enterprise value
        enterprise_value = pv_fcf + pv_terminal
        
        # Equity value (EV - debt + cash)
        total_debt = safe_get(info, 'totalDebt') or 0
        total_cash = safe_get(info, 'totalCash') or 0
        
        equity_value = enterprise_value - total_debt + total_cash
        
        # Per share value
        dcf_price = equity_value / shares
        
        # Sanity check - DCF should be positive and not absurdly high
        if dcf_price <= 0:
            result.error = "Negative DCF value"
            return result
        
        if dcf_price > result.current_price * 10:
            # Cap at 10x current price (likely bad inputs)
            dcf_price = result.current_price * 10
        
        result.dcf_price = round(dcf_price, 2)
        result.upside = round((dcf_price / result.current_price - 1) * 100, 2)
        
        return result
        
    except Exception as e:
        logger.error(f"SimpleDCF error for {ticker}: {e}")
        result.error = str(e)[:50]
        return result


# =============================================================================
# FULL DCF - For Deck Generation (Comprehensive & Bulletproof)
# =============================================================================

@dataclass
class FullDCFResult:
    """Comprehensive result from full DCF calculation."""
    # Core results
    implied_share_price: Optional[float] = None
    current_price: Optional[float] = None
    margin_of_safety: Optional[float] = None  # Percentage
    
    # Valuation components
    enterprise_value: Optional[float] = None
    equity_value: Optional[float] = None
    terminal_value: Optional[float] = None
    pv_fcf_total: Optional[float] = None
    pv_terminal: Optional[float] = None
    
    # Key inputs
    wacc: Optional[float] = None
    cost_of_equity: Optional[float] = None
    cost_of_debt: Optional[float] = None
    tax_rate: Optional[float] = None
    terminal_growth_rate: float = 0.025
    beta: Optional[float] = None
    risk_free_rate: Optional[float] = None
    market_return: Optional[float] = None
    
    # Financial data
    market_cap: Optional[float] = None
    total_debt: Optional[float] = None
    total_cash: Optional[float] = None
    shares_outstanding: Optional[float] = None
    
    # Projections (5 years)
    projected_revenue: List[float] = field(default_factory=list)
    projected_ebit: List[float] = field(default_factory=list)
    projected_fcf: List[float] = field(default_factory=list)
    discounted_fcf: List[float] = field(default_factory=list)
    
    # Margins used
    ebit_margin: Optional[float] = None
    da_margin: Optional[float] = None
    capex_margin: Optional[float] = None
    nwc_margin: Optional[float] = None
    
    # Reverse DCF
    implied_growth_rate: Optional[float] = None
    
    # Status
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'impliedSharePrice': self.implied_share_price,
            'currentPrice': self.current_price,
            'marginOfSafety': self.margin_of_safety,
            'enterpriseValue': self.enterprise_value,
            'equityValue': self.equity_value,
            'terminalValue': self.terminal_value,
            'pvFcfTotal': self.pv_fcf_total,
            'pvTerminal': self.pv_terminal,
            'wacc': self.wacc,
            'costOfEquity': self.cost_of_equity,
            'costOfDebt': self.cost_of_debt,
            'taxRate': self.tax_rate,
            'terminalGrowthRate': self.terminal_growth_rate,
            'beta': self.beta,
            'riskFreeRate': self.risk_free_rate,
            'marketReturn': self.market_return,
            'marketCap': self.market_cap,
            'totalDebt': self.total_debt,
            'totalCash': self.total_cash,
            'sharesOutstanding': self.shares_outstanding,
            'projectedRevenue': self.projected_revenue,
            'projectedEbit': self.projected_ebit,
            'projectedFcf': self.projected_fcf,
            'discountedFcf': self.discounted_fcf,
            'ebitMargin': self.ebit_margin,
            'daMargin': self.da_margin,
            'capexMargin': self.capex_margin,
            'nwcMargin': self.nwc_margin,
            'impliedGrowthRate': self.implied_growth_rate,
            'error': self.error,
            'warnings': self.warnings,
        }


class FullDCFModel:
    """
    Comprehensive DCF Model - Bulletproof version for deck generation.
    
    Based on the GitHub code but with extensive error handling to never crash.
    Uses proper WACC calculation, analyst estimates when available, and
    historical margins for projections.
    """
    
    # Default assumptions when data is missing
    DEFAULT_WACC = 0.09
    DEFAULT_TERMINAL_GROWTH = 0.025
    DEFAULT_TAX_RATE = 0.21
    DEFAULT_RISK_FREE = 0.045  # ~4.5%
    DEFAULT_MARKET_RETURN = 0.10  # ~10%
    DEFAULT_BETA = 1.0
    DEFAULT_GROWTH = 0.05
    
    def __init__(
        self,
        ticker: str,
        terminal_growth_rate: float = 0.025,
        risk_free_ticker: str = "^TNX",
        market_ticker: str = "SPY",
    ):
        self.ticker = ticker.upper()
        self.terminal_growth_rate = terminal_growth_rate
        self.risk_free_ticker = risk_free_ticker
        self.market_ticker = market_ticker
        
        # Initialize result
        self.result = FullDCFResult(terminal_growth_rate=terminal_growth_rate)
        
        # Data containers
        self.stock = None
        self.info = {}
        self.income_stmt = None
        self.balance_sheet = None
        self.cashflow = None
        
        # Weights for historical averages
        self.weights_4 = [0.4, 0.3, 0.2, 0.1]
        self.weights_3 = [0.5, 0.3, 0.2]
    
    def calculate(self) -> FullDCFResult:
        """Run the full DCF calculation."""
        try:
            # Step 1: Load data
            if not self._load_data():
                return self.result
            
            # Step 2: Get basic info
            self._get_basic_info()
            
            # Step 3: Calculate WACC
            self._calculate_wacc()
            
            # Step 4: Project financials
            self._project_revenue()
            self._project_ebit()
            self._project_fcf()
            
            # Step 5: Calculate DCF
            self._calculate_dcf()
            
            # Step 6: Calculate implied share price
            self._calculate_implied_price()
            
            # Step 7: Reverse DCF (implied growth rate)
            self._calculate_implied_growth()
            
            return self.result
            
        except Exception as e:
            logger.error(f"FullDCF error for {self.ticker}: {e}")
            self.result.error = f"Calculation error: {str(e)[:100]}"
            return self.result
    
    def _load_data(self) -> bool:
        """Load all data from yfinance."""
        try:
            self.stock = yf.Ticker(self.ticker)
            self.info = self.stock.info or {}
            
            if not self.info:
                self.result.error = "No data available for ticker"
                return False
            
            # Load financial statements (with error handling)
            try:
                self.income_stmt = self.stock.financials
            except Exception:
                self.result.warnings.append("Could not load income statement")
            
            try:
                self.balance_sheet = self.stock.balance_sheet
            except Exception:
                self.result.warnings.append("Could not load balance sheet")
            
            try:
                self.cashflow = self.stock.cashflow
            except Exception:
                self.result.warnings.append("Could not load cash flow statement")
            
            return True
            
        except Exception as e:
            self.result.error = f"Failed to load data: {str(e)[:50]}"
            return False
    
    def _get_basic_info(self):
        """Extract basic company info."""
        self.result.current_price = safe_get(
            self.info, 'currentPrice', 'regularMarketPrice', 'previousClose'
        )
        self.result.market_cap = safe_get(self.info, 'marketCap')
        self.result.total_debt = safe_get(self.info, 'totalDebt') or 0
        self.result.total_cash = safe_get(self.info, 'totalCash') or 0
        self.result.shares_outstanding = safe_get(self.info, 'sharesOutstanding')
        self.result.beta = safe_get(self.info, 'beta') or self.DEFAULT_BETA
        
        if self.result.shares_outstanding is None or self.result.shares_outstanding <= 0:
            self.result.error = "Missing shares outstanding"
    
    def _calculate_wacc(self):
        """Calculate Weighted Average Cost of Capital."""
        try:
            # Get risk-free rate
            try:
                rf_ticker = yf.Ticker(self.risk_free_ticker)
                rf_info = rf_ticker.info
                self.result.risk_free_rate = safe_get(
                    rf_info, 'previousClose', 'regularMarketPrice'
                )
                if self.result.risk_free_rate:
                    self.result.risk_free_rate = self.result.risk_free_rate / 100
            except Exception:
                pass
            
            if self.result.risk_free_rate is None:
                self.result.risk_free_rate = self.DEFAULT_RISK_FREE
                self.result.warnings.append("Using default risk-free rate")
            
            # Get market return
            try:
                market_ticker = yf.Ticker(self.market_ticker)
                market_info = market_ticker.info
                self.result.market_return = safe_get(
                    market_info, 'threeYearAverageReturn', 'fiveYearAverageReturn'
                )
            except Exception:
                pass
            
            if self.result.market_return is None:
                self.result.market_return = self.DEFAULT_MARKET_RETURN
                self.result.warnings.append("Using default market return")
            
            # Cost of equity (CAPM)
            beta = self.result.beta or self.DEFAULT_BETA
            rf = self.result.risk_free_rate
            mr = self.result.market_return
            
            self.result.cost_of_equity = rf + beta * (mr - rf)
            
            # Cost of debt
            interest_expense = None
            if self.income_stmt is not None:
                interest_row = safe_loc(
                    self.income_stmt,
                    'Interest Expense',
                    'Interest Expense Non Operating',
                    'Net Interest Income'
                )
                if interest_row is not None and len(interest_row) > 0:
                    interest_expense = abs(safe_float(interest_row.iloc[0]))
            
            if interest_expense and self.result.total_debt and self.result.total_debt > 0:
                self.result.cost_of_debt = interest_expense / self.result.total_debt
            else:
                self.result.cost_of_debt = rf + 0.02  # Risk-free + 2% spread
                self.result.warnings.append("Estimated cost of debt")
            
            # Tax rate
            self._calculate_tax_rate()
            
            # WACC calculation
            if self.result.market_cap and self.result.market_cap > 0:
                total_value = self.result.market_cap + (self.result.total_debt or 0)
                weight_equity = self.result.market_cap / total_value
                weight_debt = (self.result.total_debt or 0) / total_value
                
                tax = self.result.tax_rate or self.DEFAULT_TAX_RATE
                
                self.result.wacc = (
                    weight_equity * self.result.cost_of_equity +
                    weight_debt * self.result.cost_of_debt * (1 - tax)
                )
            else:
                self.result.wacc = self.DEFAULT_WACC
                self.result.warnings.append("Using default WACC")
            
            # Sanity check WACC
            if self.result.wacc < 0.05:
                self.result.wacc = 0.05
            elif self.result.wacc > 0.20:
                self.result.wacc = 0.20
                
        except Exception as e:
            logger.warning(f"WACC calculation error: {e}")
            self.result.wacc = self.DEFAULT_WACC
            self.result.warnings.append("WACC calculation failed, using default")
    
    def _calculate_tax_rate(self):
        """Calculate effective tax rate from financial statements."""
        if self.income_stmt is None:
            self.result.tax_rate = self.DEFAULT_TAX_RATE
            return
        
        try:
            tax_row = safe_loc(
                self.income_stmt,
                'Tax Provision',
                'Income Tax Expense',
                'Tax Expense'
            )
            ebit_row = safe_loc(
                self.income_stmt,
                'EBIT',
                'Operating Income',
                'Operating Profit'
            )
            
            if tax_row is not None and ebit_row is not None:
                tax_values = safe_series_values(tax_row, 3)
                ebit_values = safe_series_values(ebit_row, 3)
                
                if tax_values and ebit_values:
                    rates = []
                    for t, e in zip(tax_values, ebit_values):
                        if e != 0:
                            rate = abs(t / e)
                            if 0 < rate < 0.5:  # Sanity check
                                rates.append(rate)
                    
                    if rates:
                        self.result.tax_rate = weighted_average(rates, 3)
                        return
            
            self.result.tax_rate = self.DEFAULT_TAX_RATE
            
        except Exception:
            self.result.tax_rate = self.DEFAULT_TAX_RATE
    
    def _project_revenue(self):
        """Project future revenue."""
        try:
            # Try to get analyst estimates first
            revenue_growth = None
            base_revenue = None
            
            try:
                estimates = self.stock.revenue_estimate
                if estimates is not None and not estimates.empty:
                    if '0y' in estimates.index:
                        base_revenue = safe_float(estimates.loc['0y', 'avg'])
                    if '+1y' in estimates.index:
                        revenue_growth = safe_float(estimates.loc['+1y', 'growth'])
            except Exception:
                pass
            
            # Fallback to historical revenue
            if base_revenue is None:
                base_revenue = safe_get(self.info, 'totalRevenue', 'revenue')
            
            if base_revenue is None and self.income_stmt is not None:
                rev_row = safe_loc(
                    self.income_stmt,
                    'Total Revenue',
                    'Revenue',
                    'Net Sales'
                )
                if rev_row is not None and len(rev_row) > 0:
                    base_revenue = safe_float(rev_row.iloc[0])
            
            if base_revenue is None:
                self.result.error = "Could not determine revenue"
                return
            
            # Get growth rate
            if revenue_growth is None:
                revenue_growth = safe_get(self.info, 'revenueGrowth')
            
            if revenue_growth is None:
                revenue_growth = self.DEFAULT_GROWTH
                self.result.warnings.append("Using default growth rate")
            
            # Cap growth rate
            revenue_growth = max(min(revenue_growth, 0.30), -0.10)
            
            # Project 5 years with decaying growth
            self.result.projected_revenue = []
            current_rev = base_revenue
            
            for i in range(5):
                # Decay growth towards terminal rate
                year_growth = revenue_growth - (revenue_growth - self.terminal_growth_rate) * (i / 5)
                current_rev = current_rev * (1 + year_growth)
                self.result.projected_revenue.append(current_rev)
                
        except Exception as e:
            logger.warning(f"Revenue projection error: {e}")
            self.result.warnings.append("Revenue projection failed")
    
    def _project_ebit(self):
        """Project future EBIT using historical margins."""
        if not self.result.projected_revenue:
            return
        
        try:
            # Calculate historical EBIT margin
            if self.income_stmt is not None:
                ebit_row = safe_loc(
                    self.income_stmt,
                    'EBIT',
                    'Operating Income',
                    'Operating Profit'
                )
                rev_row = safe_loc(
                    self.income_stmt,
                    'Total Revenue',
                    'Revenue'
                )
                
                if ebit_row is not None and rev_row is not None:
                    ebit_values = safe_series_values(ebit_row, 4)
                    rev_values = safe_series_values(rev_row, 4)
                    
                    if ebit_values and rev_values:
                        margins = []
                        for e, r in zip(ebit_values, rev_values):
                            if r != 0:
                                margin = e / r
                                if -0.5 < margin < 0.5:  # Sanity check
                                    margins.append(margin)
                        
                        if margins:
                            self.result.ebit_margin = weighted_average(margins)
            
            # Fallback to info
            if self.result.ebit_margin is None:
                op_margin = safe_get(self.info, 'operatingMargins')
                if op_margin:
                    self.result.ebit_margin = op_margin
                else:
                    self.result.ebit_margin = 0.15  # Default 15%
                    self.result.warnings.append("Using default EBIT margin")
            
            # Project EBIT
            self.result.projected_ebit = [
                rev * self.result.ebit_margin
                for rev in self.result.projected_revenue
            ]
            
        except Exception as e:
            logger.warning(f"EBIT projection error: {e}")
    
    def _project_fcf(self):
        """Project free cash flow."""
        if not self.result.projected_revenue or not self.result.projected_ebit:
            return
        
        try:
            # Calculate historical margins for D&A, CapEx, NWC
            if self.cashflow is not None and self.income_stmt is not None:
                rev_row = safe_loc(self.income_stmt, 'Total Revenue', 'Revenue')
                rev_values = safe_series_values(rev_row, 4) if rev_row is not None else []
                
                # D&A margin
                da_row = safe_loc(
                    self.cashflow,
                    'Depreciation And Amortization',
                    'Depreciation',
                    'Depreciation & Amortization'
                )
                if da_row is not None and rev_values:
                    da_values = [abs(v) for v in safe_series_values(da_row, 4)]
                    if da_values:
                        margins = [d/r for d, r in zip(da_values, rev_values) if r != 0]
                        self.result.da_margin = weighted_average(margins)
                
                # CapEx margin
                capex_row = safe_loc(
                    self.cashflow,
                    'Capital Expenditure',
                    'Capital Expenditures',
                    'Purchase Of PPE'
                )
                if capex_row is not None and rev_values:
                    capex_values = [abs(v) for v in safe_series_values(capex_row, 4)]
                    if capex_values:
                        margins = [c/r for c, r in zip(capex_values, rev_values) if r != 0]
                        self.result.capex_margin = weighted_average(margins)
                
                # NWC margin
                nwc_row = safe_loc(
                    self.cashflow,
                    'Change In Working Capital',
                    'Changes In Working Capital'
                )
                if nwc_row is not None and rev_values:
                    nwc_values = safe_series_values(nwc_row, 4)
                    if nwc_values:
                        margins = [n/r for n, r in zip(nwc_values, rev_values) if r != 0]
                        self.result.nwc_margin = weighted_average(margins)
            
            # Set defaults if missing
            if self.result.da_margin is None:
                self.result.da_margin = 0.05  # 5% of revenue
            if self.result.capex_margin is None:
                self.result.capex_margin = 0.05  # 5% of revenue
            if self.result.nwc_margin is None:
                self.result.nwc_margin = 0.01  # 1% of revenue
            
            # Calculate FCF for each year
            tax_rate = self.result.tax_rate or self.DEFAULT_TAX_RATE
            
            self.result.projected_fcf = []
            for i, (rev, ebit) in enumerate(zip(
                self.result.projected_revenue,
                self.result.projected_ebit
            )):
                # EBIAT (EBIT after tax)
                ebiat = ebit * (1 - tax_rate)
                
                # Add back D&A
                da = rev * self.result.da_margin
                
                # Subtract CapEx
                capex = rev * self.result.capex_margin
                
                # Subtract change in NWC
                nwc = rev * self.result.nwc_margin
                
                # FCF = EBIAT + D&A - CapEx - NWC
                fcf = ebiat + da - capex - nwc
                self.result.projected_fcf.append(fcf)
                
        except Exception as e:
            logger.warning(f"FCF projection error: {e}")
    
    def _calculate_dcf(self):
        """Calculate discounted cash flow and terminal value."""
        if not self.result.projected_fcf or self.result.wacc is None:
            return
        
        try:
            wacc = self.result.wacc
            
            # Discount projected FCF
            self.result.discounted_fcf = []
            for i, fcf in enumerate(self.result.projected_fcf):
                # Mid-year convention
                discount_factor = (1 + wacc) ** (i + 0.5)
                pv = fcf / discount_factor
                self.result.discounted_fcf.append(pv)
            
            self.result.pv_fcf_total = sum(self.result.discounted_fcf)
            
            # Terminal value
            final_fcf = self.result.projected_fcf[-1]
            tgr = self.terminal_growth_rate
            
            self.result.terminal_value = (
                final_fcf * (1 + tgr) / (wacc - tgr)
            )
            
            # Discount terminal value
            self.result.pv_terminal = (
                self.result.terminal_value / ((1 + wacc) ** 5)
            )
            
            # Enterprise value
            self.result.enterprise_value = (
                self.result.pv_fcf_total + self.result.pv_terminal
            )
            
        except Exception as e:
            logger.warning(f"DCF calculation error: {e}")
    
    def _calculate_implied_price(self):
        """Calculate implied share price from enterprise value."""
        if self.result.enterprise_value is None:
            return
        
        if self.result.shares_outstanding is None or self.result.shares_outstanding <= 0:
            return
        
        try:
            # Equity value = EV - Debt + Cash
            self.result.equity_value = (
                self.result.enterprise_value -
                (self.result.total_debt or 0) +
                (self.result.total_cash or 0)
            )
            
            # Per share
            self.result.implied_share_price = (
                self.result.equity_value / self.result.shares_outstanding
            )
            
            # Sanity check
            if self.result.implied_share_price < 0:
                self.result.implied_share_price = None
                self.result.error = "Negative implied price"
                return
            
            # Cap at reasonable multiple of current price
            if self.result.current_price and self.result.implied_share_price > self.result.current_price * 10:
                self.result.implied_share_price = self.result.current_price * 10
                self.result.warnings.append("DCF capped at 10x current price")
            
            self.result.implied_share_price = round(self.result.implied_share_price, 2)
            
            # Margin of safety
            if self.result.current_price and self.result.current_price > 0:
                self.result.margin_of_safety = round(
                    (self.result.implied_share_price / self.result.current_price - 1) * 100,
                    2
                )
                
        except Exception as e:
            logger.warning(f"Implied price calculation error: {e}")
    
    def _calculate_implied_growth(self, tolerance: float = 0.01, max_iterations: int = 50):
        """
        Reverse DCF: Calculate the growth rate implied by current price.
        Uses binary search to find the growth rate that produces current price.
        """
        if self.result.current_price is None or self.result.current_price <= 0:
            return
        
        if not self.result.projected_revenue:
            return
        
        try:
            base_revenue = self.result.projected_revenue[0] / (1 + (self.result.ebit_margin or 0.05))
            
            lower = -0.20
            upper = 0.40
            
            for _ in range(max_iterations):
                mid = (lower + upper) / 2
                
                # Calculate price at this growth rate
                price = self._calculate_price_at_growth(base_revenue, mid)
                
                if price is None:
                    break
                
                if abs(price - self.result.current_price) < tolerance:
                    self.result.implied_growth_rate = round(mid * 100, 2)
                    return
                
                if price > self.result.current_price:
                    upper = mid
                else:
                    lower = mid
            
            # Didn't converge, use midpoint
            self.result.implied_growth_rate = round((lower + upper) / 2 * 100, 2)
            
        except Exception as e:
            logger.warning(f"Implied growth calculation error: {e}")
    
    def _calculate_price_at_growth(self, base_revenue: float, growth: float) -> Optional[float]:
        """Helper to calculate implied price at a given growth rate."""
        try:
            # Project revenue
            revenues = []
            rev = base_revenue
            for i in range(5):
                year_growth = growth - (growth - self.terminal_growth_rate) * (i / 5)
                rev = rev * (1 + year_growth)
                revenues.append(rev)
            
            # Project EBIT and FCF using same margins
            ebit_margin = self.result.ebit_margin or 0.15
            tax_rate = self.result.tax_rate or 0.21
            da_margin = self.result.da_margin or 0.05
            capex_margin = self.result.capex_margin or 0.05
            nwc_margin = self.result.nwc_margin or 0.01
            wacc = self.result.wacc or 0.09
            
            fcfs = []
            for rev in revenues:
                ebit = rev * ebit_margin
                ebiat = ebit * (1 - tax_rate)
                fcf = ebiat + (rev * da_margin) - (rev * capex_margin) - (rev * nwc_margin)
                fcfs.append(fcf)
            
            # DCF
            pv_fcf = sum(fcf / ((1 + wacc) ** (i + 0.5)) for i, fcf in enumerate(fcfs))
            terminal = fcfs[-1] * (1 + self.terminal_growth_rate) / (wacc - self.terminal_growth_rate)
            pv_terminal = terminal / ((1 + wacc) ** 5)
            
            ev = pv_fcf + pv_terminal
            equity = ev - (self.result.total_debt or 0) + (self.result.total_cash or 0)
            
            if self.result.shares_outstanding:
                return equity / self.result.shares_outstanding
            
            return None
            
        except Exception:
            return None


def calculate_full_dcf(
    ticker: str,
    terminal_growth_rate: float = 0.025,
) -> FullDCFResult:
    """
    Calculate comprehensive DCF valuation.
    
    This is the DETAILED version for deck generation.
    
    Args:
        ticker: Stock ticker symbol
        terminal_growth_rate: Terminal growth rate (default 2.5%)
    
    Returns:
        FullDCFResult with complete DCF analysis
    """
    model = FullDCFModel(ticker, terminal_growth_rate)
    return model.calculate()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_dcf_for_relative_table(ticker: str) -> Dict[str, Any]:
    """
    Get DCF data formatted for the relative table.
    Returns only the essential columns: dcfPrice and dcfUpside.
    """
    result = calculate_simple_dcf(ticker)
    return {
        'dcfPrice': result.dcf_price,
        'dcfUpside': result.upside,
    }


def get_dcf_for_deck(ticker: str) -> Dict[str, Any]:
    """
    Get comprehensive DCF data for pitch deck generation.
    Returns full analysis with all projections and assumptions.
    """
    result = calculate_full_dcf(ticker)
    return result.to_dict()
