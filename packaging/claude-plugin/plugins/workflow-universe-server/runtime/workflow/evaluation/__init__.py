"""Evaluation subsystem -- structural analysis + editorial reading.

Structural: Deterministic checks (no LLM cost).
Editorial: Natural-language feedback from a different model family.
"""

from workflow.evaluation.editorial import (
    EditorialConcern,
    EditorialNotes,
    read_editorial,
)
from workflow.evaluation.process import (
    ProcessCheck,
    ProcessEvaluation,
    evaluate_scene_process,
)
from workflow.evaluation.structural import (
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
