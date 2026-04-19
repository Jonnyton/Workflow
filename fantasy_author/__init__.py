"""Back-compat shim: ``fantasy_author`` IS ``fantasy_daemon``.

Re-binds ``sys.modules`` so any ``import fantasy_author[.submodule]`` or
``from fantasy_author import X`` transparently returns the corresponding
object from the ``fantasy_daemon`` package. No re-export snapshot — both
aliases point at the same module objects, so writes through one are
visible through the other (same pattern as the original
``fantasy_author.runtime`` shim).

Gated by ``WORKFLOW_AUTHOR_RENAME_COMPAT`` (default on). Removed in
Phase 5 after all callers migrate to ``fantasy_daemon``.

See ``docs/exec-plans/active/2026-04-15-author-to-daemon-rename.md``.
"""

from __future__ import annotations

import sys
import warnings

from workflow._rename_compat import rename_compat_enabled

if not rename_compat_enabled():
    raise ImportError(
        "fantasy_author is deprecated; import fantasy_daemon instead. "
        "Set WORKFLOW_AUTHOR_RENAME_COMPAT=1 to temporarily re-enable the "
        "back-compat shim."
    )

warnings.warn(
    "fantasy_author is a back-compat alias; migrate imports to "
    "fantasy_daemon",
    DeprecationWarning,
    stacklevel=2,
)

import fantasy_daemon as _fd  # noqa: E402

sys.modules[__name__] = _fd
