"""
Revenue Quality & GTM module.

Focus: revenue model quality + go-to-market engine.
Include KPIs only if values are provided.
Failure modes only if supported by inputs (e.g., churn rising, channel dependence).
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Extract revenue quality and GTM fields from inputs."""
    company = inputs.get("company") or {}
    rq = inputs.get("revenue_quality") or {}
    gtm = inputs.get("gtm") or {}

    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        # Revenue quality fields
        "recurring_pct": rq.get("recurring_pct"),
        "arr": rq.get("arr"),
        "nrr": rq.get("nrr"),
        "grr": rq.get("grr"),
        "churn": rq.get("churn"),
        "contract_length": rq.get("contract_length"),
        "rpo": rq.get("rpo"),
        "backlog": rq.get("backlog"),
        "usage_mix": rq.get("usage_mix"),
        "ads_mix": rq.get("ads_mix"),
        "take_rate": rq.get("take_rate"),
        # GTM fields
        "customer_segments": gtm.get("customer_segments"),
        "acv": gtm.get("acv"),
        "sales_cycle": gtm.get("sales_cycle"),
        "channel_mix": gtm.get("channel_mix"),
        "cac_payback": gtm.get("cac_payback"),
        "magic_number": gtm.get("magic_number"),
        "sm_efficiency_proxy": gtm.get("sm_efficiency_proxy"),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the revenue_quality_gtm module."""
    # Build a data summary of what's available
    data_lines: list[str] = []

    # Revenue quality
    for key in ("recurring_pct", "arr", "nrr", "grr", "churn",
                "contract_length", "rpo", "backlog", "usage_mix",
                "ads_mix", "take_rate"):
        val = ctx.get(key)
        if val is not None and val != "" and val != []:
            data_lines.append(f"  {key}: {val}")

    # GTM
    for key in ("customer_segments", "acv", "sales_cycle", "channel_mix",
                "cac_payback", "magic_number", "sm_efficiency_proxy"):
        val = ctx.get(key)
        if val is not None and val != "" and val != []:
            data_lines.append(f"  {key}: {val}")

    data_block = "\n".join(data_lines) if data_lines else "  (limited data available)"

    return f"""## MODULE: revenue_quality_gtm
Company: {ctx["company_name"]}
Available data:
{data_block}

INSTRUCTIONS:
- Write 2 to 6 concise bullets about the company's revenue model quality and GTM engine.
- If a KPI value is present, include it as a KPIItem with label, value, as_of (if known), source_note (if known).
- If a KPI value is missing, do NOT reference it numerically. Set KPIItem.value to null.
- Include failure_modes ONLY if supported by the data (e.g., rising churn, channel dependence).
  Do not invent failure modes for data that is not provided.
- Set confidence: "high" if >= 3 KPI values present, "medium" if 1-2 present, "low" if mostly inferred.
- Tone: neutral, factual, institutional. No hype, no marketing language.

HARD RULES:
- Do NOT fabricate KPI values.
- Do NOT invent metrics not present in the data above.
- If an area is unknown, mention it in the module notes field, NOT in bullets.
"""
