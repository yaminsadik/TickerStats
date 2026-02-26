"""
Base types for modular deck section definitions.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


BuildPromptFn = Callable[[dict[str, Any]], str]
PostprocessFn = Callable[[Any, dict[str, Any]], Any]


@dataclass(frozen=True)
class SectionSpec:
    """
    Declarative definition for a deck section.
    """

    id: str
    build_prompt: BuildPromptFn
    schema: dict[str, Any]
    required_context: set[str] = field(default_factory=set)
    postprocess: Optional[PostprocessFn] = None
