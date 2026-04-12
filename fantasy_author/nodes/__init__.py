"""Mock node implementations for Phase 0.

All nodes accept a state dict and return a partial state dict.
Phase 1 will replace these with real implementations.

Re-exports
----------
orient          -- deterministic forward-projection
plan            -- beat sheet generation
draft           -- prose generation
commit          -- evaluation and verdict
consolidate     -- chapter-level fact promotion
learn           -- style rule lifecycle
select_task     -- universe task routing
worldbuild      -- world knowledge updates
reflect         -- creative direction review
universe_cycle  -- end-of-cycle maintenance
book_close      -- book-level consolidation
diagnose        -- stuck detection and recovery
"""

from fantasy_author.nodes._activity import activity_log
from fantasy_author.nodes.book_close import book_close
from fantasy_author.nodes.commit import commit
from fantasy_author.nodes.consolidate import consolidate
from fantasy_author.nodes.diagnose import diagnose
from fantasy_author.nodes.draft import draft
from fantasy_author.nodes.learn import learn
from fantasy_author.nodes.orient import orient
from fantasy_author.nodes.plan import plan
from fantasy_author.nodes.reflect import reflect
from fantasy_author.nodes.select_task import select_task
from fantasy_author.nodes.universe_cycle import universe_cycle
from fantasy_author.nodes.worldbuild import worldbuild

__all__ = [
    "activity_log",
    "book_close",
    "commit",
    "consolidate",
    "diagnose",
    "draft",
    "learn",
    "orient",
    "plan",
    "reflect",
    "select_task",
    "universe_cycle",
    "worldbuild",
]
