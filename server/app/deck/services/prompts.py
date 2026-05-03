"""
Shared prompt fragments used by the deck generation pipeline.

Section-specific prompting now lives inside modular SectionSpec implementations.
This module intentionally keeps only cross-section prompts still used by the
orchestrator.
"""

from __future__ import annotations

INVESTMENT_DECK_DESIGN_PROMPT = """## INVESTMENT PITCH DECK DESIGN SKILL
Think like an investment banking associate preparing slides for an investment
committee. Each slide should make one clear argument and give the presenter
material to defend it.

SLIDE STRATEGY:
- Write the slide title as the takeaway, not the topic.
- Prefer synthesis over inventory; combine related facts into a conclusion.
- Make every slide answer "so what?" for a long or short investment decision.
- Use the user's position, horizon, and risk profile to frame material.
- Keep one governing message per slide; move supporting detail to notes.

INVESTOR WRITING RULES:
- Use concise, specific, institutionally toned language.
- Avoid generic claims such as "strong brand", "growth opportunities", or
  "competitive market" unless tied to a concrete mechanism.
- Surface uncertainty clearly: say what is known, what is inferred, and what
  would need verification.
- Do not add decorative adjectives. Emphasize mechanism, evidence, magnitude,
  timing, and risk.

VISUAL DESIGN INTENT:
- When layout_hints are available, choose the most presentation-ready style:
  snapshot_header for identity and quick stats, two_column for contrasts,
  timeline for events, table for comps/KPIs, bar_chart or line_chart for trends,
  waterfall for valuation bridge, and bullets only when no clearer structure
  fits.
- Suggest a visual only when the underlying data supports it.
- Keep bullets short enough to fit on a slide. Put caveats, backups, and extra
  details in speaker notes.
"""


SYSTEM_PROMPT = f"""You are an expert investment analyst assistant specializing in creating professional pitch deck content for student investment funds. Your role is to generate clear, concise, and fund-ready slide content.

CRITICAL RULES:
1. OUTPUT FORMAT: Respond ONLY with valid JSON. No markdown, no explanations, no code blocks.
2. BULLET LIMIT: Maximum 4 bullets per slide. Each bullet must be concise (under 100 characters when possible).
3. NO FABRICATED NUMBERS: Do not invent financial metrics, percentages, or statistics. If a number is needed and not provided, write "(source needed)" and set the appropriate flag.
4. PROFESSIONAL TONE: Write for a sophisticated investment committee audience.
5. ACTIONABLE CONTENT: Every bullet should convey a meaningful insight, not filler.
6. SPEAKER NOTES: Provide presenter talking points that expand on bullets without reading them verbatim.

{INVESTMENT_DECK_DESIGN_PROMPT}

STYLE GUIDELINES:
- Use active voice and strong verbs
- Lead with the most important point
- Avoid jargon unless industry-standard
- Be specific rather than generic
- Include "why it matters" context where appropriate"""


# ---------------------------------------------------------------------------
# Data Trust Mode instructions
# ---------------------------------------------------------------------------

_DATA_TRUST_INSTRUCTIONS = {
    "user_only": (
        "## DATA TRUST MODE: USER-ONLY NUMBERS\n"
        "You MUST NOT introduce any financial numbers, percentages, metrics, or "
        "statistics that are not explicitly provided in the user data below. "
        "If data is missing, describe the topic qualitatively. Never guess or "
        "estimate numerical values. Only reformat and reference user-provided figures."
    ),
    "user_auto_fetch": (
        "## DATA TRUST MODE: USER + AUTO-FETCH\n"
        "You may use numbers from the provided data sources (comparables table, "
        "DCF valuation, user-pasted data blocks). Flag any number not traceable "
        "to these sources with (source needed) and set source_needed=true."
    ),
    "narrative_only": (
        "## DATA TRUST MODE: NARRATIVE-ONLY\n"
        "Do NOT include any financial numbers, percentages, dollar amounts, "
        "multiples, or quantitative claims. Everything must be qualitative narrative. "
        "Only identity facts are allowed (founding year, headquarters city, "
        "approximate employee count band). Describe trends directionally "
        "(e.g., 'revenue has grown meaningfully') without citing figures."
    ),
}


