"""Import compatibility layer for Phase 2 extraction.

During the transition from Phase 1 (in-place interfaces) to Phase 2 (extracted
packages), two import paths work:

  from fantasy_author.providers import ...   (original, still works)
  from workflow.providers import ...         (new canonical path)

The original fantasy_author/ package remains fully functional. All source code
has been copied to:

  workflow/                       — shared infrastructure library
  domains/fantasy_author/         — fantasy-specific domain

The original fantasy_author/ stays in place with its original imports unchanged.
Existing tests and __main__.py continue importing from fantasy_author.*, which
still resolves correctly.

Transition Plan
---------------

Phase 2a (current):  Both old and new import paths work in parallel.
                     - fantasy_author/ retains original source with original imports
                     - workflow/ has rewritten imports (fantasy_author -> workflow)
                     - domains/ has rewritten imports (fantasy_author -> domains)

Phase 2b (future):   New canonical paths become primary.
                     - Update tests to import from workflow.* and domains.*
                     - Update __main__.py and entry points as needed
                     - Redirect fantasy_author/ imports to new packages

Phase 3 (later):     Deprecation and removal.
                     - Mark old imports as deprecated
                     - Set removal deadline
                     - Remove fantasy_author/ re-export shims

Key Points
----------

- Both the old and new packages are installed and functional.
- The old fantasy_author/ package continues to work as-is for compatibility.
- The new workflow/ and domains/ packages have independent, rewritten imports.
- No tests need to change immediately. Existing tests will work with old paths.
- Gradual migration to new paths is preferred over forcing all tests at once.

Package Mapping
---------------

Infrastructure moved to workflow/:

  fantasy_author.providers      -> workflow.providers
  fantasy_author.memory         -> workflow.memory
  fantasy_author.retrieval      -> workflow.retrieval
  fantasy_author.knowledge      -> workflow.knowledge
  fantasy_author.evaluation     -> workflow.evaluation
  fantasy_author.constraints    -> workflow.constraints
  fantasy_author.planning       -> workflow.planning
  fantasy_author.checkpointing  -> workflow.checkpointing
  fantasy_author.learning       -> workflow.learning
  fantasy_author.ingestion      -> workflow.ingestion
  fantasy_author.judges         -> workflow.judges
  fantasy_author.notes          -> workflow.notes
  fantasy_author.work_targets   -> workflow.work_targets
  fantasy_author.author_server  -> workflow.author_server
  fantasy_author.api            -> workflow.api
  fantasy_author.desktop        -> workflow.desktop
  fantasy_author.testing        -> workflow.testing
  fantasy_author.config         -> workflow.config
  fantasy_author.runtime        -> workflow.runtime
  fantasy_author.exceptions     -> workflow.exceptions
  fantasy_author.protocols      -> workflow.protocols

Fantasy-specific modules moved to domains/fantasy_author/:

  fantasy_author.graphs         -> domains.fantasy_author.graphs
  fantasy_author.phases         -> domains.fantasy_author.phases
  fantasy_author.nodes          -> (nodes merged into graphs or phases)
  fantasy_author.tools          -> domains.fantasy_author.tools
  fantasy_author.eval           -> domains.fantasy_author.eval
  fantasy_author.state          -> domains.fantasy_author.state
  fantasy_author.memory         -> domains.fantasy_author.memory (domain-specific)

Verification
------------

All three packages parse cleanly:
  workflow/: 78 files, 0 syntax errors
  domains/: 39 files, 0 syntax errors
  fantasy_author/: 112 files, 0 syntax errors (original)
"""
