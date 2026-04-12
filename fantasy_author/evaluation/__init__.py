"""Evaluation subsystem -- structural analysis + editorial reading.

Structural: Deterministic checks (no LLM cost).
Editorial: Natural-language feedback from a different model family.
"""

from fantasy_author.evaluation.editorial import (
    EditorialConcern,
    EditorialNotes,
    read_editorial,
)
from fantasy_author.evaluation.process import (
    ProcessCheck,
    ProcessEvaluation,
    evaluate_scene_process,
)
from fantasy_author.evaluation.structural import (
    CheckResult,
    StructuralEvaluator,
    StructuralResult,
)

__all__ = [
    "CheckResult",
    "EditorialConcern",
    "EditorialNotes",
    "ProcessCheck",
    "ProcessEvaluation",
    "StructuralEvaluator",
    "StructuralResult",
    "evaluate_scene_process",
    "read_editorial",
]
