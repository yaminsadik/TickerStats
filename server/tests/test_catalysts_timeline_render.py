"""Tests for catalyst timeline slide rendering (timing expansion)."""

from app.deck.services.sections.catalysts_timeline import render as catalyst_render


def test_expand_comma_separated_timings_into_separate_bullets():
    out = {
        "catalysts": [
            {
                "name": "Megafactory ramp",
                "timing": "H1 2025, H2 2025, 2026",
                "mechanism": "Utilization",
            },
        ],
        "confidence": "medium",
    }
    slides = catalyst_render.render_to_slides(out)
    assert len(slides) == 1
    texts = [b["text"] for b in slides[0]["bullets"]]
    assert len(texts) == 3
    assert "[H1 2025]" in texts[0]
    assert "[H2 2025]" in texts[1]
    assert "[2026]" in texts[2]
    assert all("Megafactory ramp" in t for t in texts)
