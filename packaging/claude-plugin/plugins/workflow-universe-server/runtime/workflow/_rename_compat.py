"""Back-compat flag for the Author -> Daemon rename transition.

Active during Phases 1-4. Flipped off (and file removed) in Phase 5.
See docs/exec-plans/active/2026-04-15-author-to-daemon-rename.md.
"""

from __future__ import annotations

import os

_FLAG_ENV = "WORKFLOW_AUTHOR_RENAME_COMPAT"


def rename_compat_enabled() -> bool:
    """Return True when back-compat shims/aliases should be exported."""
    raw = os.environ.get(_FLAG_ENV, "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}
