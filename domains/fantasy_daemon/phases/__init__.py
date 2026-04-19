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

from domains.fantasy_daemon.phases._activity import activity_log
from domains.fantasy_daemon.phases.book_close import book_close
from domains.fantasy_daemon.phases.commit import commit
from domains.fantasy_daemon.phases.consolidate import consolidate
from domains.fantasy_daemon.phases.diagnose import diagnose
from domains.fantasy_daemon.phases.draft import draft
from domains.fantasy_daemon.phases.learn import learn
from domains.fantasy_daemon.phases.orient import orient
from domains.fantasy_daemon.phases.plan import plan
from domains.fantasy_daemon.phases.reflect import reflect
from domains.fantasy_daemon.phases.select_task import select_task
from domains.fantasy_daemon.phases.universe_cycle import universe_cycle
from domains.fantasy_daemon.phases.worldbuild import worldbuild

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
