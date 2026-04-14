"""NodeBid dataclass + I/O helpers (Phase G).

A NodeBid is a cross-universe, bid-priced, single-node execution
request stored as YAML under ``<repo_root>/bids/<node_bid_id>.yaml``.
The NodeBidProducer reads these, emits BranchTasks with
``branch_def_id = "<node_bid>" + node_def_id`` so the dispatcher
cycle can pick them by tier, and ``_run_graph`` routes them to
``execute_node_bid`` instead of the Branch wrapper stream.

Flat-dict invariant on ``inputs`` is inherited from Phase F
(``validate_pool_task_inputs``). See docs/specs/phase_g_preflight.md §R4.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from workflow.producers.goal_pool import validate_pool_task_inputs

logger = logging.getLogger(__name__)

BIDS_DIRNAME = "bids"


@dataclass
class NodeBid:
    """Cross-universe node-execution bid.

    ``status`` transitions:
      open → claimed:<daemon_id> → succeeded | failed
      open → expired (by external sweep, not this module)
    """

    node_bid_id: str
    node_def_id: str
    required_llm_type: str = ""
    inputs: dict = field(default_factory=dict)
    bid: float = 0.0
    submitted_by: str = ""
    status: str = "open"
    evidence_url: str = ""
    submitted_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NodeBid":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def validate_node_bid_inputs(inputs: object) -> tuple[bool, str]:
    """Reuse Phase F validator verbatim — same flat-dict invariant."""
    return validate_pool_task_inputs(inputs)


def bids_dir(repo_root: Path) -> Path:
    return Path(repo_root) / BIDS_DIRNAME


def bid_path(repo_root: Path, node_bid_id: str) -> Path:
    return bids_dir(repo_root) / f"{node_bid_id}.yaml"


def _lock_path(repo_root: Path, node_bid_id: str) -> Path:
    return bids_dir(repo_root) / f"{node_bid_id}.yaml.lock"


@contextlib.contextmanager
def _bid_file_lock(repo_root: Path, node_bid_id: str):
    """Cross-platform lock on a sidecar ``.lock`` file for one bid.

    Mirrors ``branch_tasks._file_lock`` but per-bid so concurrent
    operations on different bids don't serialize against each other.
    """
    bids_dir(repo_root).mkdir(parents=True, exist_ok=True)
    lf = _lock_path(repo_root, node_bid_id)
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


def write_node_bid_post(repo_root: Path, bid_dict: dict) -> Path:
    """Write a NodeBid YAML under ``<repo_root>/bids/<id>.yaml``.

    Returns the output path. Caller is responsible for validation.
    """
    import yaml

    node_bid_id = str(bid_dict.get("node_bid_id") or "").strip()
    if not node_bid_id:
        raise ValueError("node_bid_id required")
    out = bid_path(repo_root, node_bid_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(dict(bid_dict), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return out


def read_node_bids(repo_root: Path) -> list[NodeBid]:
    """Scan ``<repo_root>/bids/*.yaml``. Malformed entries are skipped
    with a WARN log (never raise from read)."""
    d = bids_dir(repo_root)
    if not d.is_dir():
        return []
    import yaml
    out: list[NodeBid] = []
    for p in sorted(d.glob("*.yaml")):
        try:
            raw = p.read_text(encoding="utf-8")
            data = yaml.safe_load(raw) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("node_bid: malformed YAML at %s: %s", p, exc)
            continue
        if not isinstance(data, dict):
            logger.warning("node_bid: %s is not a mapping; skipping", p)
            continue
        # Filename stem wins — prevents a malicious rename-in-place attack.
        data["node_bid_id"] = p.stem
        try:
            out.append(NodeBid.from_dict(data))
        except Exception as exc:  # noqa: BLE001
            logger.warning("node_bid: %s failed to parse: %s", p, exc)
            continue
    return out


def read_node_bid(repo_root: Path, node_bid_id: str) -> NodeBid | None:
    """Read one bid by id. Returns None on missing."""
    p = bid_path(repo_root, node_bid_id)
    if not p.exists():
        return None
    import yaml
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("node_bid: read %s failed: %s", p, exc)
        return None
    if not isinstance(data, dict):
        return None
    data["node_bid_id"] = p.stem
    try:
        return NodeBid.from_dict(data)
    except Exception:  # noqa: BLE001
        return None


def claim_node_bid(
    repo_root: Path, node_bid_id: str, daemon_id: str,
) -> bool:
    """Advisory first-wins claim. Returns True if we became the
    claim-holder, False if the bid was already claimed / terminal /
    missing.

    Concurrency note: the accompanying BranchTask claim (via
    ``claim_task``) is the atomic serialization point for the
    dispatcher. This advisory YAML update is for cross-host visibility
    only. See preflight R13 (accepted double-execution for v1).
    """
    import yaml

    with _bid_file_lock(repo_root, node_bid_id):
        p = bid_path(repo_root, node_bid_id)
        if not p.exists():
            return False
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(data, dict):
            return False
        if data.get("status") != "open":
            return False
        data["status"] = f"claimed:{daemon_id}"
        p.write_text(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return True


def update_node_bid_status(
    repo_root: Path,
    node_bid_id: str,
    *,
    status: str,
    evidence_url: str = "",
) -> bool:
    """File-locked status write. Returns True on success."""
    import yaml

    with _bid_file_lock(repo_root, node_bid_id):
        p = bid_path(repo_root, node_bid_id)
        if not p.exists():
            return False
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(data, dict):
            return False
        data["status"] = status
        if evidence_url:
            data["evidence_url"] = evidence_url
        p.write_text(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return True


def new_node_bid_id() -> str:
    """Generate a unique node_bid_id. Prefix ``nb_`` distinguishes
    from BranchTask ids (``bt_``).
    """
    return f"nb_{int(time.time() * 1000):013d}_{os.urandom(4).hex()}"
