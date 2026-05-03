"""Gemini-generated design specs for local PPTX rendering."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.deck.api.schemas import DeckPptxDesignSpecResponse
from app.deck.services.llm_base import LLMError, LLMOptions, get_provider
from app.deck.utils.logging import get_logger

logger = get_logger(__name__)

PROMPT_VERSION = "gemini-pptx-design-v4"


class GeminiPptxDesignError(Exception):
    """Raised when Gemini cannot produce a valid PPTX design spec."""


@dataclass(frozen=True)
class GeminiPptxDesignResult:
    spec: dict[str, Any]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False
    usage: dict[str, int] = field(default_factory=dict)


class GeminiPptxDesignService:
    """Create compact layout instructions for the browser PPTX renderer."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        cache_dir: str,
        max_tokens: int = 8192,
        timeout_seconds: int = 120,
    ) -> None:
        if not api_key:
            raise GeminiPptxDesignError("Gemini export requires Vertex AI configuration or GEMINI_API_KEY")
        self.api_key = api_key
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def create_spec(self, *, deck: dict[str, Any], title: str | None = None) -> GeminiPptxDesignResult:
        compact_deck = self._compact_deck(deck)
        if not compact_deck["sections"]:
            raise GeminiPptxDesignError("Deck must contain at least one slide")

        cache_key = self._cache_key(compact_deck=compact_deck, title=title)
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            spec = json.loads(cache_path.read_text())
            spec["cached"] = True
            return GeminiPptxDesignResult(
                spec=spec,
                model=str(spec.get("model") or self.model),
                cached=True,
                usage=dict(spec.get("usage") or {}),
            )

        provider = get_provider("gemini", self.api_key, self.model)
        system_prompt = self._system_prompt()
        user_prompt = self._user_prompt(compact_deck=compact_deck, title=title)
        schema = DeckPptxDesignSpecResponse.model_json_schema()

        started = time.monotonic()
        try:
            response = provider.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=schema,
                options=LLMOptions(
                    temperature=0.4,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout_seconds,
                    reasoning_level="low",
                    extra={"model": self.model},
                ),
            )
        except LLMError as exc:
            raise GeminiPptxDesignError(f"Gemini PPTX design spec failed: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        spec = DeckPptxDesignSpecResponse.model_validate(response.content).model_dump()
        spec["version"] = PROMPT_VERSION
        spec["provider"] = "gemini"
        spec["model"] = response.model
        spec["cached"] = False
        spec["usage"] = self._normalize_usage(response.usage)
        spec["latency_ms"] = latency_ms
        self._ensure_slide_coverage(spec, compact_deck)
        cache_path.write_text(json.dumps(spec, indent=2, sort_keys=True))

        usage = dict(spec.get("usage") or {})
        return GeminiPptxDesignResult(
            spec=spec,
            model=response.model,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency_ms,
            cached=False,
            usage=usage,
        )

    def _system_prompt(self) -> str:
        return (
            "You are an investment banking deck layout planner. Return only strict JSON matching the "
            "supplied schema. No prose, no markdown, no comments. You write a reusable bulge-bracket "
            "style layout blueprint for a local pptxgenjs renderer.\n\n"
            "Design system: deep navy #0A2540 for titles, rules, and primary emphasis; one warm accent "
            "#7A1F2B or #B8860B for selective emphasis; white page ground; light gray #F4F5F7 for card "
            "fills; mid gray #6B7280 for body/source text; dark gray #374151 for table/card borders. "
            "Use restrained IB styling: flat cards, hairline rules, almost no shadows, high alignment, "
            "medium-high density with visible whitespace. No gradients or decorative clutter.\n\n"
            "Canvas is 13.33 x 7.5 inches. Title band is y=0.3 to 1.0, footer band y=7.05 to 7.4, "
            "content band y=1.1 to 7.0. Outer margins are 0.5 inches. Prefer full width 12.33, halves "
            "6.07, thirds 3.97, quarters 2.92, or 60/40 splits 7.40 + 4.73. Use 3-6 blocks per slide "
            "except cover/divider. Blocks must not overlap; preserve 0.15+ inch gutters.\n\n"
            "Supported block types only: hero_callout, metric_tile, bullet_card, text_box, timeline_item, "
            "two_column_panel, risk_box, valuation_callout, section_badge. Use hero_callout for the main "
            "takeaway, metric_tile for KPI-like facts, bullet_card for grouped narrative, timeline_item "
            "for sequenced dates/catalysts, risk_box for risk/mitigant content, valuation_callout for "
            "target/multiple/DCF/upside content.\n\n"
            "Preserve facts. Never invent financial claims, numbers, dates, target prices, ratings, or "
            "company facts. Factual content must be referenced through text_refs such as title or bullet_0. "
            "Do not reuse the same bullet_N in multiple blocks on the same slide. Use bullet_0 for the hero "
            "only, then use bullet_1, bullet_2, etc. for supporting blocks. If there are fewer bullets than "
            "blocks, create fewer blocks instead of duplicating a bullet. Timeline and KPI blocks must map "
            "to distinct bullet_N values. "
            "static_text may only contain design labels like Key Takeaway, Market believes, We believe, "
            "Risks, Catalysts, BEAR, BASE, BULL, Target, Upside. Use body only for non-factual labels or "
            "leave it empty. Vary slide arrangements across consecutive slides."
        )

    def _user_prompt(self, *, compact_deck: dict[str, Any], title: str | None) -> str:
        return (
            "Create a PPTX design blueprint for this deck using canonical bulge-bracket investment "
            "banking pitch deck conventions. Return one slide design item for every slide in the same "
            "section_id + slide_index order. Prefer layout=blueprint with 3-6 positioned blocks per slide. "
            "Do not repeat the same arrangement on consecutive slides.\n\n"
            "For each slide, choose blocks that map to the source content:\n"
            "- hero_callout for the main takeaway, usually text_source bullet_0.\n"
            "- metric_tile for short KPI-like bullets.\n"
            "- bullet_card for supporting arguments.\n"
            "- timeline_item for dated milestones/catalysts.\n"
            "- two_column_panel for market view vs variant view or competitive contrasts.\n"
            "- risk_box for risk/mitigant items.\n"
            "- valuation_callout for price target, multiple, DCF, upside/downside, or valuation takeaway.\n\n"
            "Prefer text_refs over text_source. Use text_refs values only: title or bullet_N where N is "
            "a zero-based bullet index. Never use the same bullet_N twice on the same slide unless the "
            "slide has only one bullet and only one factual block. For multiple KPI/timeline/card blocks, "
            "assign sequential distinct sources: bullet_0, bullet_1, bullet_2, bullet_3. Every block must "
            "have x, y, w, h coordinates in inches. Keep "
            "layouts clean with spacing; do not overlap blocks. Use style tokens when helpful: fill can "
            "be white, light_gray, navy, or accent; text_color/header_color can be navy, accent, text, "
            "mid_gray, white, positive, or negative; border can be none, hairline_navy, or hairline_gray. "
            "If a slide is naturally SWOT/timeline/valuation/two_column, still include useful blocks.\n\n"
            "Slide playbook: executive summary uses a full-width hero banner plus 2x2 cards; KPI slides "
            "use a 2x3 metric tile grid; valuation uses a top valuation_callout plus two supporting panels; "
            "variant view uses three vertical cards for Market believes / We believe / We're wrong if; "
            "catalysts use timeline_item blocks along a horizontal strip; risk slides use risk_box grids; "
            "recommendation uses one large hero_callout plus three recap cards.\n\n"
            f"Export title: {title or compact_deck.get('title') or 'Investment pitch deck'}\n"
            f"Deck JSON:\n{json.dumps(compact_deck, ensure_ascii=True, separators=(',', ':'))}"
        )

    def _compact_deck(self, deck: dict[str, Any]) -> dict[str, Any]:
        metadata = deck.get("metadata") if isinstance(deck.get("metadata"), dict) else {}
        sections = deck.get("results") or deck.get("sections") or []
        compact_sections: list[dict[str, Any]] = []
        for section in sections if isinstance(sections, list) else []:
            if not isinstance(section, dict):
                continue
            compact_slides: list[dict[str, Any]] = []
            for index, slide in enumerate(section.get("slides") or []):
                if not isinstance(slide, dict):
                    continue
                bullets = []
                for bullet in slide.get("bullets") or []:
                    if isinstance(bullet, dict):
                        text = str(bullet.get("text") or "")[:240]
                    else:
                        text = str(bullet)[:240]
                    if text.strip():
                        bullets.append(text.strip())
                compact_slides.append(
                    {
                        "slide_index": index,
                        "slide_id": slide.get("slide_id"),
                        "title": str(slide.get("title") or "")[:140],
                        "bullets": bullets[:6],
                        "layout_hints": slide.get("layout_hints") or {},
                    }
                )
            if compact_slides:
                compact_sections.append(
                    {
                        "section_id": str(section.get("section_id") or "section")[:120],
                        "slides": compact_slides,
                    }
                )

        return {
            "ticker": deck.get("ticker") or metadata.get("ticker"),
            "company_name": deck.get("company_name") or metadata.get("company_name"),
            "title": deck.get("title") or metadata.get("title"),
            "sections": compact_sections,
        }

    def _ensure_slide_coverage(self, spec: dict[str, Any], compact_deck: dict[str, Any]) -> None:
        existing = {
            (str(item.get("section_id")), int(item.get("slide_index", -1)))
            for item in spec.get("slides", [])
            if isinstance(item, dict)
        }
        for section in compact_deck["sections"]:
            section_id = section["section_id"]
            for slide in section["slides"]:
                key = (section_id, int(slide["slide_index"]))
                if key not in existing:
                    spec.setdefault("slides", []).append(
                        {
                            "section_id": section_id,
                            "slide_index": slide["slide_index"],
                            "slide_id": slide.get("slide_id"),
                            "layout": "cards",
                            "emphasis": "balanced",
                            "accent_color": "38BDF8",
                            "rationale": "Fallback local layout for omitted Gemini design item.",
                            "blocks": self._fallback_blocks(slide),
                        }
                    )
                    continue

                for item in spec.get("slides", []):
                    if not isinstance(item, dict):
                        continue
                    if (
                        item.get("section_id") == section_id
                        and int(item.get("slide_index", -1)) == int(slide["slide_index"])
                        and not item.get("blocks")
                    ):
                        item["blocks"] = self._fallback_blocks(slide)
                    if (
                        item.get("section_id") == section_id
                        and int(item.get("slide_index", -1)) == int(slide["slide_index"])
                    ):
                        self._dedupe_block_refs(item, slide)

    def _dedupe_block_refs(self, slide_design: dict[str, Any], slide: dict[str, Any]) -> None:
        bullets = slide.get("bullets") or []
        if not bullets:
            return

        available = [f"bullet_{index}" for index in range(len(bullets))]
        used: set[str] = set()
        next_index = 0

        for block in slide_design.get("blocks") or []:
            if not isinstance(block, dict):
                continue

            refs = block.get("text_refs")
            if not isinstance(refs, list) or not refs:
                source = block.get("text_source")
                refs = [source] if isinstance(source, str) and source else []

            cleaned_refs: list[str] = []
            for ref in refs:
                if not isinstance(ref, str):
                    continue
                if not ref.startswith("bullet_"):
                    cleaned_refs.append(ref)
                    continue
                if ref not in used and ref in available:
                    cleaned_refs.append(ref)
                    used.add(ref)
                    continue

                replacement = None
                while next_index < len(available):
                    candidate = available[next_index]
                    next_index += 1
                    if candidate not in used:
                        replacement = candidate
                        break
                if replacement:
                    cleaned_refs.append(replacement)
                    used.add(replacement)

            if not cleaned_refs and next_index < len(available):
                replacement = available[next_index]
                next_index += 1
                cleaned_refs = [replacement]
                used.add(replacement)

            if cleaned_refs:
                block["text_refs"] = cleaned_refs[:2]
                block["text_source"] = cleaned_refs[0]
            else:
                block["text_refs"] = []
                block["text_source"] = "title"

    def _fallback_blocks(self, slide: dict[str, Any]) -> list[dict[str, Any]]:
        bullets = slide.get("bullets") or []
        blocks: list[dict[str, Any]] = []
        if bullets:
            blocks.append({
                "type": "hero_callout",
                "x": 0.65,
                "y": 1.62,
                "w": 12.0,
                "h": 1.1,
                "text_source": "bullet_0",
                "text_refs": ["bullet_0"],
                "static_text": ["Key Takeaway"],
                "label": "Key Takeaway",
                "title": "",
                "body": "",
                "accent_color": "38BDF8",
                "style": {
                    "fill": "white",
                    "text_color": "navy",
                    "header_color": "accent",
                    "border": "hairline_gray",
                    "alignment": "left",
                },
            })
        for index, _bullet in enumerate(bullets[1:4], start=1):
            blocks.append({
                "type": "bullet_card",
                "x": 0.65 + (index - 1) * 4.12,
                "y": 3.18,
                "w": 3.82,
                "h": 1.55,
                "text_source": f"bullet_{index}",
                "text_refs": [f"bullet_{index}"],
                "static_text": [],
                "label": "",
                "title": "",
                "body": "",
                "accent_color": "38BDF8",
                "style": {
                    "fill": "light_gray",
                    "text_color": "text",
                    "header_color": "navy",
                    "border": "hairline_gray",
                    "alignment": "left",
                },
            })
        return blocks

    def _cache_key(self, *, compact_deck: dict[str, Any], title: str | None) -> str:
        payload = {
            "deck": compact_deck,
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "title": title or "",
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _normalize_usage(self, usage: dict[str, Any]) -> dict[str, int]:
        return {
            "prompt_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
