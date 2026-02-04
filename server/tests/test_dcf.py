"""
Unit tests for DCF calculator.

Tests the deterministic DCF calculation with fixed inputs to guarantee
reproducible outputs.
"""

import pytest
from app.deck.services.dcf_calculator import (
    DCFAssumptions,
    DCFBreakdown,
    DCFCalculator,
    DCFOverrides,
    calculate_dcf,
)
from app.deck.services.dcf_data_provider import DCFInputs, DCFSources


class TestDCFAssumptions:
    """Test assumption validation."""
    
    def test_default_assumptions_valid(self):
        """Default assumptions should be valid."""
        assumptions = DCFAssumptions()
        errors = assumptions.validate()
        assert errors == []
    
    def test_forecast_years_too_low(self):
        """Forecast years below 5 should be invalid."""
        assumptions = DCFAssumptions(forecast_years=3)
        errors = assumptions.validate()
        assert "forecast_years must be between 5 and 10" in errors
    
    def test_forecast_years_too_high(self):
        """Forecast years above 10 should be invalid."""
        assumptions = DCFAssumptions(forecast_years=15)
        errors = assumptions.validate()
        assert "forecast_years must be between 5 and 10" in errors
    
    def test_terminal_growth_exceeds_wacc(self):
        """Terminal growth >= WACC should be invalid."""
        assumptions = DCFAssumptions(terminal_growth_rate=0.10, wacc=0.09)
        errors = assumptions.validate()
        assert any("terminal_growth_rate must be less than wacc" in e for e in errors)
    
    def test_terminal_growth_equals_wacc(self):
        """Terminal growth = WACC should be invalid (division by zero)."""
        assumptions = DCFAssumptions(terminal_growth_rate=0.09, wacc=0.09)
        errors = assumptions.validate()
        assert any("terminal_growth_rate must be less than wacc" in e for e in errors)
    
    def test_zero_wacc_invalid(self):
        """WACC = 0 should be invalid."""
        assumptions = DCFAssumptions(wacc=0)
        errors = assumptions.validate()
        assert "wacc must be positive" in errors
    
    def test_negative_wacc_invalid(self):
        """Negative WACC should be invalid."""
        assumptions = DCFAssumptions(wacc=-0.05)
        errors = assumptions.validate()
        assert "wacc must be positive" in errors
    
    def test_extreme_growth_rate_invalid(self):
        """Growth rate > 100% should be invalid."""
        assumptions = DCFAssumptions(fcf_growth_rate=1.5)
        errors = assumptions.validate()
        assert "fcf_growth_rate must be between -50% and 100%" in errors


