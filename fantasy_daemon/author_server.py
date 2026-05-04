"""Back-compat shim: ``fantasy_daemon.author_server`` IS ``workflow.daemon_server``.

Re-binds ``sys.modules`` so any ``from fantasy_daemon import author_server``
or ``import fantasy_daemon.author_server`` transparently resolves to
``workflow.daemon_server``. Same pattern as the other 4 Phase 1 Part 2
shims (fantasy_author/__init__.py, domains/fantasy_author/__init__.py,
workflow/author_server.py, packaging mirror). No snapshot re-export —
module-level state written through one alias is visible through the
other.

Previously this file used ``from workflow.daemon_server import *``,
which is a point-in-time snapshot: writes through
``fantasy_daemon.author_server.X = ...`` were NOT visible at
``workflow.daemon_server.X``. Switching to sys.modules rebind makes
the 5 shims uniform. See `docs/audits/2026-04-18-rename-tree-consistency-audit.md` §3.

Gated by ``WORKFLOW_AUTHOR_RENAME_COMPAT`` (default on). Removed in
Phase 5 after all callers migrate to ``workflow.daemon_server``.
"""

from __future__ import annotations

import sys
import warnings

from workflow._rename_compat import rename_compat_enabled

if not rename_compat_enabled():
    raise ImportError(
        "fantasy_daemon.author_server is deprecated; import "
        "workflow.daemon_server instead. Set "
        "WORKFLOW_AUTHOR_RENAME_COMPAT=1 to temporarily re-enable the "
        "back-compat shim."
    )

warnings.warn(
    "fantasy_daemon.author_server is a back-compat alias; migrate imports "
    "to workflow.daemon_server",
    DeprecationWarning,
    stacklevel=2,
)

import workflow.daemon_server as _ds  # noqa: E402

sys.modules[__name__] = _ds
