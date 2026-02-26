"""
Platform Dependencies & Risk module.

Focus: platform concentration/dependencies + switching/lock-in mechanics.
Failure modes: policy change, partner repricing, integration break risk
(only if referenced in inputs).
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Extract platform dependency fields from inputs."""
    company = inputs.get("company") or {}
    pd = inputs.get("platform_deps") or {}

    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "top_partners": pd.get("top_partners"),
        "cloud_provider_concentration": pd.get("cloud_provider_concentration"),
        "app_store_dependence": pd.get("app_store_dependence"),
        "key_integrations": pd.get("key_integrations"),
        "data_suppliers": pd.get("data_suppliers"),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the platform_dependencies_risk module."""
    data_lines: list[str] = []

    for key in ("top_partners", "cloud_provider_concentration",
                "app_store_dependence", "key_integrations", "data_suppliers"):
        val = ctx.get(key)
        if val is not None and val != "" and val != []:
            if isinstance(val, list):
                data_lines.append(f"  {key}: {', '.join(str(v) for v in val)}")
            else:
                data_lines.append(f"  {key}: {val}")

    data_block = "\n".join(data_lines) if data_lines else "  (limited data available)"

    return f"""## MODULE: platform_dependencies_risk
Company: {ctx["company_name"]}
Available data:
{data_block}

INSTRUCTIONS:
- Write 2 to 6 concise bullets about platform concentration, dependencies, and lock-in mechanics.
- Include KPIs only if values are provided in the data above.
- Include failure_modes ONLY for risks referenced in the inputs:
  - Policy change risk (if app_store_dependence or top_partners present)
  - Partner repricing risk (if top_partners or cloud_provider_concentration present)
  - Integration break risk (if key_integrations present)
  Do not invent failure modes for data that is not provided.
- Set confidence: "high" if >= 2 fields present, "medium" if 1 present, "low" if inferred.
- Tone: neutral, factual, institutional. No hype.

HARD RULES:
- Do NOT fabricate partner names, dependencies, or risk scenarios.
- Do NOT invent metrics not present in the data above.
- If an area is unknown, mention it in the module notes field, NOT in bullets.
"""