class TestDCFCalculatorDeterministic:
    """
    Test DCF calculation with fixed inputs to guarantee deterministic outputs.
    
    These tests verify the exact formulas:
    - FCF_t = FCF_0 * (1 + g)^t
    - PV_FCF_t = FCF_t / (1 + WACC)^t
    - TV_N = FCF_(N+1) / (WACC - g)
    - PV_TV = TV_N / (1 + WACC)^N
    - EV = sum(PV_FCF_t) + PV_TV
    - Equity = EV + Cash - Debt
    - TargetPrice = Equity / Shares
    - Upside = (TargetPrice / MarketPrice) - 1
    """
    
    @pytest.fixture
    def fixed_inputs(self) -> DCFInputs:
        """Fixed inputs for deterministic testing."""
        return DCFInputs(
            market_price=100.0,
            shares_outstanding=1_000_000_000,  # 1B shares
            cash=50_000_000_000,  # $50B cash
            debt=30_000_000_000,  # $30B debt
            fcf_0=20_000_000_000,  # $20B FCF
            currency="USD",
        )
    
    @pytest.fixture
    def fixed_assumptions(self) -> DCFAssumptions:
        """Fixed assumptions for deterministic testing."""
        return DCFAssumptions(
            forecast_years=5,
            fcf_growth_rate=0.10,  # 10% FCF growth
            terminal_growth_rate=0.02,  # 2% terminal growth
            wacc=0.10,  # 10% WACC
        )
    
    def test_fcf_forecast(self, fixed_inputs, fixed_assumptions):
        """Test FCF forecast calculation."""
        calc = DCFCalculator()
        
        # Manually apply inputs (bypass yfinance)
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # FCF_t = FCF_0 * (1 + g)^t
        fcf_0 = 20_000_000_000
        g = 0.10
        
        expected_fcf = [
            fcf_0 * (1 + g) ** 1,  # Year 1: 22B
            fcf_0 * (1 + g) ** 2,  # Year 2: 24.2B
            fcf_0 * (1 + g) ** 3,  # Year 3: 26.62B
            fcf_0 * (1 + g) ** 4,  # Year 4: 29.282B
            fcf_0 * (1 + g) ** 5,  # Year 5: 32.2102B
        ]
        
        for i, (actual, expected) in enumerate(zip(breakdown.fcf_forecast, expected_fcf)):
            assert abs(actual - expected) < 0.01, f"Year {i+1} FCF mismatch"
    
    def test_pv_fcf(self, fixed_inputs, fixed_assumptions):
        """Test present value of FCF calculation."""
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # PV_FCF_t = FCF_t / (1 + WACC)^t
        wacc = 0.10
        
        for i, (fcf, pv) in enumerate(zip(breakdown.fcf_forecast, breakdown.pv_fcf)):
            t = i + 1
            expected_pv = fcf / ((1 + wacc) ** t)
            assert abs(pv - expected_pv) < 0.01, f"Year {t} PV mismatch"
    
    def test_terminal_value(self, fixed_inputs, fixed_assumptions):
        """Test terminal value calculation."""
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # FCF_(N+1) = FCF_N * (1 + g_terminal)
        fcf_n = breakdown.fcf_forecast[-1]
        g_terminal = 0.02
        expected_fcf_n_plus_1 = fcf_n * (1 + g_terminal)
        
        assert abs(breakdown.fcf_n_plus_1 - expected_fcf_n_plus_1) < 0.01
        
        # TV_N = FCF_(N+1) / (WACC - g)
        wacc = 0.10
        expected_tv = expected_fcf_n_plus_1 / (wacc - g_terminal)
        
        assert abs(breakdown.terminal_value - expected_tv) < 0.01
    
    def test_pv_terminal(self, fixed_inputs, fixed_assumptions):
        """Test present value of terminal value calculation."""
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # PV_TV = TV_N / (1 + WACC)^N
        wacc = 0.10
        n = 5
        expected_pv_tv = breakdown.terminal_value / ((1 + wacc) ** n)
        
        assert abs(breakdown.pv_terminal - expected_pv_tv) < 0.01
    
    def test_enterprise_value(self, fixed_inputs, fixed_assumptions):
        """Test enterprise value calculation."""
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # EV = sum(PV_FCF_t) + PV_TV
        expected_ev = sum(breakdown.pv_fcf) + breakdown.pv_terminal
        
        assert abs(breakdown.enterprise_value - expected_ev) < 0.01
        assert breakdown.sum_pv_fcf == sum(breakdown.pv_fcf)
    
    def test_equity_value(self, fixed_inputs, fixed_assumptions):
        """Test equity value calculation."""
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # Equity = EV + Cash - Debt
        expected_equity = breakdown.enterprise_value + 50_000_000_000 - 30_000_000_000
        
        assert abs(breakdown.equity_value - expected_equity) < 0.01
    
    def test_target_price(self, fixed_inputs, fixed_assumptions):
        """Test target price calculation."""
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # TargetPrice = Equity / Shares
        expected_target = breakdown.equity_value / 1_000_000_000
        
        assert abs(breakdown.target_price - expected_target) < 0.01
    
    def test_upside_calculation(self, fixed_inputs, fixed_assumptions):
        """Test upside percentage calculation."""
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # Upside = (TargetPrice / MarketPrice) - 1
        expected_upside = (breakdown.target_price / 100.0) - 1
        
        assert abs(breakdown.upside_pct - expected_upside) < 0.0001
    
    def test_full_calculation_reproducible(self, fixed_inputs, fixed_assumptions):
        """
        Full DCF calculation should produce consistent results.
        
        With the fixed inputs above, we can verify the exact expected values.
        """
        calc = DCFCalculator()
        breakdown = calc._compute_dcf(fixed_inputs, fixed_assumptions)
        
        # Verify key metrics (calculated manually for verification)
        # FCF_0 = 20B, g_fcf = 10%, g_term = 2%, WACC = 10%, N = 5
        
        # Year 5 FCF = 20B * 1.1^5 = 32.2102B
        assert abs(breakdown.fcf_forecast[4] - 32210200000) < 1000
        
        # FCF_6 = 32.2102B * 1.02 = 32854404000
        assert abs(breakdown.fcf_n_plus_1 - 32854404000) < 1000
        
        # TV = 32854404000 / (0.10 - 0.02) = 410680050000
        assert abs(breakdown.terminal_value - 410680050000) < 1000
        
        # Verify breakdown object has all required fields
        assert breakdown.fcf_0 == 20_000_000_000
        assert breakdown.forecast_years == 5
        assert len(breakdown.fcf_forecast) == 5
        assert len(breakdown.pv_fcf) == 5
        assert breakdown.cash == 50_000_000_000
        assert breakdown.debt == 30_000_000_000
        assert breakdown.shares_outstanding == 1_000_000_000
        assert breakdown.market_price == 100.0


