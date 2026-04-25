"""Sandbox detection module.

Re-exports the key symbols from workflow.sandbox.detect so callers can do::

    from workflow.sandbox import detect_bwrap, SandboxStatus, SandboxUnavailableError
"""

from __future__ import annotations

from workflow.sandbox.detect import (
    _BWRAP_FAILURE_PATTERNS,
    SandboxStatus,
    SandboxUnavailableError,
    check_bwrap_output,
    detect_bwrap,
)

__all__ = [
    "SandboxStatus",
    "SandboxUnavailableError",
    "_BWRAP_FAILURE_PATTERNS",
    "check_bwrap_output",
    "detect_bwrap",
]
