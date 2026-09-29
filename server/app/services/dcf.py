"""Discounted cash flow (DCF) valuation.

One implementation, used by the comparison table, the /api/v1/valuation/dcf
endpoint and pitch decks, so a ticker gets the same fair value everywhere.

    FCF_t   = FCF_0 * (1 + g)^t                              t = 1..N
    PV_t    = FCF_t / (1 + WACC)^t
    TV_N    = FCF_N * (1 + g_terminal) / (WACC - g_terminal)
    EV      = sum(PV_t) + TV_N / (1 + WACC)^N
    Equity  = EV + cash - debt
    Target  = Equity / shares          Upside = Target / price - 1

Inputs come from Yahoo Finance, can be overridden, and ``sources`` records
where each one came from. The comparison table uses the default assumptions
for every company, so its DCF column compares like with like.

When the model would produce a misleading number (negative cash flow,
negative equity, statements in a different currency from the price) it
returns an error instead of a price.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.yfinance_service import get_info, get_ttm_cashflow, safe_float

REQUIRED_INPUTS = ("market_price", "shares_outstanding", "cash", "debt", "fcf_0")
OVERRIDE_KEYS = {  # request field -> input
    "marketPrice": "market_price",
    "sharesOutstanding": "shares_outstanding",
    "cash": "cash",
    "debt": "debt",
    "fcf0": "fcf_0",
}


@dataclass
class Assumptions:
    forecast_years: int = 5
    fcf_growth_rate: float = 0.08
    terminal_growth_rate: float = 0.025
    wacc: float = 0.09

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "Assumptions":
        data = data or {}
        defaults = cls()
        return cls(
            forecast_years=int(data.get("forecastYears") or defaults.forecast_years),
            fcf_growth_rate=float(data.get("fcfGrowthRate", defaults.fcf_growth_rate)),
            terminal_growth_rate=float(data.get("terminalGrowthRate", defaults.terminal_growth_rate)),
            wacc=float(data.get("wacc", defaults.wacc)),
        )

    def errors(self) -> list[str]:
        errors = []
        if not 5 <= self.forecast_years <= 10:
            errors.append("forecast_years must be between 5 and 10")
        if self.wacc <= 0:
            errors.append("wacc must be positive")
        if self.terminal_growth_rate >= self.wacc:
            errors.append("terminal_growth_rate must be less than wacc (otherwise terminal value is infinite/negative)")
        if not -0.5 <= self.fcf_growth_rate <= 1.0:
            errors.append("fcf_growth_rate must be between -50% and 100%")
        return errors

    def to_dict(self) -> dict:
        return {
            "forecastYears": self.forecast_years,
            "fcfGrowthRate": self.fcf_growth_rate,
            "terminalGrowthRate": self.terminal_growth_rate,
            "wacc": self.wacc,
        }


def _first(info: dict, *keys: str) -> tuple[Optional[float], str]:
    """The first usable value among Yahoo info keys, and where it came from."""
    for key in keys:
        value = safe_float(info.get(key))
        if value is not None:
            return value, f"yfinance info.{key}"
    return None, "missing"


def fetch_inputs(ticker: str) -> tuple[dict, dict, list[str]]:
    """(inputs, sources, warnings) for a ticker from Yahoo Finance. Missing inputs are None."""
    info = get_info(ticker)
    inputs: dict[str, Any] = {"currency": info.get("currency") or "USD", "fcf_0": None}
    sources: dict[str, str] = {"fcf_0": "missing"}
    warnings: list[str] = []

    inputs["market_price"], sources["market_price"] = _first(info, "currentPrice", "regularMarketPrice")
    # impliedSharesOutstanding counts every share class (GOOGL, BRK-B); plain
    # sharesOutstanding can be one class only and would overstate per-share value.
    inputs["shares_outstanding"], sources["shares_outstanding"] = _first(
        info, "impliedSharesOutstanding", "sharesOutstanding"
    )
    inputs["cash"], sources["cash"] = _first(info, "totalCash")
    inputs["debt"], sources["debt"] = _first(info, "totalDebt")
    inputs["beta"], sources["beta"] = _first(info, "beta")

    # FCF from the reported cash flow statement, trailing twelve months, so it
    # can be checked against the filings. (Yahoo's info.freeCashflow is its own
    # "levered FCF" estimate and can even exceed operating cash flow.)
    try:
        cashflow = get_ttm_cashflow(ticker)
        operating = safe_float(cashflow.get("Operating Cash Flow"))
        capex = safe_float(cashflow.get("Capital Expenditure"))
        if operating is not None and capex is not None:
            inputs["fcf_0"] = operating - abs(capex)
            sources["fcf_0"] = "yfinance TTM cash flow: operating cash flow - capital expenditure"
    except Exception as exc:
        warnings.append(f"cash flow statement unavailable: {exc}")

    statement_currency = info.get("financialCurrency")
    if statement_currency and statement_currency != inputs["currency"]:
        inputs["statement_currency"] = statement_currency

    for key in REQUIRED_INPUTS:
        if inputs[key] is None:
            warnings.append(f"{key}: not available from yfinance, manual input required")
    return inputs, sources, warnings


def compute(inputs: dict, a: Assumptions) -> dict:
    """The DCF arithmetic, step by step. Pure function: no I/O."""
    fcf_0 = inputs["fcf_0"]
    forecast = []
    for t in range(1, a.forecast_years + 1):
        fcf_t = fcf_0 * (1 + a.fcf_growth_rate) ** t
        forecast.append({"year": t, "fcf": fcf_t, "pvFcf": fcf_t / (1 + a.wacc) ** t})

    fcf_n_plus_1 = forecast[-1]["fcf"] * (1 + a.terminal_growth_rate)
    terminal_value = fcf_n_plus_1 / (a.wacc - a.terminal_growth_rate)
    pv_terminal = terminal_value / (1 + a.wacc) ** a.forecast_years
    sum_pv_fcf = sum(year["pvFcf"] for year in forecast)
    enterprise_value = sum_pv_fcf + pv_terminal
    equity_value = enterprise_value + inputs["cash"] - inputs["debt"]
    target_price = equity_value / inputs["shares_outstanding"]

    return {
        "fcf0": fcf_0,
        **a.to_dict(),
        "fcfForecast": forecast,
        "fcfNPlus1": fcf_n_plus_1,
        "terminalValue": terminal_value,
        "pvTerminal": pv_terminal,
        "sumPvFcf": sum_pv_fcf,
        "enterpriseValue": enterprise_value,
        "cash": inputs["cash"],
        "debt": inputs["debt"],
        "equityValue": equity_value,
        "sharesOutstanding": inputs["shares_outstanding"],
        "targetPrice": target_price,
        "marketPrice": inputs["market_price"],
        "upsidePct": target_price / inputs["market_price"] - 1,
    }


def _problem(inputs: dict, sources: dict) -> Optional[str]:
    """Why a DCF on these inputs would be misleading, or None if it is fine."""
    missing = [key for key in REQUIRED_INPUTS if inputs[key] is None]
    if missing:
        return f"Missing required inputs: {', '.join(missing)}. Please provide manual overrides."
    statement_currency = inputs.get("statement_currency")
    from_statements = any(sources[k].startswith("yfinance") for k in ("fcf_0", "cash", "debt"))
    if statement_currency and from_statements:
        return (
            f"Financial statements are in {statement_currency} but the price is in "
            f"{inputs['currency']}; override fcf0, cash and debt in {inputs['currency']}."
        )
    if inputs["market_price"] <= 0 or inputs["shares_outstanding"] <= 0:
        return "Price and shares outstanding must be positive."
    if inputs["fcf_0"] <= 0:
        return "Free cash flow is zero or negative, so a cash-flow valuation is not meaningful."
    return None


def calculate_dcf(
    ticker: str,
    assumptions: Optional[dict] = None,
    overrides: Optional[dict] = None,
) -> dict:
    """DCF for a ticker. Never raises: problems are reported in ``error``."""
    ticker = ticker.upper().strip()
    a = Assumptions.from_dict(assumptions)
    result: dict[str, Any] = {
        "meta": {
            "ticker": ticker,
            "asOf": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "provider": "yfinance",
        },
        "inputs": {},
        "assumptions": a.to_dict(),
        "valuation": {},
        "calculationBreakdown": {},
        "warnings": [],
        "sources": {},
        "error": None,
    }
    if a.errors():
        result["error"] = f"Invalid assumptions: {'; '.join(a.errors())}"
        return result

    try:
        inputs, sources, warnings = fetch_inputs(ticker)
    except Exception as exc:
        result["error"] = f"Could not load market data for {ticker}: {exc}"
        return result

    for request_key, input_key in OVERRIDE_KEYS.items():
        value = (overrides or {}).get(request_key)
        if value is not None:
            inputs[input_key] = float(value)
            sources[input_key] = "manual_override"

    result.update(inputs=inputs, sources=sources, warnings=warnings)
    result["meta"]["currency"] = inputs["currency"]

    result["error"] = _problem(inputs, sources)
    if result["error"]:
        return result

    breakdown = compute(inputs, a)
    result["calculationBreakdown"] = breakdown
    if breakdown["equityValue"] <= 0:
        result["error"] = "Debt exceeds the present value of the cash flows, so equity value is negative."
        return result

    result["valuation"] = {
        "targetPrice": round(breakdown["targetPrice"], 2),
        "marketPrice": round(breakdown["marketPrice"], 2),
        "upsidePct": round(breakdown["upsidePct"], 4),
    }
    return result