class TestDCFOverrides:
    """Test manual override functionality."""
    
    def test_overrides_from_dict(self):
        """Test parsing overrides from dict."""
        data = {
            "sharesOutstanding": 1000000,
            "cash": 5000000,
            "debt": 2000000,
            "fcf0": 1000000,
            "marketPrice": 50.0,
        }
        overrides = DCFOverrides.from_dict(data)
        
        assert overrides.shares_outstanding == 1000000
        assert overrides.cash == 5000000
        assert overrides.debt == 2000000
        assert overrides.fcf_0 == 1000000
        assert overrides.market_price == 50.0
    
    def test_overrides_from_empty_dict(self):
        """Test parsing overrides from empty dict."""
        overrides = DCFOverrides.from_dict({})
        
        assert overrides.shares_outstanding is None
        assert overrides.cash is None
        assert overrides.debt is None
        assert overrides.fcf_0 is None
        assert overrides.market_price is None
    
    def test_overrides_from_none(self):
        """Test parsing overrides from None."""
        overrides = DCFOverrides.from_dict(None)
        
        assert overrides.shares_outstanding is None


class TestCalculateDCFFunction:
    """Test the convenience calculate_dcf function."""
    
    def test_returns_dict(self):
        """Result should be a dict."""
        # This will fail due to missing yfinance data, but should return a dict
        result = calculate_dcf("INVALID_TICKER_XYZ123")
        
        assert isinstance(result, dict)
        assert "meta" in result
        assert "inputs" in result
        assert "sources" in result
    
    def test_with_full_overrides(self):
        """Test calculation with all values overridden (no yfinance needed)."""
        result = calculate_dcf(
            ticker="TEST",
            assumptions={
                "forecastYears": 5,
                "fcfGrowthRate": 0.10,
                "terminalGrowthRate": 0.02,
                "wacc": 0.10,
            },
            overrides={
                "sharesOutstanding": 1_000_000_000,
                "cash": 50_000_000_000,
                "debt": 30_000_000_000,
                "fcf0": 20_000_000_000,
                "marketPrice": 100.0,
            },
        )
        
        assert result["error"] is None
        assert "valuation" in result
        assert "targetPrice" in result["valuation"]
        assert "marketPrice" in result["valuation"]
        assert "upsidePct" in result["valuation"]
        assert result["valuation"]["marketPrice"] == 100.0
        
        # Verify sources show overrides
        sources = result["sources"]
        assert sources["market_price"] == "manual_override"
        assert sources["shares_outstanding"] == "manual_override"
        assert sources["cash"] == "manual_override"
        assert sources["debt"] == "manual_override"
        assert sources["fcf_0"] == "manual_override"
    
    def test_invalid_assumptions_returns_error(self):
        """Invalid assumptions should return error."""
        result = calculate_dcf(
            ticker="TEST",
            assumptions={
                "forecastYears": 5,
                "terminalGrowthRate": 0.15,  # > WACC
                "wacc": 0.10,
            },
            overrides={
                "sharesOutstanding": 1000,
                "cash": 1000,
                "debt": 500,
                "fcf0": 100,
                "marketPrice": 10.0,
            },
        )
        
        assert result["error"] is not None
        assert "terminal_growth_rate must be less than wacc" in result["error"]


class TestDCFBreakdownSerialization:
    """Test breakdown object serialization."""
    
    def test_to_dict(self):
        """Test breakdown serialization to dict."""
        breakdown = DCFBreakdown(
            fcf_0=1000,
            forecast_years=5,
            fcf_growth_rate=0.08,
            terminal_growth_rate=0.025,
            wacc=0.09,
            fcf_forecast=[1080, 1166.4, 1259.7, 1360.5, 1469.3],
            pv_fcf=[990.8, 981.7, 972.6, 963.6, 954.7],
            fcf_n_plus_1=1506.0,
            terminal_value=23169.2,
            pv_terminal=15060.7,
            sum_pv_fcf=4863.4,
            enterprise_value=19924.1,
            cash=500,
            debt=200,
            equity_value=20224.1,
            shares_outstanding=100,
            target_price=202.24,
            market_price=150.0,
            upside_pct=0.3483,
        )
        
        result = breakdown.to_dict()
        
        assert result["fcf0"] == 1000
        assert result["forecastYears"] == 5
        assert len(result["fcfForecast"]) == 5
        assert result["fcfForecast"][0]["year"] == 1
        assert result["targetPrice"] == 202.24
        assert result["upsidePct"] == 0.3483
