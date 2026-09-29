"""Tests for the DCF valuation (app/services/dcf.py). Yahoo Finance is mocked."""
import pandas as pd
import pytest

from app.services import dcf
from app.services.dcf import Assumptions, calculate_dcf, compute

# FCF 20B growing 10% for 5 years, WACC 10%, terminal growth 2%.
# Each year's PV is exactly 20B (growth = discount rate), the terminal value
# is worth 20B * 1.02 / 0.08 = 255B today, so EV = 100B + 255B = 355B.
FIXED_INPUTS = {
    "market_price": 100.0,
    "shares_outstanding": 1_000_000_000,
    "cash": 50_000_000_000,
    "debt": 30_000_000_000,
    "fcf_0": 20_000_000_000,
}
FIXED_ASSUMPTIONS = Assumptions(forecast_years=5, fcf_growth_rate=0.10, terminal_growth_rate=0.02, wacc=0.10)


class TestAssumptions:
    def test_defaults_are_valid(self):
        assert Assumptions().errors() == []

    @pytest.mark.parametrize("kwargs, message", [
        ({"forecast_years": 4}, "forecast_years"),
        ({"forecast_years": 11}, "forecast_years"),
        ({"terminal_growth_rate": 0.09, "wacc": 0.09}, "terminal_growth_rate"),
        ({"terminal_growth_rate": 0.10, "wacc": 0.09}, "terminal_growth_rate"),
        ({"wacc": 0}, "wacc must be positive"),
        ({"wacc": -0.05}, "wacc must be positive"),
        ({"fcf_growth_rate": 1.5}, "fcf_growth_rate"),
    ])
    def test_invalid(self, kwargs, message):
        assert any(message in error for error in Assumptions(**kwargs).errors())

    def test_from_dict_uses_defaults_for_missing_keys(self):
        a = Assumptions.from_dict({"wacc": 0.11})
        assert (a.wacc, a.forecast_years, a.fcf_growth_rate) == (0.11, 5, 0.08)


class TestCompute:
    def test_known_answer(self):
        b = compute(FIXED_INPUTS, FIXED_ASSUMPTIONS)
        assert [round(y["pvFcf"]) for y in b["fcfForecast"]] == [20_000_000_000] * 5
        assert b["pvTerminal"] == pytest.approx(255e9)
        assert b["enterpriseValue"] == pytest.approx(355e9)
        assert b["equityValue"] == pytest.approx(375e9)  # EV + 50B cash - 30B debt
        assert b["targetPrice"] == pytest.approx(375.0)
        assert b["upsidePct"] == pytest.approx(2.75)

    def test_formulas(self):
        b = compute(FIXED_INPUTS, FIXED_ASSUMPTIONS)
        for year in b["fcfForecast"]:
            t = year["year"]
            assert year["fcf"] == pytest.approx(20e9 * 1.1 ** t)
            assert year["pvFcf"] == pytest.approx(year["fcf"] / 1.1 ** t)
        assert b["fcfNPlus1"] == pytest.approx(20e9 * 1.1 ** 5 * 1.02)
        assert b["terminalValue"] == pytest.approx(b["fcfNPlus1"] / 0.08)


@pytest.fixture
def yahoo(monkeypatch):
    """Fake Yahoo data; tests edit `info` and `cashflow` in place."""
    data = {
        "info": {
            "currency": "USD",
            "financialCurrency": "USD",
            "currentPrice": 100.0,
            "sharesOutstanding": 400_000_000,           # one share class only
            "impliedSharesOutstanding": 1_000_000_000,  # all classes
            "totalCash": 50_000_000_000,
            "totalDebt": 30_000_000_000,
            "freeCashflow": 99_000_000_000,             # Yahoo's estimate: must be ignored
        },
        "cashflow": pd.Series({"Operating Cash Flow": 26e9, "Capital Expenditure": -6e9}),
    }
    monkeypatch.setattr(dcf, "get_info", lambda ticker: data["info"])
    monkeypatch.setattr(dcf, "get_ttm_cashflow", lambda ticker: data["cashflow"])
    return data


class TestCalculateDcf:
    def test_uses_statement_fcf_and_all_share_classes(self, yahoo):
        result = calculate_dcf("goog", assumptions=FIXED_ASSUMPTIONS.to_dict())
        assert result["error"] is None
        assert result["inputs"]["fcf_0"] == 20e9                     # 26B OCF - 6B capex
        assert result["inputs"]["shares_outstanding"] == 1_000_000_000
        assert result["valuation"] == {"targetPrice": 375.0, "marketPrice": 100.0, "upsidePct": 2.75}
        assert result["meta"]["ticker"] == "GOOG"

    def test_falls_back_to_shares_outstanding(self, yahoo):
        del yahoo["info"]["impliedSharesOutstanding"]
        result = calculate_dcf("X")
        assert result["sources"]["shares_outstanding"] == "yfinance info.sharesOutstanding"

    def test_negative_fcf_gives_error_not_price(self, yahoo):
        yahoo["cashflow"] = pd.Series({"Operating Cash Flow": 5e9, "Capital Expenditure": -8e9})
        result = calculate_dcf("X")
        assert "negative" in result["error"] and result["valuation"] == {}

    def test_negative_equity_gives_error_not_price(self, yahoo):
        yahoo["info"]["totalDebt"] = 900e9
        result = calculate_dcf("X")
        assert "equity value is negative" in result["error"] and result["valuation"] == {}

    def test_missing_statement_asks_for_override(self, yahoo):
        yahoo["cashflow"] = pd.Series(dtype=float)
        result = calculate_dcf("X")
        assert "fcf_0" in result["error"] and result["sources"]["fcf_0"] == "missing"

    def test_currency_mismatch_needs_overrides(self, yahoo):
        yahoo["info"]["financialCurrency"] = "TWD"
        assert "TWD" in calculate_dcf("TSM")["error"]

        overrides = {"fcf0": 20e9, "cash": 50e9, "debt": 30e9}
        result = calculate_dcf("TSM", assumptions=FIXED_ASSUMPTIONS.to_dict(), overrides=overrides)
        assert result["error"] is None and result["valuation"]["targetPrice"] == 375.0

    def test_overrides_win_and_are_labelled(self, yahoo):
        result = calculate_dcf("X", overrides={"marketPrice": 250.0})
        assert result["inputs"]["market_price"] == 250.0
        assert result["sources"]["market_price"] == "manual_override"

    def test_invalid_assumptions(self, yahoo):
        result = calculate_dcf("X", assumptions={"wacc": 0.02, "terminalGrowthRate": 0.03})
        assert result["error"].startswith("Invalid assumptions")

    def test_data_failure_is_reported_not_raised(self, monkeypatch):
        def fail(ticker):
            raise ConnectionError("Yahoo down")
        monkeypatch.setattr(dcf, "get_info", fail)
        assert "Yahoo down" in calculate_dcf("X")["error"]