def get_data_trust_instructions(mode: str) -> str:
    """Return prompt instructions for the given data trust mode.

    Falls back to user_auto_fetch if mode is unrecognised.
    """
    return _DATA_TRUST_INSTRUCTIONS.get(mode, _DATA_TRUST_INSTRUCTIONS["user_auto_fetch"])


def get_position_framing(position: str | None) -> str:
    """Return a short prompt fragment describing the investment position."""
    if position == "short":
        return (
            "## POSITION: SHORT\n"
            "Frame the analysis for a SHORT thesis. Emphasise headwinds, "
            "downside catalysts, overvaluation signals, and risk factors. "
            "Strengths should be acknowledged but weighed against the short case."
        )
    if position == "long":
        return (
            "## POSITION: LONG\n"
            "Frame the analysis for a LONG thesis. Emphasise growth drivers, "
            "upside catalysts, undervaluation signals, and competitive advantages. "
            "Risks should be acknowledged but contextualised within the bull case."
        )
    return ""


def get_fix_prompt(
    original_output: str,
    errors: list[str],
    schema: dict,
) -> str:
    """
    Generate a prompt to fix invalid LLM output.

    Args:
        original_output: The invalid output
        errors: List of validation errors
        schema: Expected JSON schema

    Returns:
        Fix prompt string
    """
    import json as _json

    error_list = "\n".join(f"- {e}" for e in errors)

    # Build a compact structural hint from the schema so the model knows
    # which fields must be objects/arrays vs. strings.
    schema_hint = _build_schema_hint(schema)

    return f"""Your previous response had validation errors. Please fix and respond with valid JSON only.

ERRORS FOUND:
{error_list}

EXPECTED JSON STRUCTURE:
{schema_hint}

CRITICAL: Fields that the schema defines as "object" or "array" MUST be
returned as JSON objects/arrays — NEVER as plain strings or bullet-point text.
Each nested object must include ALL of its required sub-fields.

REQUIREMENTS:
1. Fix all listed errors — pay special attention to type mismatches
2. Respond with ONLY the JSON object
3. No markdown code blocks, no explanations, no extra text
4. Maximum 4 bullets per slide
5. All required fields must be present

YOUR PREVIOUS OUTPUT (truncated):
{original_output[:1500]}

Please provide the corrected JSON response now:"""


def _build_schema_hint(schema: dict, max_depth: int = 3) -> str:
    """Return a compact textual summary of the JSON schema structure."""
    import json as _json

    defs = schema.get("$defs", {})

    def _resolve(node: dict) -> dict:
        ref = node.get("$ref", "")
        if ref.startswith("#/$defs/"):
            name = ref.split("/")[-1]
            return defs.get(name, node)
        # Collapse anyOf/oneOf with a single non-null branch
        for key in ("anyOf", "oneOf"):
            choices = node.get(key)
            if isinstance(choices, list):
                non_null = [c for c in choices if isinstance(c, dict) and c.get("type") != "null"]
                if len(non_null) == 1:
                    return _resolve(non_null[0])
        return node

    def _summarize(node: dict, depth: int = 0) -> str:
        node = _resolve(node)
        ntype = node.get("type", "object")
        if isinstance(ntype, list):
            ntype = next((t for t in ntype if t != "null"), "string")

        if ntype == "object" and depth < max_depth:
            props = node.get("properties", {})
            if not props:
                return "{...}"
            lines = []
            for key, prop in props.items():
                lines.append(f"{'  ' * (depth + 1)}\"{key}\": {_summarize(prop, depth + 1)}")
            inner = ",\n".join(lines)
            return "{\n" + inner + "\n" + "  " * depth + "}"
        if ntype == "array":
            items = node.get("items", {})
            return f"[{_summarize(items, depth + 1)}, ...]"
        if "enum" in node:
            return " | ".join(f'"{v}"' for v in node["enum"])
        return f"<{ntype}>"

    try:
        return _summarize(schema)
    except Exception:
        # Fallback: dump a truncated version of the raw schema
        return _json.dumps(schema, indent=2)[:2000]
