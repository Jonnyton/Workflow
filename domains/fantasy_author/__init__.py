"""Back-compat shim: ``domains.fantasy_author`` IS ``domains.fantasy_daemon``.

Re-binds ``sys.modules`` so any ``import domains.fantasy_author[.X]`` or
``from domains.fantasy_author import Y`` transparently resolves to
``domains.fantasy_daemon``. Same pattern as ``fantasy_author/__init__.py``.

Gated by ``WORKFLOW_AUTHOR_RENAME_COMPAT`` (default on). Removed in
Phase 5.

See ``docs/exec-plans/active/2026-04-15-author-to-daemon-rename.md``.
"""

from __future__ import annotations

import sys
import warnings

from workflow._rename_compat import rename_compat_enabled

if not rename_compat_enabled():
    raise ImportError(
        "domains.fantasy_author is deprecated; import "
        "domains.fantasy_daemon instead. Set "
        "WORKFLOW_AUTHOR_RENAME_COMPAT=1 to temporarily re-enable the "
        "back-compat shim."
    )

warnings.warn(
    "domains.fantasy_author is a back-compat alias; migrate imports to "
    "domains.fantasy_daemon",
    DeprecationWarning,
    stacklevel=2,
)

import domains.fantasy_daemon as _fd  # noqa: E402

sys.modules[__name__] = _fd
