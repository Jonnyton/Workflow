"""Run-transcript rotation (BUG-023 Phase 2).

Moves run transcripts older than a retention window into an ``archived/``
subdirectory, compressed with gzip. Prevents the 2026-04-23 P0 class where
run artifacts accumulate silently until the volume fills.

Design:
- Reads retention days from ``WORKFLOW_RUN_TRANSCRIPT_RETENTION_DAYS``
  (default 30). Files whose mtime is older than ``now - retention`` move.
- Only regular files under ``<data_dir>/runs/`` (non-recursive relative
  to the runs root by default; descended when ``recursive=True``).
- Destination preserves the relative path + appends ``.gz`` suffix,
  placed under ``<data_dir>/runs/archived/``. Already-archived files are
  skipped; re-running is idempotent.
- Never crashes the caller — per-file errors are collected into the
  result, not raised. The rotation loop logs and continues.

Scheduled via ``scripts/rotate_run_transcripts.py`` (CLI entry) which
can be wired to a systemd timer or invoked inline from the existing
disk-watch cadence.
"""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from workflow.storage import data_dir

logger = logging.getLogger(__name__)

_DEFAULT_RETENTION_DAYS = 30
_ARCHIVED_DIRNAME = "archived"
_RUNS_DIRNAME = "runs"


@dataclass
class RotationResult:
    """Summary of a rotation pass, for logging + test assertions."""

    scanned: int = 0
    archived: int = 0
    skipped_already_archived: int = 0
    skipped_under_retention: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "scanned": self.scanned,
            "archived": self.archived,
            "skipped_already_archived": self.skipped_already_archived,
            "skipped_under_retention": self.skipped_under_retention,
            "errors": list(self.errors),
        }


def _retention_days_from_env() -> int:
    raw = os.environ.get("WORKFLOW_RUN_TRANSCRIPT_RETENTION_DAYS", "").strip()
    if not raw:
        return _DEFAULT_RETENTION_DAYS
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "WORKFLOW_RUN_TRANSCRIPT_RETENTION_DAYS=%r is not an integer; "
            "using default %d",
            raw, _DEFAULT_RETENTION_DAYS,
        )
        return _DEFAULT_RETENTION_DAYS
    if value < 1:
        logger.warning(
            "WORKFLOW_RUN_TRANSCRIPT_RETENTION_DAYS=%d is < 1; using default %d",
            value, _DEFAULT_RETENTION_DAYS,
        )
        return _DEFAULT_RETENTION_DAYS
    return value


def rotate_run_transcripts(
    runs_dir: Path | None = None,
    *,
    retention_days: int | None = None,
    now_fn: Callable[[], float] = time.time,
    recursive: bool = True,
) -> RotationResult:
    """Compress + archive run transcripts older than the retention window.

    Parameters
    ----------
    runs_dir
        Directory holding run transcripts. Defaults to
        ``data_dir() / "runs"``.
    retention_days
        Files with mtime older than ``now - retention_days`` move.
        Defaults to ``WORKFLOW_RUN_TRANSCRIPT_RETENTION_DAYS`` env var,
        or 30.
    now_fn
        Injection seam for mock clock. Returns POSIX seconds.
    recursive
        When True, descends into subdirectories under ``runs_dir`` and
        mirrors the relative path into ``archived/``. When False, only
        top-level files rotate.
    """
    base = runs_dir if runs_dir is not None else data_dir() / _RUNS_DIRNAME
    if retention_days is None:
        retention_days = _retention_days_from_env()

    result = RotationResult()

    if not base.is_dir():
        # No runs dir yet → nothing to rotate, not an error.
        return result

    cutoff_ts = now_fn() - (retention_days * 86400)
    archived_root = base / _ARCHIVED_DIRNAME

    iterator = base.rglob("*") if recursive else base.iterdir()
    for src in iterator:
        try:
            # Skip the archive dir itself + any contents beneath it.
            if archived_root in src.parents or src == archived_root:
                continue
            if not src.is_file():
                continue

            # Already-archived files (end with .gz under archived root) are
            # impossible here due to the parent-of-archived_root guard,
            # but also skip any .gz that looks like prior rotation output.
            if src.suffix == ".gz" and src.name.endswith(".gz"):
                # Inside the live runs dir (not archived/), a .gz file is
                # either a user-written artifact OR a prior rotation that
                # failed mid-move. Skip it either way — idempotent.
                result.skipped_already_archived += 1
                continue

            result.scanned += 1

            try:
                mtime = src.stat().st_mtime
            except OSError as exc:
                result.errors.append((str(src), f"stat failed: {exc}"))
                continue

            if mtime >= cutoff_ts:
                result.skipped_under_retention += 1
                continue

            rel = src.relative_to(base)
            dest = archived_root / rel.with_suffix(rel.suffix + ".gz")
            dest.parent.mkdir(parents=True, exist_ok=True)

            if dest.exists():
                # Rare: a previous run archived this file but didn't
                # delete the source. Treat as already-archived and drop
                # the source to converge.
                try:
                    src.unlink()
                    result.skipped_already_archived += 1
                except OSError as exc:
                    result.errors.append(
                        (str(src), f"unlink after stale-archive: {exc}")
                    )
                continue

            try:
                with src.open("rb") as fsrc, gzip.open(dest, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                src.unlink()
            except OSError as exc:
                result.errors.append((str(src), f"compress+move failed: {exc}"))
                # Clean up partial dest if write crashed mid-stream.
                try:
                    if dest.exists():
                        dest.unlink()
                except OSError:
                    pass
                continue

            result.archived += 1
            logger.info(
                "rotate_run_transcripts: archived %s -> %s",
                src, dest,
            )
        except Exception as exc:  # noqa: BLE001 — rotation never crashes
            result.errors.append((str(src), f"unexpected: {exc}"))
            logger.exception("rotate_run_transcripts: unexpected on %s", src)

    return result
