import pytest
from pydantic import ValidationError

from app.deck.api.schemas import DeckPptxDesignSpecRequest
from app.deck.services.gemini_pptx_design_service import (
    GeminiPptxDesignError,
    GeminiPptxDesignService,
)
from app.deck.services.llm_base import LLMResponse


def _sample_deck():
    return {
        "ticker": "ACN",
        "metadata": {"company_name": "Accenture"},
        "results": [
            {
                "section_id": "overview",
                "slides": [
                    {
                        "slide_id": "overview_1",
                        "title": "Accenture Overview",
                        "bullets": [
                            {"text": "Global professional services company", "source_needed": False},
                        ],
                    },
                    {
                        "slide_id": "overview_2",
                        "title": "Catalyst Timeline",
                        "bullets": [
                            {"text": "2026: AI bookings continue to scale"},
                        ],
                    },
                ],
            }
        ],
    }


class _FakeProvider:
    def __init__(self):
        self.calls = 0

    def generate_json(self, *_args, **_kwargs):
        self.calls += 1
        return LLMResponse(
            content={
                "version": "gemini-pptx-design-v1",
                "provider": "gemini",
                "model": "gemini-3.1-pro-preview",
                "cached": False,
                "theme": {
                    "name": "institutional_navy",
                    "navy": "172554",
                    "blue": "1E3A8A",
                    "accent": "38BDF8",
                    "bg": "F8FAFC",
                    "card": "FFFFFF",
                    "ink": "0F172A",
                    "text": "334155",
                    "muted": "64748B",
                    "border": "CBD5E1",
                    "head_font_face": "Aptos Display",
                    "body_font_face": "Aptos",
                },
                "slides": [
                    {
                        "section_id": "overview",
                        "slide_index": 0,
                        "slide_id": "overview_1",
                        "layout": "cards",
                        "emphasis": "balanced",
                        "accent_color": "38BDF8",
                        "rationale": "Dashboard-style overview.",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
                "latency_ms": 10,
            },
            raw_response="{}",
            model="gemini-3.1-pro-preview",
            provider="gemini",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )


def test_gemini_design_request_requires_slides():
    with pytest.raises(ValidationError):
        DeckPptxDesignSpecRequest(deck={"results": []})


def test_gemini_design_service_uses_cache_and_backfills_missing_slides(tmp_path, monkeypatch):
    fake_provider = _FakeProvider()
    monkeypatch.setattr(
        "app.deck.services.gemini_pptx_design_service.get_provider",
        lambda *_args, **_kwargs: fake_provider,
    )
    service = GeminiPptxDesignService(
        api_key="test-key",
        model="gemini-3.1-pro-preview",
        cache_dir=str(tmp_path),
    )

    first = service.create_spec(deck=_sample_deck(), title="ACN deck")
    second = service.create_spec(deck=_sample_deck(), title="ACN deck")

    assert first.cached is False
    assert second.cached is True
    assert fake_provider.calls == 1
    assert len(first.spec["slides"]) == 2
    assert first.spec["slides"][1]["layout"] == "cards"


def test_gemini_design_service_requires_api_key(tmp_path):
    with pytest.raises(GeminiPptxDesignError, match="Gemini export requires"):
        GeminiPptxDesignService(
            api_key="",
            model="gemini-3.1-pro-preview",
            cache_dir=str(tmp_path),
        )


def test_compact_deck_adds_comps_section_when_comps_data_exists(tmp_path):
    service = GeminiPptxDesignService(
        api_key="test-key",
        model="gemini-3.1-pro-preview",
        cache_dir=str(tmp_path),
    )
    deck = {
        **_sample_deck(),
        "computed_inputs": {
            "comps_table": {
                "target": {
                    "ticker": "ACN",
                    "snapshot": {"sharePrice": 100, "marketCap": 1000},
                },
                "comparables": [
                    {"ticker": "IBM", "snapshot": {"sharePrice": 90, "marketCap": 900}},
                ],
            }
        },
    }

    compact = service._compact_deck(deck)

    comps_section = compact["sections"][-1]
    assert comps_section["section_id"] == "comparable_companies"
    assert compact["comps_table"]["subject_index"] == 0


def test_dedupe_preserves_multi_ref_two_column_blocks(tmp_path):
    service = GeminiPptxDesignService(
        api_key="test-key",
        model="gemini-3.1-pro-preview",
        cache_dir=str(tmp_path),
    )
    slide_design = {
        "blocks": [
            {
                "type": "two_column_panel",
                "text_refs": ["bullet_0", "bullet_1", "bullet_2", "bullet_3"],
            }
        ]
    }
    slide = {"bullets": ["one", "two", "three", "four"]}

    service._dedupe_block_refs(slide_design, slide)

    assert slide_design["blocks"][0]["text_refs"] == [
        "bullet_0",
        "bullet_1",
        "bullet_2",
        "bullet_3",
    ]
