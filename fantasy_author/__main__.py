"""Back-compat CLI surface for the Author -> Daemon rename.

The real implementation lives in ``fantasy_daemon.__main__``. This shim keeps
the old entrypoint importable during the compat window and preserves the
static invariants tests look for around `.pause`, `_build_unified_graph_builder`,
and `build_universe_graph()`.
"""

from fantasy_daemon.__main__ import *  # noqa: F401,F403
