"""Durable BranchTask queue.

A BranchTask is a queued *execution intent*: "run branch X against
universe Y with inputs Z." Distinct from WorkTargets, which are
content (the scene, the canon repair, the plan). One WorkTarget may
spawn zero or many BranchTasks.

The queue is per-universe (``<universe>/branch_tasks.json``) — sibling
to ``work_targets.json``. All mutations go through a sidecar ``.lock``
file so concurrent ``submit_request`` + daemon-claim + mark-status
paths can't clobber one another. This is the codebase's first
file-lock primitive; the pattern is also exercised by the queue
race tests.

Startup GC moves terminal tasks older than
``ARCHIVE_AFTER_DAYS`` into ``branch_tasks_archive.json``. The
archive is append-only and never read by the dispatcher.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

QUEUE_FILENAME = "branch_tasks.json"
ARCHIVE_FILENAME = "branch_tasks_archive.json"
LOCK_FILENAME = "branch_tasks.json.lock"

# Exposed for test override (invariant 10).
ARCHIVE_AFTER_DAYS = 30

VALID_TRIGGER_SOURCES = frozenset({
    "host_request",
    "user_request",
    "owner_queued",
    "goal_pool",
    "opportunistic",
    "paid_bid",
})

VALID_STATUSES = frozenset({
    "pending", "running", "succeeded", "failed", "cancelled",
})
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})

# Valid transitions. `pending` can go to running or cancelled;
# running can go to any terminal state. Terminal states are sinks.
_VALID_TRANSITIONS = {
    "pending": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


@dataclass
class BranchTask:
    """Durable execution-intent record.

    Reserved fields (bid, goal_id, required_llm_type, evidence_url)
    are present in v1 with empty defaults so later producers can
    populate them without migration.
    """

    branch_task_id: str
    branch_def_id: str
    universe_id: str
    inputs: dict = field(default_factory=dict)
    trigger_source: str = "user_request"
    priority_weight: float = 0.0
    pickup_signal_weight: float = 0.0
    queued_at: str = ""
    claimed_by: str = ""
    status: str = "pending"
    bid: float = 0.0
    goal_id: str = ""
    required_llm_type: str = ""
    directed_daemon_id: str = ""
    required_domain_claims: list[str] = field(default_factory=list)
    required_claim_proofs: list[str] = field(default_factory=list)
    borrowed_role_context_id: str = ""
    evidence_url: str = ""
    error: str = ""
    cancel_requested: bool = False
    request_type: str = "branch_run"
    deadline: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BranchTask":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def queue_path(universe_path: Path) -> Path:
    return Path(universe_path) / QUEUE_FILENAME


def archive_path(universe_path: Path) -> Path:
    return Path(universe_path) / ARCHIVE_FILENAME


def _lock_path(universe_path: Path) -> Path:
    return Path(universe_path) / LOCK_FILENAME


@contextlib.contextmanager
def _file_lock(universe_path: Path) -> Iterator[None]:
    """Cross-platform exclusive lock on a sidecar .lock file.

    Windows uses ``msvcrt.locking`` with ``LK_LOCK`` (blocking with
    retry); POSIX uses ``fcntl.flock``. The sidecar pattern avoids
    racing with the JSON-read path: opening the data file with r+ for
    a lock serializes with json-read on Windows.

    The lock file is created on demand and left in place between
    operations; that is intentional — deleting it while another
    process holds the lock would unlink the descriptor and break the
    contract.
    """
    Path(universe_path).mkdir(parents=True, exist_ok=True)
    lock_file = _lock_path(universe_path)
    # Open for read+write, creating if missing.
    fd = os.open(
        str(lock_file),
        os.O_RDWR | os.O_CREAT,
        0o644,
    )
    try:
        if sys.platform == "win32":
            import msvcrt
            # Lock a single byte; retry on conflict. LK_LOCK blocks up
            # to ~10s per call, then raises OSError — loop until we
            # get it.
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_raw(qp: Path) -> list[dict]:
    if not qp.exists():
        return []
    try:
        raw = qp.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read {qp}: {exc}") from exc
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Corrupt queue at {qp}: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError(f"Queue at {qp} is not a list")
    return data


def _write_raw(qp: Path, data: list[dict]) -> None:
    qp.parent.mkdir(parents=True, exist_ok=True)
    tmp = qp.with_suffix(qp.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(tmp, qp)


def read_queue(universe_path: Path) -> list[BranchTask]:
    """File-locked read. Returns [] on missing file.

    Raises ``RuntimeError`` on corrupt JSON — Hard Rule 8, no silent
    fallback.
    """
    qp = queue_path(universe_path)
    with _file_lock(universe_path):
        raw = _read_raw(qp)
    return [BranchTask.from_dict(row) for row in raw if isinstance(row, dict)]


def append_task(universe_path: Path, task: BranchTask) -> None:
    """File-locked append. Stamps ``queued_at`` if missing."""
    if task.trigger_source not in VALID_TRIGGER_SOURCES:
        raise ValueError(f"Invalid trigger_source: {task.trigger_source}")
    if task.status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {task.status}")
    if not task.queued_at:
        task.queued_at = _now_iso()
    qp = queue_path(universe_path)
    with _file_lock(universe_path):
        raw = _read_raw(qp)
        raw.append(task.to_dict())
        _write_raw(qp, raw)


def _normalize_tokens(values: list[str] | None) -> set[str]:
    if not values:
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def claim_eligibility_failure(
    task: BranchTask,
    *,
    claimer: str,
    claimer_daemon_id: str = "",
    domain_claims: list[str] | None = None,
    claim_proofs: list[str] | None = None,
    borrowed_role_context_ids: list[str] | None = None,
) -> str:
    """Return a machine-readable reason if this claimer cannot take task.

    Empty string means eligible. This is intentionally separate from scoring:
    claim-time identity, expertise, and proof requirements are hard filters.
    """
    claimed_identity = (claimer_daemon_id or claimer).strip()
    directed = task.directed_daemon_id.strip()
    if directed and claimed_identity != directed:
        return "directed_daemon_mismatch"

    required_domains = _normalize_tokens(task.required_domain_claims)
    if required_domains:
        domains = _normalize_tokens(domain_claims)
        if not required_domains.issubset(domains):
            borrowed = task.borrowed_role_context_id.strip()
            borrowed_roles = _normalize_tokens(borrowed_role_context_ids)
            if not borrowed or borrowed not in borrowed_roles:
                return "missing_domain_claims"

    required_proofs = _normalize_tokens(task.required_claim_proofs)
    if required_proofs and not required_proofs.issubset(_normalize_tokens(claim_proofs)):
        return "missing_claim_proofs"

    return ""


def claim_task(
    universe_path: Path,
    task_id: str,
    claimer: str,
    *,
    claimer_daemon_id: str = "",
    domain_claims: list[str] | None = None,
    claim_proofs: list[str] | None = None,
    borrowed_role_context_ids: list[str] | None = None,
) -> BranchTask | None:
    """File-locked claim. Returns claimed task, or None if already
    claimed / missing / not pending / ineligible.
    """
    qp = queue_path(universe_path)
    with _file_lock(universe_path):
        raw = _read_raw(qp)
        for row in raw:
            if not isinstance(row, dict):
                continue
            if row.get("branch_task_id") != task_id:
                continue
            if row.get("status") != "pending":
                return None
            task = BranchTask.from_dict(row)
            if claim_eligibility_failure(
                task,
                claimer=claimer,
                claimer_daemon_id=claimer_daemon_id,
                domain_claims=domain_claims,
                claim_proofs=claim_proofs,
                borrowed_role_context_ids=borrowed_role_context_ids,
            ):
                return None
            row["status"] = "running"
            row["claimed_by"] = claimer
            _write_raw(qp, raw)
            return BranchTask.from_dict(row)
    return None


def mark_status(
    universe_path: Path,
    task_id: str,
    *,
    status: str,
    error: str = "",
) -> None:
    """File-locked status update. Raises on invalid transition."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    qp = queue_path(universe_path)
    with _file_lock(universe_path):
        raw = _read_raw(qp)
        for row in raw:
            if not isinstance(row, dict):
                continue
            if row.get("branch_task_id") != task_id:
                continue
            current = row.get("status", "pending")
            if status not in _VALID_TRANSITIONS.get(current, set()):
                raise ValueError(
                    f"Invalid transition {current} -> {status} "
                    f"for task {task_id}"
                )
            row["status"] = status
            if error:
                row["error"] = error
            _write_raw(qp, raw)
            return
        raise KeyError(f"Task {task_id} not found")


