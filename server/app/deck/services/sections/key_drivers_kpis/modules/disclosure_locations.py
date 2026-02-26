"""
Disclosure locations module — where each KPI appears in filings/materials.

HARD RULE: Only disclosure references. Never guess page numbers or sections.
If filing location is unknown, set source_type = "not_provided".
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute disclosure context from available filing references."""
    # Collect any disclosure / filing data from inputs
    disclosures = inputs.get("disclosures") or inputs.get("filing_refs") or {}
    filings = inputs.get("filings") or {}
    return {
        "company_name": inputs.get("company_name", "Unknown"),
        "disclosures": disclosures,
        "filings": filings,
        "has_filing_data": bool(disclosures or filings),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for disclosure locations."""
    filing_block = ""
    if ctx["has_filing_data"]:
        filing_block = (
            "\nFiling data is available in the inputs. "
            "Match each KPI to its disclosure source if possible.\n"
        )
    else:
        filing_block = (
            "\nNo filing references are available in the inputs. "
            "Set source_type to \"not_provided\" for all KPIs.\n"
        )

    return f"""## MODULE: disclosure_locations
Company: {ctx["company_name"]}
{filing_block}
INSTRUCTIONS:
- For each KPI, populate the "disclosure" object:
  - "source_type": one of "10-K", "10-Q", "earnings_release", "earnings_deck", "investor_presentation", "other", "not_provided"
  - "description": e.g. "MD&A, Business Overview" or "Quarterly press release". null if not known.
  - "page_or_section": only if explicitly provided in the inputs. null otherwise.
  - "link_label": null unless your system supports linking.

HARD RULES:
- NEVER guess page numbers, section headings, or filing locations.
- If no filing data exists for a KPI, set source_type to "not_provided" and all other fields to null.
- Do NOT add extra KPIs or modify any fields beyond the "disclosure" object.
"""
