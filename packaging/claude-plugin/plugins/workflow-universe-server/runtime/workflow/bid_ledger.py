"""Deprecated alias for ``workflow.bid_execution_log`` (renamed in
Phase H, closes G.2 follow-up #4).

The new module disambiguates this per-universe daemon-local log from
the repo-root-level immutable settlement ledger at
``workflow/settlements.py``. New code should import from
``workflow.bid_execution_log`` directly; this shim re-exports the
full surface for one deprecation cycle so external callers keep
working.
"""

from __future__ import annotations

from workflow.bid_execution_log import (
    LEDGER_FILENAME,
    LEDGER_LOCK_FILENAME,
    append_execution_log_entry,
    append_ledger_entry,
    execution_log_path,
    ledger_path,
    read_execution_log,
    read_ledger,
)

__all__ = [
    "LEDGER_FILENAME",
    "LEDGER_LOCK_FILENAME",
    "append_ledger_entry",
    "append_execution_log_entry",
    "ledger_path",
    "execution_log_path",
    "read_ledger",
    "read_execution_log",
]
