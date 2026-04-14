"""Per-universe bid settlement ledger (Phase G).

Each time a daemon finalizes a NodeBid execution it appends an entry
to ``<universe>/bid_ledger.json``. Append is serialized via a sidecar
``.lock`` file so concurrent finalizations from different threads
don't clobber each other.

Distinct from the dispatcher-side activity.log in that the ledger is
the billable record — settlement reconciliation reads this.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

LEDGER_FILENAME = "bid_ledger.json"
LEDGER_LOCK_FILENAME = "bid_ledger.json.lock"


def ledger_path(universe_path: Path) -> Path:
    return Path(universe_path) / LEDGER_FILENAME


def _lock_path(universe_path: Path) -> Path:
    return Path(universe_path) / LEDGER_LOCK_FILENAME


@contextlib.contextmanager
def _ledger_lock(universe_path: Path) -> Iterator[None]:
    Path(universe_path).mkdir(parents=True, exist_ok=True)
    lf = _lock_path(universe_path)
    fd = os.open(str(lf), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        if sys.platform == "win32":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if sys.platform == "win32":
                import msvcrt
                try:
                    os.lseek(fd, 0, 0)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
    finally:
        os.close(fd)


def read_ledger(universe_path: Path) -> list[dict]:
    """Return ledger entries. Returns ``[]`` on missing / corrupt file
    (corrupt is logged, not raised — the ledger is append-only
    accounting, best-effort read)."""
    p = ledger_path(universe_path)
    if not p.exists():
        return []
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return []
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("bid_ledger: corrupt at %s: %s", p, exc)
        return []
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict)]


def append_ledger_entry(universe_path: Path, entry: dict) -> None:
    """File-locked append of a single ledger entry."""
    p = ledger_path(universe_path)
    with _ledger_lock(universe_path):
        data = read_ledger(universe_path)
        data.append(dict(entry))
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
        os.replace(tmp, p)