def request_task_cancel(universe_path: Path, task_id: str) -> bool:
    """Set ``cancel_requested=True`` on a task row.

    Cooperative-cancel flag paralleling ``runs.request_cancel``. The
    graph's stream loop polls ``is_task_cancel_requested`` and breaks
    at the next inter-node event; the daemon then finalizes the
    claimed task as ``cancelled`` rather than ``failed``.

    Returns True if the row was updated, False if the task is not
    present or is already in a terminal state (setting the flag on
    a terminal task is a no-op so stale MCP calls can't resurrect
    it).
    """
    qp = queue_path(universe_path)
    if not qp.exists():
        return False
    with _file_lock(universe_path):
        raw = _read_raw(qp)
        for row in raw:
            if not isinstance(row, dict):
                continue
            if row.get("branch_task_id") != task_id:
                continue
            if row.get("status") in TERMINAL_STATUSES:
                return False
            if row.get("cancel_requested"):
                return True  # idempotent
            row["cancel_requested"] = True
            _write_raw(qp, raw)
            return True
    return False


def is_task_cancel_requested(universe_path: Path, task_id: str) -> bool:
    """Return True if a cooperative-cancel has been requested.

    Read-only helper — does not mutate the queue. Safe to call in a
    hot stream loop. Missing task or missing flag → False.
    """
    qp = queue_path(universe_path)
    if not qp.exists():
        return False
    with _file_lock(universe_path):
        raw = _read_raw(qp)
    for row in raw:
        if not isinstance(row, dict):
            continue
        if row.get("branch_task_id") != task_id:
            continue
        return bool(row.get("cancel_requested", False))
    return False


