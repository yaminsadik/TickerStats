"""
Tests for provider-aware reasoning option mapping in DeckGenerator.
"""

from app.deck.services.deck_generator import DeckGenerator
from app.deck.api.schemas import (
    DeckGenerateRequest,
    FundConstraints,
    Provider,
    ValuationInput,
)


class TestProviderReasoningMapping:
    def setup_method(self):
        self.generator = DeckGenerator()

    def test_openai_maps_reasoning_effort(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="openai",
            model="gpt-5.2",
            reasoning_level="high",
        )
        assert extra["model"] == "gpt-5.2"
        assert extra["reasoning_effort"] == "high"

    def test_gemini_31_pro_maps_medium_to_high(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="gemini",
            model="gemini-3.1-pro-preview",
            reasoning_level="medium",
        )
        assert extra["thinking_level"] == "high"

    def test_gemini_31_pro_maps_low_to_low(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="gemini",
            model="gemini-3.1-pro-preview",
            reasoning_level="low",
        )
        assert extra["thinking_level"] == "low"

    def test_deepseek_uses_model_only(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="deepseek",
            model="deepseek-reasoner",
            reasoning_level="high",
        )
        assert extra == {"model": "deepseek-reasoner"}

    def test_zai_toggles_thinking(self):
        low_extra = self.generator._build_provider_options_extra(
            provider_name="zai",
            model="glm-4.7-flashx",
            reasoning_level="low",
        )
        high_extra = self.generator._build_provider_options_extra(
            provider_name="zai",
            model="glm-4.7-flashx",
            reasoning_level="high",
        )
        assert low_extra["thinking_enabled"] is False
        assert high_extra["thinking_enabled"] is True


class TestSectionInputAssembly:
    def setup_method(self):
        self.generator = DeckGenerator()

    def _request(self, valuation_input=None):
        return DeckGenerateRequest(
            ticker="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            fund_constraints=FundConstraints(
                time_horizon="12-24 months",
                risk_profile="moderate",
            ),
            sections=["valuation_summary"],
            provider=Provider.GEMINI,
            valuation_input=valuation_input,
        )

    def test_comps_step_peers_flow_into_valuation_context(self):
        inputs = self.generator._assemble_section_inputs(
            ticker="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            fund_constraints={"time_horizon": "12-24 months", "risk_profile": "moderate"},
            comps_summary=None,
            dcf_summary=None,
            requested_sections=["valuation_summary"],
            request=self._request(),
            comp_tickers=["MSFT", "GOOGL"],
        )

        assert inputs["comp_tickers"] == ["MSFT", "GOOGL"]
        assert inputs["valuation"]["peer_tickers"] == ["MSFT", "GOOGL"]
        assert inputs["valuation"]["methods"] == ["relative"]

    def test_comps_step_peers_do_not_overwrite_explicit_valuation_peers(self):
        inputs = self.generator._assemble_section_inputs(
            ticker="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            fund_constraints={"time_horizon": "12-24 months", "risk_profile": "moderate"},
            comps_summary=None,
            dcf_summary=None,
            requested_sections=["valuation_summary"],
            request=self._request(
                valuation_input=ValuationInput(
                    methods=["dcf"],
                    peer_tickers=["NVDA"],
                    price_target="$250",
                )
            ),
            comp_tickers=["MSFT", "GOOGL"],
        )

        assert inputs["valuation"]["peer_tickers"] == ["NVDA"]
        assert inputs["valuation"]["methods"] == ["dcf", "relative"]
        assert inputs["valuation"]["price_target"] == "$250"

    def test_computed_inputs_include_comps_and_dcf_data(self):
        comps_data = {"target": {"ticker": "AAPL"}, "comparables": []}
        dcf_data = {"valuation": {"targetPrice": 250.0}}

        inputs = self.generator._assemble_section_inputs(
            ticker="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            fund_constraints={"time_horizon": "12-24 months", "risk_profile": "moderate"},
            comps_summary="comps",
            dcf_summary="dcf",
            requested_sections=["valuation_summary"],
            request=self._request(),
            comps_data=comps_data,
            dcf_data=dcf_data,
        )

        assert inputs["computed_inputs"]["comps_table"] == comps_data
        assert inputs["computed_inputs"]["dcf_valuation"] == dcf_data
        assert inputs["comps_table"] == comps_data
        assert inputs["dcf_valuation"] == dcf_data
        assert inputs["include_dcf"] is True
