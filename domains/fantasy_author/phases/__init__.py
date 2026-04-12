"""Mock phase implementations.

All phases accept a state dict and return a partial state dict.
Phase 1 replaced the old node implementations with real phases.

Re-exports match the original interface for backward compatibility:

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

Additional Phase 1+ implementations (not in original):

activity_log                  -- activity logging support
authorial_priority_review     -- justified authorial work routing
foundation_priority_review    -- hard-blocking upload synthesis
dispatch_execution            -- work execution dispatcher
"""

from domains.fantasy_author.phases._activity import activity_log
from domains.fantasy_author.phases.authorial_priority_review import (
    authorial_priority_review,
)
from domains.fantasy_author.phases.book_close import book_close
from domains.fantasy_author.phases.commit import commit
from domains.fantasy_author.phases.consolidate import consolidate
from domains.fantasy_author.phases.diagnose import diagnose
from domains.fantasy_author.phases.dispatch_execution import dispatch_execution
from domains.fantasy_author.phases.draft import draft
from domains.fantasy_author.phases.foundation_priority_review import (
    foundation_priority_review,
)
from domains.fantasy_author.phases.learn import learn
from domains.fantasy_author.phases.orient import orient
from domains.fantasy_author.phases.plan import plan
from domains.fantasy_author.phases.reflect import reflect
from domains.fantasy_author.phases.select_task import select_task
from domains.fantasy_author.phases.universe_cycle import universe_cycle
from domains.fantasy_author.phases.worldbuild import worldbuild

__all__ = [
    "activity_log",
    "authorial_priority_review",
    "book_close",
    "commit",
    "consolidate",
    "diagnose",
    "dispatch_execution",
    "draft",
    "foundation_priority_review",
    "learn",
    "orient",
    "plan",
    "reflect",
    "select_task",
    "universe_cycle",
    "worldbuild",
]
