"""
Governance module — governance structure and flags.

HARD RULE: ONLY governance structure/flags. No management details,
no ownership stakes.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute governance context from orchestrator inputs."""
    raw_gov = inputs.get("governance") or {}
    if not isinstance(raw_gov, dict):
        raw_gov = {}

    flags = raw_gov.get("flags") or []
    board_info = raw_gov.get("board") or raw_gov.get("board_info")

    has_flags = bool(flags)
    if has_flags:
        confidence = "high"
    elif board_info:
        confidence = "medium"
    else:
        confidence = "medium"  # Not low — governance may simply not be disclosed

    return {
        "company_name": (
            (inputs.get("company") or {}).get("name")
            or inputs.get("company_name", "Unknown")
        ),
        "flags": flags,
        "board_info": board_info,
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the governance module."""
    parts = ["## MODULE: governance"]

    if ctx["flags"]:
        flag_lines = []
        for f in ctx["flags"]:
            if isinstance(f, dict):
                ftype = f.get("flag_type") or f.get("type", "other")
                fact = f.get("fact", "")
                severity = f.get("severity", "")
                line = f"  - {ftype}: {fact}"
                if severity:
                    line += f" (severity: {severity})"
                flag_lines.append(line)
        parts.append("Known governance flags:\n" + "\n".join(flag_lines))
    else:
        parts.append("No governance flags provided.")

    if ctx["board_info"]:
        parts.append(f"Board information: {ctx['board_info']}")

    conf = ctx["confidence"]
    parts.append(f"""
INSTRUCTIONS:
- flags: list 0–8 governance flags. Use ONLY facts from provided data.
- Each flag requires: flag_type, severity, fact (factual statement), why_it_matters (neutral 1-liner).
- Severity mapping:
  - dual_class or insider_control -> severity at least "medium"
  - auditor_change or related_party -> severity "medium" or "high" depending on context
  - other flags -> "low" unless explicitly stated as major issue
- takeaways: 1–3 bullets summarizing governance implications.
- Set confidence to at most "{conf}".
- If no flags are available, set flags=[], confidence="medium", notes="governance flags not provided in inputs".

HARD RULES:
- ONLY governance structure and flags.
- State flags neutrally: fact + why it matters. No accusations, no "fraud" language.
- Do NOT fabricate governance facts, board members, or flag severity.
- Do NOT include management track record — that belongs in management module.
- Do NOT include ownership stakes — that belongs in ownership module.
""")

    return "\n".join(parts)