def recover_claimed_tasks(universe_path: Path) -> int:
    """Restart recovery: reset any ``running`` rows to ``pending``.

    Claimed-but-unfinished tasks at daemon startup can't know whether
    the previous daemon finished them; safest is to re-queue. Returns
    the count reset.
    """
    qp = queue_path(universe_path)
    if not qp.exists():
        return 0
    count = 0
    with _file_lock(universe_path):
        raw = _read_raw(qp)
        for row in raw:
            if isinstance(row, dict) and row.get("status") == "running":
                row["status"] = "pending"
                row["claimed_by"] = ""
                count += 1
        if count:
            _write_raw(qp, raw)
    if count:
        logger.info(
            "branch_tasks recovery: reset %d running->pending in %s",
            count, universe_path,
        )
    return count


def garbage_collect(
    universe_path: Path,
    *,
    archive_after_days: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Move old terminal tasks to archive.

    Pending/running tasks are never archived regardless of age.
    Constant ``archive_after_days`` exposed for test override. Returns
    ``{"archived": int, "kept": int}``.
    """
    days = (
        archive_after_days
        if archive_after_days is not None
        else ARCHIVE_AFTER_DAYS
    )
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    qp = queue_path(universe_path)
    ap = archive_path(universe_path)
    if not qp.exists():
        return {"archived": 0, "kept": 0}
    archived = 0
    with _file_lock(universe_path):
        raw = _read_raw(qp)
        keep: list[dict] = []
        to_archive: list[dict] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            status = row.get("status", "")
            queued_at = row.get("queued_at", "")
            if status in TERMINAL_STATUSES and queued_at:
                try:
                    qt = datetime.fromisoformat(queued_at)
                except ValueError:
                    keep.append(row)
                    continue
                if qt.tzinfo is None:
                    qt = qt.replace(tzinfo=timezone.utc)
                if qt < cutoff:
                    to_archive.append(row)
                    continue
            keep.append(row)
        if to_archive:
            existing_archive: list[dict] = []
            if ap.exists():
                try:
                    a_raw = ap.read_text(encoding="utf-8")
                    if a_raw.strip():
                        loaded = json.loads(a_raw)
                        if isinstance(loaded, list):
                            existing_archive = loaded
                except (OSError, json.JSONDecodeError):
                    logger.warning(
                        "Corrupt archive at %s; starting fresh", ap,
                    )
            existing_archive.extend(to_archive)
            ap.parent.mkdir(parents=True, exist_ok=True)
            tmp = ap.with_suffix(ap.suffix + ".tmp")
            tmp.write_text(
                json.dumps(existing_archive, indent=2, default=str),
                encoding="utf-8",
            )
            os.replace(tmp, ap)
            _write_raw(qp, keep)
            archived = len(to_archive)
    if archived:
        logger.info(
            "branch_tasks GC: archived %d terminal tasks from %s",
            archived, universe_path,
        )
    return {"archived": archived, "kept": len(raw) - archived}


def new_task_id() -> str:
    """Generate a unique branch_task_id. ULID-like (time + random hex)."""
    return f"bt_{int(time.time() * 1000):013d}_{os.urandom(4).hex()}"
