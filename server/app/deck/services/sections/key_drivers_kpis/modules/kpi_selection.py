"""
KPI selection module — choose and justify value linkage for 3-5 KPIs.

HARD RULE: Only select KPIs from inputs. Never invent metrics.
Only choose and justify value linkage — no definitions, no disclosure refs.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.key_drivers_kpis.fallbacks import (
    select_kpis_from_inputs,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute KPI selection context from inputs."""
    kpi_hints, confidence, notes = select_kpis_from_inputs(inputs)
    return {
        "company_name": inputs.get("company_name", "Unknown"),
        "ticker": inputs.get("ticker", ""),
        "sector": inputs.get("sector", "not specified"),
        "kpi_hints": kpi_hints,
        "selection_confidence": confidence,
        "selection_notes": notes,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for KPI selection."""
    hints = ctx.get("kpi_hints", [])
    hint_names = [h.get("name", "") for h in hints if h.get("name")]

    hint_block = ""
    if hint_names:
        hint_block = (
            "\nThe following KPIs are available from inputs — select 3-5 from these:\n"
            + "\n".join(f"  - {name}" for name in hint_names)
            + "\n"
        )
    else:
        hint_block = (
            "\nNo explicit KPIs were found in inputs. "
            "You may identify operational drivers from the provided data, "
            "but do NOT invent metrics that are not grounded in the inputs.\n"
        )

    return f"""## MODULE: kpi_selection
Company: {ctx["company_name"]} ({ctx["ticker"]})
Sector: {ctx["sector"]}
{hint_block}
INSTRUCTIONS:
- Select 3 to 5 value-driving KPIs from the inputs.
- For each KPI, provide the "name" and "why_it_moves_value" fields.
- "why_it_moves_value" must be exactly 1 sentence: causal and specific to this business.
- Prefer operational drivers over accounting outcomes (e.g., ARPU, churn, utilization, same-store sales, backlog, NRR, units shipped, take-rate, AUM, NIM, LTV/CAC).
- Avoid "revenue" unless explicitly the primary driver for a purely volume-driven business.
- If fewer than 3 KPIs exist in inputs, use what is available (1-2) and note the limitation.

HARD RULES:
- Do NOT invent KPIs that are not grounded in the provided inputs.
- Do NOT provide definitions or units here — those come from the kpi_definitions module.
- Do NOT provide disclosure references here — those come from the disclosure_locations module.
"""
