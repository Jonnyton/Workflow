"""Back-compat shim: ``workflow.author_server`` IS ``workflow.daemon_server``.

Re-binds ``sys.modules`` so ``from workflow import author_server``,
``import workflow.author_server``, and ``from workflow.author_server
import X`` all resolve to the same module object as
``workflow.daemon_server``. No snapshot — module-level state written
through one alias is visible through the other.

Gated by ``WORKFLOW_AUTHOR_RENAME_COMPAT`` (default on). Removed in
Phase 5 after all callers migrate.

See ``docs/exec-plans/active/2026-04-15-author-to-daemon-rename.md``.
"""

from __future__ import annotations

import sys
import warnings

from workflow._rename_compat import rename_compat_enabled

if not rename_compat_enabled():
    raise ImportError(
        "workflow.author_server is deprecated; import "
        "workflow.daemon_server instead. Set "
        "WORKFLOW_AUTHOR_RENAME_COMPAT=1 to temporarily re-enable the "
        "back-compat shim."
    )

warnings.warn(
    "workflow.author_server is a back-compat alias; migrate imports to "
    "workflow.daemon_server",
    DeprecationWarning,
    stacklevel=2,
)

import workflow.daemon_server as _ds  # noqa: E402

sys.modules[__name__] = _ds
