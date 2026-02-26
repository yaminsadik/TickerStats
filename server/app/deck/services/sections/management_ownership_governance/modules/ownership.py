"""
Ownership module — major holders, insider ownership, activist presence.

HARD RULE: ONLY holders + stakes + activist status. No management details,
no governance flags.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute ownership context from orchestrator inputs."""
    raw_own = inputs.get("ownership") or {}
    if not isinstance(raw_own, dict):
        raw_own = {}

    holders = raw_own.get("top_holders") or raw_own.get("holders") or []
    insider_summary = raw_own.get("insider_ownership_summary")
    activist = raw_own.get("activist_presence")

    has_holders = bool(holders)
    if has_holders:
        confidence = "high"
    elif insider_summary:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "company_name": (
            (inputs.get("company") or {}).get("name")
            or inputs.get("company_name", "Unknown")
        ),
        "holders": holders,
        "insider_ownership_summary": insider_summary,
        "activist_presence": activist,
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the ownership module."""
    parts = ["## MODULE: ownership"]

    if ctx["holders"]:
        holder_lines = []
        for h in ctx["holders"]:
            if isinstance(h, dict):
                name = h.get("name", "Unknown")
                htype = h.get("holder_type") or h.get("type", "other")
                stake = h.get("stake", "")
                comment = h.get("comment", "")
                line = f"  - {name} ({htype})"
                if stake:
                    line += f": {stake}"
                if comment:
                    line += f" — {comment}"
                holder_lines.append(line)
        parts.append("Known holders:\n" + "\n".join(holder_lines))
    else:
        parts.append("No holder data provided.")

    if ctx["insider_ownership_summary"]:
        parts.append(f"Insider ownership: {ctx['insider_ownership_summary']}")

    if ctx["activist_presence"]:
        parts.append(f"Activist presence: {ctx['activist_presence']}")

    conf = ctx["confidence"]
    parts.append(f"""
INSTRUCTIONS:
- top_holders: list 0–10 holders. Use ONLY names from provided data. Do NOT invent holder names.
- insider_ownership_summary: include ONLY if insider ownership data is provided. Otherwise null.
- activist_presence: include ONLY if activist activity data is provided. Otherwise null. Do NOT speculate.
- takeaways: 1–3 bullets summarizing ownership implications for investors.
- Set confidence to at most "{conf}".

HARD RULES:
- ONLY ownership data: holders, stakes, activist status.
- Do NOT fabricate holder names, percentages, or dollar amounts.
- Do NOT include executive details — that belongs in management module.
- Do NOT include governance flags — that belongs in governance module.
""")

    return "\n".join(parts)
