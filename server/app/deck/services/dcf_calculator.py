"""
Deterministic DCF Calculator.

Computes DCF valuation using explicit formulas. All intermediate steps
are exposed for verification. NO LLM-generated numbers.

DCF Procedure:
1) Forecast FCF for N years: FCF_t = FCF_0 * (1 + fcfGrowthRate)^t
2) Discount each FCF: PV_FCF_t = FCF_t / (1 + WACC)^t
3) Terminal Value: TV_N = FCF_(N+1) / (WACC - g), where FCF_(N+1) = FCF_N * (1 + g)
4) Discount Terminal Value: PV_TV = TV_N / (1 + WACC)^N
5) Enterprise Value: EV = sum(PV_FCF_t) + PV_TV
6) Equity Value: Equity = EV + Cash - Debt
7) Target Price: TargetPrice = Equity / SharesOutstanding
8) Upside: UpsidePct = (TargetPrice / MarketPrice) - 1
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from .dcf_data_provider import DCFInputs, DCFSources, get_dcf_data_provider


@dataclass
class DCFAssumptions:
    """User-editable DCF assumptions."""
    forecast_years: int = 5
    fcf_growth_rate: float = 0.08
    terminal_growth_rate: float = 0.025
    wacc: float = 0.09
    
    def validate(self) -> list[str]:
        """Validate assumptions, return list of errors."""
        errors = []
        if not 5 <= self.forecast_years <= 10:
            errors.append("forecast_years must be between 5 and 10")
        if self.terminal_growth_rate >= self.wacc:
            errors.append("terminal_growth_rate must be less than wacc (otherwise terminal value is infinite/negative)")
        if self.wacc <= 0:
            errors.append("wacc must be positive")
        if self.fcf_growth_rate < -0.5 or self.fcf_growth_rate > 1.0:
            errors.append("fcf_growth_rate must be between -50% and 100%")
        return errors
    
    def to_dict(self) -> dict:
        return {
            "forecastYears": self.forecast_years,
            "fcfGrowthRate": self.fcf_growth_rate,
            "terminalGrowthRate": self.terminal_growth_rate,
            "wacc": self.wacc,
        }


@dataclass
class DCFBreakdown:
    """Step-by-step calculation breakdown for verification."""
    fcf_0: float = 0.0
    forecast_years: int = 5
    fcf_growth_rate: float = 0.08
    terminal_growth_rate: float = 0.025
    wacc: float = 0.09
    
    # Per-year forecasts (index 0 = year 1, etc.)
    fcf_forecast: list[float] = field(default_factory=list)  # FCF_t for t=1..N
    pv_fcf: list[float] = field(default_factory=list)  # PV of each year's FCF
    
    # Terminal value components
    fcf_n_plus_1: float = 0.0
    terminal_value: float = 0.0
    pv_terminal: float = 0.0
    
    # Aggregates
    sum_pv_fcf: float = 0.0
    enterprise_value: float = 0.0
    cash: float = 0.0
    debt: float = 0.0
    equity_value: float = 0.0
    shares_outstanding: float = 0.0
    target_price: float = 0.0
    market_price: float = 0.0
    upside_pct: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict with camelCase keys."""
        return {
            "fcf0": self.fcf_0,
            "forecastYears": self.forecast_years,
            "fcfGrowthRate": self.fcf_growth_rate,
            "terminalGrowthRate": self.terminal_growth_rate,
            "wacc": self.wacc,
            "fcfForecast": [
                {"year": i + 1, "fcf": fcf, "pvFcf": pv}
                for i, (fcf, pv) in enumerate(zip(self.fcf_forecast, self.pv_fcf))
            ],
            "fcfNPlus1": self.fcf_n_plus_1,
            "terminalValue": self.terminal_value,
            "pvTerminal": self.pv_terminal,
            "sumPvFcf": self.sum_pv_fcf,
            "enterpriseValue": self.enterprise_value,
            "cash": self.cash,
            "debt": self.debt,
            "equityValue": self.equity_value,
            "sharesOutstanding": self.shares_outstanding,
            "targetPrice": self.target_price,
            "marketPrice": self.market_price,
            "upsidePct": self.upside_pct,
        }


@dataclass
class DCFOverrides:
    """Manual overrides for DCF inputs."""
    shares_outstanding: Optional[float] = None
    cash: Optional[float] = None
    debt: Optional[float] = None
    fcf_0: Optional[float] = None
    market_price: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "DCFOverrides":
        if not data:
            return cls()
        return cls(
            shares_outstanding=data.get("sharesOutstanding"),
            cash=data.get("cash"),
            debt=data.get("debt"),
            fcf_0=data.get("fcf0"),
            market_price=data.get("marketPrice"),
        )


@dataclass
class DCFResult:
    """Complete DCF calculation result."""
    meta: dict
    inputs: dict
    assumptions: dict
    valuation: dict
    calculation_breakdown: dict
    warnings: list[str]
    sources: dict
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


