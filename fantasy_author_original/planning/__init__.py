"""Planning layer -- HTN decomposition and DOME outline expansion.

Exports:
- HTNPlanner.decompose() -- hierarchical task decomposition
- DOMEExpander.expand() -- recursive outline deepening with KG feedback
"""

from fantasy_author.planning.dome_expansion import DOMEExpander
from fantasy_author.planning.htn_planner import HTNPlanner

__all__ = [
    "DOMEExpander",
    "HTNPlanner",
]
