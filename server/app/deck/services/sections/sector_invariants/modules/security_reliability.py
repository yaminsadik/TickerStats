"""
Security & Reliability module.

Focus: security posture, certifications, uptime/SLA, breaches.
Failure modes: breach, downtime, compliance gaps (only if referenced in inputs).
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Extract security and reliability fields from inputs."""
    company = inputs.get("company") or {}
    sec = inputs.get("security") or {}

    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "soc2_iso": sec.get("soc2_iso"),
        "breach_history": sec.get("breach_history"),
        "uptime_sla": sec.get("uptime_sla"),
        "compliance_notes": sec.get("compliance_notes"),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the security_reliability module."""
    data_lines: list[str] = []

    for key in ("soc2_iso", "breach_history", "uptime_sla", "compliance_notes"):
        val = ctx.get(key)
        if val is not None and val != "" and val != []:
            data_lines.append(f"  {key}: {val}")

    data_block = "\n".join(data_lines) if data_lines else "  (limited data available)"

    return f"""## MODULE: security_reliability
Company: {ctx["company_name"]}
Available data:
{data_block}

INSTRUCTIONS:
- Write 2 to 6 concise bullets about the company's security posture, certifications, and reliability.
- Include KPIs only if values are provided in the data above.
- Include failure_modes ONLY for risks referenced in the inputs:
  - Breach risk (if breach_history present)
  - Downtime risk (if uptime_sla present)
  - Compliance gap risk (if compliance_notes or soc2_iso present)
  Do not invent failure modes for data that is not provided.
- Set confidence: "high" if >= 2 fields present, "medium" if 1 present, "low" if inferred.
- Tone: neutral, factual, institutional. No hype.

HARD RULES:
- Do NOT fabricate security posture, certifications, or breach history.
- Do NOT invent metrics not present in the data above.
- If an area is unknown, mention it in the module notes field, NOT in bullets.
"""