class DCFCalculator:
    """
    Deterministic DCF calculator using yfinance data.
    
    All calculations are explicit and verifiable.
    """
    
    def __init__(self):
        self.data_provider = get_dcf_data_provider()
    
    def calculate(
        self,
        ticker: str,
        assumptions: Optional[DCFAssumptions] = None,
        overrides: Optional[DCFOverrides] = None,
    ) -> DCFResult:
        """
        Calculate DCF valuation for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            assumptions: DCF assumptions (uses defaults if not provided)
            overrides: Manual overrides for inputs (override wins over yfinance)
        
        Returns:
            DCFResult with complete calculation breakdown
        """
        if assumptions is None:
            assumptions = DCFAssumptions()
        if overrides is None:
            overrides = DCFOverrides()
        
        # Validate assumptions first
        validation_errors = assumptions.validate()
        if validation_errors:
            return DCFResult(
                meta={"ticker": ticker, "asOf": datetime.now(timezone.utc).isoformat(), "provider": "yfinance"},
                inputs={},
                assumptions=assumptions.to_dict(),
                valuation={},
                calculation_breakdown={},
                warnings=[],
                sources={},
                error=f"Invalid assumptions: {'; '.join(validation_errors)}",
            )
        
        # Fetch inputs from yfinance
        inputs, sources, warnings = self.data_provider.get_inputs(ticker)
        
        # Apply overrides (override wins)
        final_inputs, final_sources = self._apply_overrides(inputs, sources, overrides)
        
        # Check for required inputs
        missing = self._check_required_inputs(final_inputs)
        if missing:
            return DCFResult(
                meta={
                    "ticker": ticker.upper(),
                    "asOf": datetime.now(timezone.utc).isoformat(),
                    "currency": final_inputs.currency,
                    "provider": "yfinance",
                },
                inputs=final_inputs.to_dict(),
                assumptions=assumptions.to_dict(),
                valuation={},
                calculation_breakdown={},
                warnings=warnings,
                sources=final_sources.to_dict(),
                error=f"Missing required inputs: {', '.join(missing)}. Please provide manual overrides.",
            )
        
        # Perform DCF calculation
        breakdown = self._compute_dcf(final_inputs, assumptions)
        
        return DCFResult(
            meta={
                "ticker": ticker.upper(),
                "asOf": datetime.now(timezone.utc).isoformat(),
                "currency": final_inputs.currency,
                "provider": "yfinance",
            },
            inputs=final_inputs.to_dict(),
            assumptions=assumptions.to_dict(),
            valuation={
                "targetPrice": round(breakdown.target_price, 2),
                "marketPrice": round(breakdown.market_price, 2),
                "upsidePct": round(breakdown.upside_pct, 4),
            },
            calculation_breakdown=breakdown.to_dict(),
            warnings=warnings,
            sources=final_sources.to_dict(),
        )
    
    def _apply_overrides(
        self,
        inputs: DCFInputs,
        sources: DCFSources,
        overrides: DCFOverrides,
    ) -> tuple[DCFInputs, DCFSources]:
        """Apply manual overrides to inputs."""
        # Create copies
        final_inputs = DCFInputs(
            market_price=inputs.market_price,
            shares_outstanding=inputs.shares_outstanding,
            cash=inputs.cash,
            debt=inputs.debt,
            fcf_0=inputs.fcf_0,
            beta=inputs.beta,
            currency=inputs.currency,
        )
        final_sources = DCFSources(
            market_price=sources.market_price,
            shares_outstanding=sources.shares_outstanding,
            cash=sources.cash,
            debt=sources.debt,
            fcf_0=sources.fcf_0,
            beta=sources.beta,
        )
        
        # Apply overrides
        if overrides.market_price is not None:
            final_inputs.market_price = overrides.market_price
            final_sources.market_price = "manual_override"
        
        if overrides.shares_outstanding is not None:
            final_inputs.shares_outstanding = overrides.shares_outstanding
            final_sources.shares_outstanding = "manual_override"
        
        if overrides.cash is not None:
            final_inputs.cash = overrides.cash
            final_sources.cash = "manual_override"
        
        if overrides.debt is not None:
            final_inputs.debt = overrides.debt
            final_sources.debt = "manual_override"
        
        if overrides.fcf_0 is not None:
            final_inputs.fcf_0 = overrides.fcf_0
            final_sources.fcf_0 = "manual_override"
        
        return final_inputs, final_sources
    
    def _check_required_inputs(self, inputs: DCFInputs) -> list[str]:
        """Check for missing required inputs."""
        missing = []
        if inputs.market_price is None:
            missing.append("marketPrice")
        if inputs.shares_outstanding is None:
            missing.append("sharesOutstanding")
        if inputs.cash is None:
            missing.append("cash")
        if inputs.debt is None:
            missing.append("debt")
        if inputs.fcf_0 is None:
            missing.append("fcf0")
        return missing
    
    def _compute_dcf(self, inputs: DCFInputs, assumptions: DCFAssumptions) -> DCFBreakdown:
        """
        Compute DCF valuation using explicit formulas.
        
        All intermediate steps are captured in the breakdown.
        """
        breakdown = DCFBreakdown(
            fcf_0=inputs.fcf_0,  # type: ignore (we checked for None above)
            forecast_years=assumptions.forecast_years,
            fcf_growth_rate=assumptions.fcf_growth_rate,
            terminal_growth_rate=assumptions.terminal_growth_rate,
            wacc=assumptions.wacc,
            cash=inputs.cash,  # type: ignore
            debt=inputs.debt,  # type: ignore
            shares_outstanding=inputs.shares_outstanding,  # type: ignore
            market_price=inputs.market_price,  # type: ignore
        )
        
        fcf_0: float = inputs.fcf_0  # type: ignore
        n = assumptions.forecast_years
        g_fcf = assumptions.fcf_growth_rate
        g_terminal = assumptions.terminal_growth_rate
        wacc = assumptions.wacc
        
        # Step 1 & 2: Forecast FCF and discount each year
        fcf_forecast: list[float] = []
        pv_fcf: list[float] = []
        
        for t in range(1, n + 1):
            # FCF_t = FCF_0 * (1 + fcfGrowthRate)^t
            fcf_t = fcf_0 * ((1 + g_fcf) ** t)
            fcf_forecast.append(fcf_t)
            
            # PV_FCF_t = FCF_t / (1 + WACC)^t
            pv_t = fcf_t / ((1 + wacc) ** t)
            pv_fcf.append(pv_t)
        
        breakdown.fcf_forecast = fcf_forecast
        breakdown.pv_fcf = pv_fcf
        
        # Step 3: Terminal value
        # FCF_(N+1) = FCF_N * (1 + g)
        fcf_n = fcf_forecast[-1]
        fcf_n_plus_1 = fcf_n * (1 + g_terminal)
        breakdown.fcf_n_plus_1 = fcf_n_plus_1
        
        # TV_N = FCF_(N+1) / (WACC - g)
        terminal_value = fcf_n_plus_1 / (wacc - g_terminal)
        breakdown.terminal_value = terminal_value
        
        # Step 4: Discount terminal value
        # PV_TV = TV_N / (1 + WACC)^N
        pv_terminal = terminal_value / ((1 + wacc) ** n)
        breakdown.pv_terminal = pv_terminal
        
        # Step 5: Enterprise Value
        sum_pv_fcf = sum(pv_fcf)
        breakdown.sum_pv_fcf = sum_pv_fcf
        
        enterprise_value = sum_pv_fcf + pv_terminal
        breakdown.enterprise_value = enterprise_value
        
        # Step 6: Equity Value
        cash: float = inputs.cash  # type: ignore
        debt: float = inputs.debt  # type: ignore
        equity_value = enterprise_value + cash - debt
        breakdown.equity_value = equity_value
        
        # Step 7: Target Price
        shares: float = inputs.shares_outstanding  # type: ignore
        target_price = equity_value / shares
        breakdown.target_price = target_price
        
        # Step 8: Upside
        market_price: float = inputs.market_price  # type: ignore
        upside_pct = (target_price / market_price) - 1
        breakdown.upside_pct = upside_pct
        
        return breakdown


