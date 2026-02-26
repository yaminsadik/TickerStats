"""
KPI definitions module — definitions and units for each selected KPI.

HARD RULE: Only definitions and units. No extra KPIs beyond those selected.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute definition context."""
    return {
        "company_name": inputs.get("company_name", "Unknown"),
        "sector": inputs.get("sector", "not specified"),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for KPI definitions."""
    return f"""## MODULE: kpi_definitions
Company: {ctx["company_name"]}
Sector: {ctx["sector"]}

INSTRUCTIONS:
- For each KPI selected in kpi_selection, provide:
  - "definition": 1-2 sentence operational definition. Be precise and specific to how this company calculates / reports the metric.
  - "unit": the measurement unit (e.g., "%", "$/user/month", "hours", "bps", "x"). Use null if not applicable.
  - "typical_direction": "up_is_good", "down_is_good", or "depends". Use null if ambiguous.

HARD RULES:
- Do NOT add extra KPIs beyond those in kpi_selection.
- Do NOT modify the "name" or "why_it_moves_value" fields.
- Do NOT provide disclosure references — those come from disclosure_locations.
- Definitions must be based on standard financial/operational conventions, not invented.
"""
