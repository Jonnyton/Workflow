"""Learning system -- style rules, craft cards, criteria discovery.

Implements the observation -> promotion cycle, calibration, and
creation-time learning.
"""

from fantasy_author.learning.craft_cards import CraftCard, generate_craft_cards
from fantasy_author.learning.criteria_discovery import (
    DiscoveredCriterion,
    discover_criteria,
)
from fantasy_author.learning.style_rules import (
    LearningOutput,
    LearningSystem,
    StyleRule,
    StyleRuleState,
)

__all__ = [
    "CraftCard",
    "DiscoveredCriterion",
    "LearningOutput",
    "LearningSystem",
    "StyleRule",
    "StyleRuleState",
    "discover_criteria",
    "generate_craft_cards",
]
