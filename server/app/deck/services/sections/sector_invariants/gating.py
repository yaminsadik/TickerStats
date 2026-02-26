"""
Deterministic gating logic for the Sector Invariants section.

All functions are pure — no LLM calls. They decide which modules to include
based on sector classification and data availability.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.deck.services.sections.sector_invariants.schemas import ModuleId, Sector


# ── Sector-to-module registry ───────────────────────────────────────────────
# Design for extension: add INDUSTRIALS_MODULES, HEALTHCARE_MODULES, etc.

TECH_MODULES: list[ModuleId] = [
    "revenue_quality_gtm",
    "platform_dependencies_risk",
    "security_reliability",
]

_SECTOR_MODULE_MAP: dict[Sector, list[ModuleId]] = {
    "tech_software": TECH_MODULES,
    # "industrials": INDUSTRIALS_MODULES,  # future
}

_MAX_MODULES = 2

# ── Keyword sets for sector classification ───────────────────────────────────

_TECH_SOFTWARE_KEYWORDS = re.compile(
    r"(?i)\b(software|saas|internet|cloud|platform|tech|technology|"
    r"information technology|digital|cybersecurity|fintech|edtech|"
    r"ai|artificial intelligence|machine learning|data analytics)\b"
)


# ── Public API ───────────────────────────────────────────────────────────────

def classify_sector(company: dict[str, Any] | None) -> Sector:
    """
    Classify a company into a supported sector bucket.

    Examines sector, industry, and subindustry fields for tech/software
    keywords.  Falls back to ``"other"`` if none match.
    """
    if not company:
        return "other"

    fields_to_check = [
        str(company.get("sector", "") or ""),
        str(company.get("industry", "") or ""),
        str(company.get("subindustry", "") or ""),
    ]
    combined = " ".join(fields_to_check)

    if _TECH_SOFTWARE_KEYWORDS.search(combined):
        return "tech_software"

    return "other"


def module_is_supported(module_id: ModuleId, sector_class: Sector) -> bool:
    """Return True if *module_id* is supported for *sector_class*."""
    supported = _SECTOR_MODULE_MAP.get(sector_class, [])
    return module_id in supported


def module_has_minimum_data(module_id: ModuleId, inputs: dict[str, Any]) -> bool:
    """
    Deterministic check: does *inputs* contain enough data for *module_id*?

    Thresholds are hard-coded — no LLM involvement.
    """
    if module_id == "revenue_quality_gtm":
        return _has_revenue_quality_gtm_data(inputs)
    elif module_id == "platform_dependencies_risk":
        return _has_platform_deps_data(inputs)
    elif module_id == "security_reliability":
        return _has_security_data(inputs)
    return False


def choose_included_modules(inputs: dict[str, Any]) -> list[ModuleId]:
    """
    Select which modules to include, in priority order.

    1. Classify sector
    2. For each module in priority order, check support + minimum data
    3. Cap at ``_MAX_MODULES``

    Returns an ordered list of ModuleIds to include (may be empty).
    """
    company = inputs.get("company") or {}
    sector_class = classify_sector(company)

    candidates = _SECTOR_MODULE_MAP.get(sector_class, [])
    included: list[ModuleId] = []
    for mod_id in candidates:
        if len(included) >= _MAX_MODULES:
            break
        if module_has_minimum_data(mod_id, inputs):
            included.append(mod_id)
    return included


# ── Private helpers ──────────────────────────────────────────────────────────

def _has_revenue_quality_gtm_data(inputs: dict[str, Any]) -> bool:
    """Require at least 2 of 5 signal groups."""
    rq = inputs.get("revenue_quality") or {}
    gtm = inputs.get("gtm") or {}

    groups_present = 0

    # Group 1: arr or recurring_pct
    if _any_present(rq, "arr", "recurring_pct"):
        groups_present += 1

    # Group 2: nrr or grr or churn
    if _any_present(rq, "nrr", "grr", "churn"):
        groups_present += 1

    # Group 3: rpo / backlog
    if _any_present(rq, "rpo", "backlog"):
        groups_present += 1

    # Group 4: cac_payback or magic_number or sm_efficiency_proxy
    if _any_present(gtm, "cac_payback", "magic_number", "sm_efficiency_proxy"):
        groups_present += 1

    # Group 5: customer_segments or acv
    if _any_present(gtm, "customer_segments", "acv"):
        groups_present += 1

    return groups_present >= 2


def _has_platform_deps_data(inputs: dict[str, Any]) -> bool:
    """Require at least 1 of the dependency fields."""
    pd = inputs.get("platform_deps") or {}
    return _any_present(
        pd,
        "cloud_provider_concentration",
        "app_store_dependence",
        "top_partners",
        "key_integrations",
        "data_suppliers",
    )


def _has_security_data(inputs: dict[str, Any]) -> bool:
    """Require at least 1 of the security/reliability fields."""
    sec = inputs.get("security") or {}
    return _any_present(sec, "soc2_iso", "breach_history", "uptime_sla", "compliance_notes")


def _any_present(d: dict[str, Any], *keys: str) -> bool:
    """Return True if at least one key is present and non-empty/non-None."""
    for k in keys:
        v = d.get(k)
        if v is not None and v != "" and v != []:
            return True
    return False
