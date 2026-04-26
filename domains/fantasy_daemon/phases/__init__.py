"""Fantasy-daemon phase nodes -- graph cycle map.

Each phase is a graph node invoked by one of four LangGraph cycles
defined in ``domains/fantasy_daemon/graphs/``:

scene cycle (``graphs/scene.py``, entry: ``orient``)
    orient -> plan -> draft -> commit -> (accept | second_draft -> draft)

chapter cycle (``graphs/chapter.py``, entry: ``run_scene``)
    run_scene -> (next_scene | done) -> consolidate -> learn

book cycle (``graphs/book.py``, entry: ``run_chapter``)
    run_chapter -> (next_chapter | diagnose | book_close)
    diagnose -> (next_chapter | book_close)

universe cycle (``graphs/universe.py``, entry: ``foundation_priority_review``)
    foundation_priority_review -> (authorial_priority_review | dispatch_execution)
    dispatch_execution -> (run_book | worldbuild | reflect | idle) -> universe_cycle

Re-exports
----------
orient          -- scene cycle entry; deterministic forward-projection
plan            -- scene cycle; beat sheet generation
draft           -- scene cycle; prose generation
commit          -- scene cycle; evaluation and verdict
consolidate     -- chapter cycle; fact promotion after scenes
learn           -- chapter cycle; style rule lifecycle
diagnose        -- book cycle; stuck detection and recovery
book_close      -- book cycle; book-level consolidation (terminal)
worldbuild      -- universe cycle; world knowledge updates
reflect         -- universe cycle; cross-series coherence review
universe_cycle  -- universe cycle; end-of-cycle maintenance
select_task     -- legacy universe routing (predates dispatch_execution)
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
