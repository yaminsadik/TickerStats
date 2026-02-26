"""
Break Thesis module — compress flip conditions into a single line.

Only produces output if the user provided flip_conditions.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Extract flip conditions from user inputs."""
    flip_conditions: list[str] = []

    # Direct flip_conditions field
    raw_flip = inputs.get("flip_conditions") or []
    if isinstance(raw_flip, list):
        for c in raw_flip:
            s = str(c).strip()
            if s:
                flip_conditions.append(s)

    # Also check thesis.what_changes_mind
    thesis = inputs.get("thesis")
    if thesis:
        wcm = None
        if isinstance(thesis, dict):
            wcm = thesis.get("what_changes_mind") or []
        elif hasattr(thesis, "what_changes_mind"):
            wcm = thesis.what_changes_mind or []
        if wcm:
            for c in wcm:
                s = str(c).strip()
                if s and s not in flip_conditions:
                    flip_conditions.append(s)

    return {
        "flip_conditions": flip_conditions,
        "has_flip": len(flip_conditions) > 0,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for break-thesis line."""
    if not ctx["has_flip"]:
        return """## MODULE: break_thesis
No flip conditions provided by user.
Set break_thesis_line to null.
"""

    conditions = ctx["flip_conditions"]
    cond_block = "\n".join(f"  - {c}" for c in conditions)

    return f"""## MODULE: break_thesis
User-provided flip conditions / "what breaks the thesis":
{cond_block}

INSTRUCTIONS:
- Compress these conditions into ONE concise sentence for break_thesis_line.
- Use neutral, institutional phrasing.
- The output must be a direct restatement — do NOT introduce new conditions.
- If there is only one condition, restate it concisely.

HARD RULES:
- Only use conditions listed above. Do NOT invent new break conditions.
- Keep it to one sentence, max ~30 words.
"""