# Module-level singleton
_calculator: Optional[DCFCalculator] = None


def get_dcf_calculator() -> DCFCalculator:
    """Get the singleton DCF calculator."""
    global _calculator
    if _calculator is None:
        _calculator = DCFCalculator()
    return _calculator


def calculate_dcf(
    ticker: str,
    assumptions: Optional[dict] = None,
    overrides: Optional[dict] = None,
) -> dict:
    """
    Convenience function to calculate DCF and return dict result.
    
    Args:
        ticker: Stock ticker symbol
        assumptions: Dict with forecastYears, fcfGrowthRate, terminalGrowthRate, wacc
        overrides: Dict with sharesOutstanding, cash, debt, fcf0, marketPrice
    
    Returns:
        Dict with complete DCF result
    """
    calc = get_dcf_calculator()
    
    # Parse assumptions
    dcf_assumptions = DCFAssumptions()
    if assumptions:
        if "forecastYears" in assumptions:
            dcf_assumptions.forecast_years = int(assumptions["forecastYears"])
        if "fcfGrowthRate" in assumptions:
            dcf_assumptions.fcf_growth_rate = float(assumptions["fcfGrowthRate"])
        if "terminalGrowthRate" in assumptions:
            dcf_assumptions.terminal_growth_rate = float(assumptions["terminalGrowthRate"])
        if "wacc" in assumptions:
            dcf_assumptions.wacc = float(assumptions["wacc"])
    
    # Parse overrides
    dcf_overrides = DCFOverrides.from_dict(overrides)
    
    result = calc.calculate(ticker, dcf_assumptions, dcf_overrides)
    return result.to_dict()
