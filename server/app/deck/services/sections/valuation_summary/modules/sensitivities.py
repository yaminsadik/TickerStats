"""Build sensitivities list for the Valuation Summary section."""

from __future__ import annotations

from app.deck.services.sections.valuation_summary.fallbacks import default_sensitivities
from app.deck.services.sections.valuation_summary.schemas import MethodSummary


_LABEL_TO_KEY: dict[str, str] = {
    "dcf": "dcf",
    "relative": "relative",
    "sum-of-the-parts": "sotp",
    "nav": "nav",
    "unit economics": "unit_econ",
    "yield-based": "yield",
}


def build_sensitivities(
    methods: list[MethodSummary],
    trust_mode: str,
) -> list[str]:
    """Build 2-3 qualitative sensitivity strings."""
    keys: list[str] = []
    for m in methods:
        k = _LABEL_TO_KEY.get(m.method.lower(), m.method.lower())
        keys.append(k)

    return default_sensitivities(keys, trust_mode)
