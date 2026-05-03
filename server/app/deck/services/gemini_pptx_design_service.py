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

PROMPT_VERSION = "gemini-pptx-design-v6"


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
            "ROLE\n"
            "You are a layout planning engine for institutional equity research pitch books. "
            "You convert structured slide content into a strict JSON layout blueprint that a pptxgenjs "
            "renderer will execute. You output JSON only matching the supplied schema. No prose, no "
            "markdown, no comments.\n\n"

            "PRIME DIRECTIVES\n"
            "1. Preserve every fact verbatim. Do not invent, round, or smooth tickers, prices, ratios, "
            "percentages, dates, ranges, names, or claims.\n"
            "2. Reference text only by key path: title or bullet_N (zero-based). The renderer resolves "
            "keys to text. Never paste raw strings into text_refs or text_source.\n"
            "3. If a value is missing, null, not provided, or N/A, do not render a block for it. "
            "Do not fill with placeholder text.\n"
            "4. If input contains VERIFY:, Low confidence:, confidence: low, or a warning flag, surface "
            "it as a text_box footnote in muted italic style and add it to the slide warnings array.\n"
            "5. Notes mixing speaker commentary and disclosure metadata: route narrative commentary "
            "(starting with Highlight, Emphasize, Address) to speaker_notes. Route disclosure metadata "
            "(confidence, source flags) to a footnote text_box.\n"
            "6. Output one JSON object per call matching the supplied schema. No trailing commas.\n\n"

            "CANVAS (inches, 13.33 x 7.5)\n"
            "Safe margins: left 0.4, right 0.4, top 0.3, bottom 0.3. "
            "Title band: x 0.4, y 0.3, w 12.53, h 0.55. Content body: y_min 1.25, y_max 6.85. "
            "Footer: y 7.05. Inter-block gutter: 0.2 horizontal, 0.18 vertical. "
            "Never let blocks overlap or cross title/footer bands.\n\n"

            "STYLE TOKENS (map to block style fields)\n"
            "style.fill values: white (paper), light_gray (panel), navy (dark emphasis), accent (warm). "
            "style.text_color values: navy (ink primary), text (body), mid_gray (muted/footnote), "
            "white (on dark fills), positive (green valence), negative (red valence). "
            "style.header_color values: navy, accent, text, positive, negative. "
            "style.border values: none, hairline_navy, hairline_gray. "
            "style.alignment: left (default), center, right. "
            "Accent is reserved for ONE element per slide: a recommendation badge, a highlighted comp row, "
            "a hero metric, or a target price. Do not over-accent.\n\n"

            "TYPOGRAPHY\n"
            "Fonts: Aptos Display for titles and hero numbers, Aptos for everything else. "
            "Sizes: cover_title 38pt, section_title 28pt, slide_title 18pt, kicker 12pt, metric_value 28pt, "
            "metric_label 9pt, body 10pt, label 9pt, footnote 7pt, badge 7pt. "
            "Weights: 700 for titles and metrics, 600 for kickers and labels, 400 for body.\n\n"

            "BLOCK TYPES (using schema field names)\n"
            "All blocks use: type, x, y, w, h, text_refs, text_source, static_text, label, title, body, "
            "accent_color, tone, severity, highlight_row_index, style.\n\n"

            "hero_callout: Main takeaway. text_refs=[bullet_0], label=design heading like Key Takeaway. "
            "tone=neutral|positive|negative|accent. style.fill=white.\n"
            "metric_tile: KPI fact. text_refs=[bullet_N] for the value, label=metric name. "
            "tone for delta valence. w 2.4-3.2, h 1.2-1.6. Skip if value is not provided.\n"
            "bullet_card: Grouped narrative. text_refs=[bullet_1, bullet_2, ...] max 5. "
            "label=card heading. style.fill=white or light_gray. "
            "If confidence is low, set static_text=[low confidence].\n"
            "text_box: Footnotes/disclosures. text_refs=[bullet_N], style.text_color=mid_gray, "
            "style.alignment=left. Use sparingly.\n"
            "timeline_item: Dated milestone. text_refs=[bullet_N], label=year or date. "
            "tone=neutral|positive|negative|accent.\n"
            "two_column_panel: Contrasting views. text_refs=[bullet_0, bullet_1, bullet_2, bullet_3], "
            "static_text=[Left Heading, Right Heading]. "
            "tone for left valence via accent_color.\n"
            "risk_box: Risk/mitigant. text_refs=[bullet_N], label=risk title. "
            "severity=low|medium|high. style.fill=white, style.border=hairline_gray.\n"
            "valuation_callout: Price target/DCF. text_refs=[bullet_N], label=method name. "
            "static_text=[method label]. tone=positive|negative|neutral.\n"
            "section_badge: Section divider slide. text_refs=[title], label=section name. "
            "Used on its own slide.\n"
            "comps_table: Comparable companies table. text_refs=[] (renderer reads comps from deck data). "
            "highlight_row_index=0 for the subject ticker. label=table heading. "
            "x 0.4, y 1.25, w 12.53, h up to 5.0.\n"
            "cover_block: Title slide. text_refs=[title], label=ticker. "
            "Used on its own slide.\n\n"

            "ARCHETYPE LAYOUTS\n"
            "Pick by section_id or infer from slide content. Match the actual pipeline output.\n\n"

            "comparable_companies: One comps_table at x 0.4 y 1.25 w 12.53, highlight subject row. "
            "One footnote text_box below for data-as-of disclosure.\n"
            "company_snapshot: Top hero_callout full width h 0.9 with positioning sentence. "
            "Left half w 6.0 bullet_card What and how with 3-5 bullets. "
            "Right half w 6.13 bullet_card Money model with up to 4 bullets.\n"
            "business_profile: Left bullet_card listing segments. Right stacked bullet_cards for "
            "Customers, Footprint, Proof Points. Confidence badges where relevant.\n"
            "company_overview: Top hero_callout with ecosystem thesis. Body two_column_panel "
            "left What right Who with 3 bullets each.\n"
            "why_now: Top hero_callout with thesis (tone accent). Body bullet_card with 3-4 supporting "
            "points full width. Footnote text_box with valuation caveat.\n"
            "investment_catalysts: Two bullet_cards: left Near term right Medium term. "
            "Bottom risk_box at full width severity medium.\n"
            "company_history: Top hero_callout. Body row of 4-5 timeline_items evenly spaced. "
            "VERIFY markers go to footnote text_box.\n"
            "business_model: Top hero_callout with revenue flow. Body two_column_panel "
            "left Products right Customers.\n"
            "segments_unit_economics: Left two-thirds bullet_card with segments. "
            "Right one-third stacked metric_tiles or single bullet_card.\n"
            "industry_overview: Top hero_callout. Body 3 bullet_cards across w 4.05 each "
            "covering growth drivers, structural trends, additional drivers.\n"
            "competitive_landscape: Top bullet_card listing competitors full width. "
            "Bottom two_column_panel left Moat pillars right Porter forces.\n"
            "historical_performance: Top hero_callout (data unavailable if no data). "
            "Body 3 metric_tiles if metrics present, else single bullet_card.\n"
            "current_setup: Single bullet_card full width with up to 5 bullets. Confidence badge.\n"
            "management_incentives: Two stacked bullet_cards: Management and Incentives.\n"
            "ownership_governance: Two stacked bullet_cards: Ownership and Governance.\n"
            "capital_structure: Left bullet_card Leverage profile. Right 2x2 metric_tiles.\n"
            "liquidity_share_count: Two stacked bullet_cards: Liquidity and Share count.\n"
            "swot_strengths_weaknesses: two_column_panel left Strengths (tone positive) "
            "right Weaknesses (tone negative). Up to 4 bullets each.\n"
            "swot_opportunities_threats: two_column_panel left Opportunities (tone positive) "
            "right Threats (tone negative). Up to 4 bullets each.\n"
            "key_drivers_kpis: Top hero_callout with takeaway. Body 3 bullet_cards across "
            "one per KPI.\n"
            "sector_invariants: Single bullet_card full width. Low confidence badge if applicable.\n"
            "investment_thesis: Top hero_callout with thesis (tone accent). Body 3 bullet_cards "
            "across as pillars.\n"
            "variant_view: two_column_panel left Market believes (tone neutral) right We believe "
            "(tone accent). Below risk_box What would change our mind severity medium.\n"
            "catalysts_timeline: Top hero_callout. Body row of 4 timeline_items.\n"
            "valuation_framework: Top hero_callout. Body 3 bullet_cards across, one per method.\n"
            "valuation_price_target: Left valuation_callout with DCF target. Right bullet_card "
            "Multiples context.\n"
            "recommendation: Centered hero_callout y 1.5 w 12.53 h 1.2 (tone from recommendation). "
            "Below 3 metric_tiles. Below bullet_card Monitoring plan.\n\n"

            "LAYOUT QUALITY RULES\n"
            "Maximum 6 rendered blocks per slide excluding title and footer. "
            "Prefer 3 or 4 equal columns; for uneven use 60/40 or 67/33. "
            "Align block left edges. Every non-cover slide must have a title. "
            "Do not place two metric_tiles taller than 1.6 in the same row. "
            "If body is sparse (fewer than 3 blocks), increase block heights and white space; "
            "do not add decorative blocks. Vary arrangements across consecutive slides.\n\n"

            "DISCLOSURE HANDLING\n"
            "not provided / null / N/A: do not render a value tile, surface in a bullet or warning.\n"
            "VERIFY: route to footnote text_box in mid_gray italic.\n"
            "confidence: low: set static_text=[low confidence] on the affected card.\n"
            "Speaker commentary in Notes: route to speaker_notes output, not to rendered blocks.\n\n"

            "FAILURE MODES TO AVOID\n"
            "- Inventing a number to fill a metric_tile: forbidden, skip the tile.\n"
            "- Rewriting a bullet for clarity: forbidden, reference by key path only.\n"
            "- Dropping VERIFY or low confidence flags: forbidden, route to footnote or warnings.\n"
            "- Adding decorative blocks for empty space: forbidden, increase whitespace.\n"
            "- Using accent on more than one block per slide.\n"
            "- Letting blocks exceed the body region or overlap.\n"
            "- Concatenating speaker commentary into rendered blocks.\n"
            "- Reusing the same bullet_N in multiple blocks on the same slide.\n\n"

            "Return JSON only matching the supplied schema."
        )

    def _user_prompt(self, *, compact_deck: dict[str, Any], title: str | None) -> str:
        return (
            "Create a PPTX design blueprint for this deck. Return one slide design item for every slide "
            "in the same section_id + slide_index order. Use layout=blueprint with 3-6 positioned blocks. "
            "Set the archetype field on each slide design to the matching archetype from the system prompt. "
            "Do not repeat the same arrangement on consecutive slides.\n\n"
            "For each slide, choose blocks that map to the source content:\n"
            "- hero_callout for the main takeaway, usually text_refs [bullet_0].\n"
            "- metric_tile for short KPI-like facts.\n"
            "- bullet_card for supporting arguments.\n"
            "- timeline_item for dated milestones.\n"
            "- two_column_panel for contrasting views (market vs variant, strengths vs weaknesses).\n"
            "- risk_box for risk/mitigant items.\n"
            "- valuation_callout for price target, DCF, upside content.\n"
            "- comps_table for comparable companies data (renderer reads comps from deck data).\n\n"
            "Use text_refs [bullet_0], [bullet_1], etc. to reference content. Never duplicate the same "
            "bullet_N across blocks on the same slide. For multiple blocks, assign sequential distinct "
            "bullet references. Every block must have x, y, w, h in inches within the content body region.\n\n"
            "Slide playbook: executive summary uses full-width hero plus 2x2 cards; KPI slides use "
            "metric tile grids; valuation uses top valuation_callout plus supporting panels; variant view "
            "uses two_column_panel for Market believes vs We believe plus risk_box; catalysts use "
            "timeline_item blocks; risk slides use risk_box; SWOT uses two_column_panel with tone; "
            "comparable companies uses a single comps_table block with highlight_row_index=0.\n\n"
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
            section_id = str(section.get("section_id") or "section")[:120]
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
                        "archetype": section_id.replace("-", "_"),
                    }
                )
            if compact_slides:
                compact_sections.append(
                    {
                        "section_id": section_id,
                        "slides": compact_slides,
                    }
                )

        # Include comps data if available (compact form for token efficiency)
        comps_compact = None
        computed_inputs = deck.get("computed_inputs") if isinstance(deck.get("computed_inputs"), dict) else {}
        comps_raw = computed_inputs.get("comps_table") if isinstance(computed_inputs.get("comps_table"), dict) else None
        if comps_raw:
            try:
                headers = ["Symbol", "Price", "Mkt Cap", "EV", "Fwd P/E", "P/S", "P/B", "EV/EBITDA", "EV/Rev", "Margin", "ROE"]
                rows = []
                target = comps_raw.get("target")
                if isinstance(target, dict):
                    snap = target.get("snapshot") or {}
                    rows.append([target.get("ticker", ""), snap.get("sharePrice"), snap.get("marketCap"),
                                 snap.get("enterpriseValue"), snap.get("forwardPE"), snap.get("priceSales"),
                                 snap.get("priceBook"), snap.get("evEbitda"), snap.get("evRevenue"),
                                 snap.get("profitMargin"), snap.get("roe")])
                for comp in (comps_raw.get("comparables") or [])[:5]:
                    if not isinstance(comp, dict):
                        continue
                    snap = comp.get("snapshot") or {}
                    rows.append([comp.get("ticker", ""), snap.get("sharePrice"), snap.get("marketCap"),
                                 snap.get("enterpriseValue"), snap.get("forwardPE"), snap.get("priceSales"),
                                 snap.get("priceBook"), snap.get("evEbitda"), snap.get("evRevenue"),
                                 snap.get("profitMargin"), snap.get("roe")])
                if rows:
                    comps_compact = {"headers": headers, "rows": rows, "subject_index": 0}
            except Exception:
                comps_compact = None

        if comps_compact and not any(
            section.get("section_id") in {"comparable_companies", "comparables"}
            for section in compact_sections
        ):
            compact_sections.append(
                {
                    "section_id": "comparable_companies",
                    "slides": [
                        {
                            "slide_index": 0,
                            "slide_id": "comparable_companies_1",
                            "title": "Comparable Companies",
                            "bullets": ["Comparable-company trading metrics from computed market data."],
                            "layout_hints": {
                                "style": "table",
                                "suggested_visual": "comps_table",
                                "max_bullets": 1,
                            },
                            "archetype": "comparable_companies",
                        }
                    ],
                }
            )

        result: dict[str, Any] = {
            "ticker": deck.get("ticker") or metadata.get("ticker"),
            "company_name": deck.get("company_name") or metadata.get("company_name"),
            "title": deck.get("title") or metadata.get("title"),
            "sections": compact_sections,
        }
        if comps_compact:
            result["comps_table"] = comps_compact
        return result

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

            block_type = str(block.get("type") or "")
            max_refs = 1
            if block_type == "two_column_panel":
                max_refs = 4
            elif block_type == "bullet_card":
                max_refs = 5
            elif block_type == "text_box":
                max_refs = 2

            if block_type in {"comps_table", "cover_block", "section_badge"}:
                block["text_refs"] = []
                block["text_source"] = "title"
            elif cleaned_refs:
                block["text_refs"] = cleaned_refs[:max_refs]
                block["text_source"] = cleaned_refs[0]
            else:
                block["text_refs"] = []
                block["text_source"] = "title"

    def _fallback_blocks(self, slide: dict[str, Any]) -> list[dict[str, Any]]:
        bullets = slide.get("bullets") or []
        title = str(slide.get("title") or "").lower()
        archetype = str(slide.get("archetype") or "").lower()
        blocks: list[dict[str, Any]] = []

        if "comparable" in title or archetype in {"comparable_companies", "comparables"}:
            return [{
                "type": "comps_table",
                "x": 0.4,
                "y": 1.25,
                "w": 12.53,
                "h": 5.0,
                "text_source": "title",
                "text_refs": [],
                "static_text": ["Comparable companies"],
                "label": "Comparable Companies",
                "title": "",
                "body": "",
                "accent_color": "38BDF8",
                "highlight_row_index": 0,
                "style": {
                    "fill": "white",
                    "text_color": "text",
                    "header_color": "navy",
                    "border": "hairline_gray",
                    "alignment": "left",
                },
            }]

        if "timeline" in title or archetype in {"catalysts_timeline", "company_history"}:
            for index, _bullet in enumerate(bullets[:4]):
                blocks.append({
                    "type": "timeline_item",
                    "x": 0.65 + index * 3.02,
                    "y": 2.3,
                    "w": 2.72,
                    "h": 2.15,
                    "text_source": f"bullet_{index}",
                    "text_refs": [f"bullet_{index}"],
                    "static_text": [],
                    "label": "",
                    "title": "",
                    "body": "",
                    "accent_color": "38BDF8",
                    "style": {
                        "fill": "white",
                        "text_color": "text",
                        "header_color": "accent",
                        "border": "none",
                        "alignment": "left",
                    },
                })
            return blocks

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
