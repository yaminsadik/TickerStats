"""
Management module — executives, track record, incentives, alignment.

HARD RULE: ONLY people + incentives + alignment. No ownership stakes
(unless equity_ownership of a named executive), no governance flags.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute management context from orchestrator inputs."""
    raw_mgmt = inputs.get("management") or {}
    if not isinstance(raw_mgmt, dict):
        raw_mgmt = {}

    executives = raw_mgmt.get("executives") or []
    incentives = raw_mgmt.get("incentives") or raw_mgmt.get("compensation") or []
    track_record = raw_mgmt.get("track_record") or []

    has_exec = bool(executives)
    has_incentives = bool(incentives)

    if has_exec and has_incentives:
        confidence = "high"
    elif has_exec or has_incentives:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "company_name": (
            (inputs.get("company") or {}).get("name")
            or inputs.get("company_name", "Unknown")
        ),
        "executives": executives,
        "incentives": incentives,
        "track_record": track_record,
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the management module."""
    parts = ["## MODULE: management"]

    # Executives
    if ctx["executives"]:
        exec_lines = []
        for ex in ctx["executives"]:
            if isinstance(ex, dict):
                name = ex.get("name", "N/A")
                role = ex.get("role", "")
                since = ex.get("since", "")
                equity = ex.get("equity_ownership", "")
                line = f"  - {name}"
                if role:
                    line += f", {role}"
                if since:
                    line += f" (since {since})"
                if equity:
                    line += f" — equity: {equity}"
                exec_lines.append(line)
        parts.append("Known executives:\n" + "\n".join(exec_lines))
    else:
        parts.append("No executive data provided.")

    # Track record
    if ctx["track_record"]:
        tr_lines = [f"  - {t}" for t in ctx["track_record"]]
        parts.append("Known track record facts:\n" + "\n".join(tr_lines))

    # Incentives
    if ctx["incentives"]:
        inc_lines = []
        for inc in ctx["incentives"]:
            if isinstance(inc, dict):
                comp = inc.get("component", "Unknown")
                metric = inc.get("metric_link", "")
                weight = inc.get("weight", "")
                line = f"  - {comp}"
                if metric:
                    line += f" (linked to: {metric})"
                if weight:
                    line += f" [{weight}]"
                inc_lines.append(line)
        parts.append("Known incentive structure:\n" + "\n".join(inc_lines))
    else:
        parts.append("No incentive/compensation data provided.")

    conf = ctx["confidence"]
    parts.append(f"""
INSTRUCTIONS:
- executives: list 0–6 executives. Use ONLY provided names. Do NOT invent names.
- track_record: 2–5 factual bullets about management performance based ONLY on provided facts
  (tenure, prior roles, delivered metrics). No hype language.
- incentives: 0–5 components. Use ONLY if compensation data is provided. If not, leave empty
  and set notes to "incentive structure not provided".
- alignment_summary: 2–4 bullets summarizing management-shareholder alignment.
  If data is limited, explicitly state the limitation.
- Set confidence to at most "{conf}".

HARD RULES:
- ONLY management people, track record, and incentive alignment.
- Do NOT fabricate names, comp numbers, or equity stakes.
- Do NOT include ownership data from institutional holders — that belongs in ownership module.
- Do NOT include governance flags — that belongs in governance module.
""")

    return "\n".join(parts)
