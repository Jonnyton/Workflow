"""Phase E tier-aware BranchTask dispatcher.

Stateless selection function over ``branch_tasks.json``. Called
exactly twice per ``_run_graph`` invocation — once at daemon startup
(before first graph compile) and once at each cycle boundary (between
wrapper returns). No internal timer, no continuous polling loop
(preflight §4.1 #2).

Priority function in Phase E is the minimum viable subset of memo §4.3:

    score = tier_weight[trigger_source]
          + recency_decay(queued_at)
          + user_boost(priority_weight)

Deferred terms (``bid``, ``goal_affinity``, ``cost_penalty``) are
zero. Their coefficients sit in :class:`DispatcherConfig` so Phase
F/G can wire them in without re-shaping ``score_task``.

R9 — dispatcher reads the queue only. Producers run inside the
graph's review gates; the dispatcher does not invoke them.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow.branch_tasks import BranchTask, append_task, read_queue

logger = logging.getLogger(__name__)

# Default tier weights per preflight §4.1 #2 + §4.3 Q2.
_DEFAULT_TIER_WEIGHTS: dict[str, float] = {
    "host_request": 100.0,
    "owner_queued": 80.0,
    "user_request": 60.0,
    "goal_pool": 40.0,
    "paid_bid": 50.0,
    "opportunistic": 10.0,
}


@dataclass
class DispatcherConfig:
    accept_external_requests: bool = True
    accept_goal_pool: bool = False
    accept_paid_bids: bool = False
    allow_opportunistic: bool = False
    tier_weights: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_TIER_WEIGHTS),
    )
    recency_half_life_seconds: float = 86400.0
    bid_coefficient: float = 0.0
    goal_affinity_coefficient: float = 0.0
    cost_penalty_coefficient: float = 0.0

    def tier_enabled(self, trigger_source: str) -> bool:
        if trigger_source in {"host_request", "owner_queued"}:
            return True
        if trigger_source == "user_request":
            return self.accept_external_requests
        if trigger_source == "goal_pool":
            return self.accept_goal_pool
        if trigger_source == "paid_bid":
            return self.accept_paid_bids
        if trigger_source == "opportunistic":
            return self.allow_opportunistic
        return False

    def tier_status_map(self) -> dict[str, str]:
        """Self-documenting status per tier (R11)."""
        return {
            "host_request": "live",
            "user_request": (
                "live" if self.accept_external_requests else "disabled"
            ),
            "owner_queued": "live",
            "goal_pool": (
                "live" if self.accept_goal_pool else "stubbed (Phase F)"
            ),
            "paid_bid": (
                "live" if self.accept_paid_bids else "stubbed (Phase G)"
            ),
            "opportunistic": (
                "live" if self.allow_opportunistic else "stubbed"
            ),
        }


def dispatcher_enabled() -> bool:
    """Read ``WORKFLOW_DISPATCHER_ENABLED``. Default on."""
    value = os.environ.get("WORKFLOW_DISPATCHER_ENABLED", "on")
    return value.strip().lower() not in {"off", "0", "false", "no"}


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def score_task(
    task: BranchTask,
    *,
    now_iso: str,
    config: DispatcherConfig,
) -> float:
    """Deterministic Phase E score.

    ``tier_weight + recency_decay + user_boost``. Other coefficients
    multiply zero in v1 but remain wired so Phase F/G slot in.
    """
    tier = config.tier_weights.get(task.trigger_source, 0.0)

    now = _parse_iso(now_iso) or datetime.now(timezone.utc)
    queued = _parse_iso(task.queued_at) or now
    age_s = max(0.0, (now - queued).total_seconds())
    # Exponential decay: boost fresh tasks slightly; decays to 0.
    # Scale of 10 picked so recency tweak doesn't cross tier boundaries.
    half_life = max(1.0, config.recency_half_life_seconds)
    recency = 10.0 * math.exp(-age_s * math.log(2) / half_life)

    boost = max(0.0, float(task.priority_weight))

    # Reserved terms (Phase F/G).
    bid_term = config.bid_coefficient * float(task.bid)
    goal_term = config.goal_affinity_coefficient  # coefficient only; no signal
    cost_term = -config.cost_penalty_coefficient

    return tier + recency + boost + bid_term + goal_term + cost_term


def run_branch_task_producers_into_queue(
    universe_path: Path,
    *,
    subscribed_goals: list[str],
    producer_config: dict | None = None,
) -> int:
    """Phase F: invoke every registered ``BranchTaskProducer`` and
    append emitted tasks into ``branch_tasks.json``.

    Called at the dispatcher boundary (cycle boundary), BEFORE
    ``select_next_task``. Idempotency is enforced at the queue
    level: a task whose ``branch_task_id`` is already present is
    NOT appended again (dedupe-on-append semantics preserve Phase F
    invariant 4).

    Returns the count appended.
    """
    from workflow.producers.branch_task import (
        registered_branch_task_producers,
        run_branch_task_producers,
    )

    producers = registered_branch_task_producers()
    if not producers:
        return 0
    emitted = run_branch_task_producers(
        Path(universe_path),
        subscribed_goals=subscribed_goals,
        producer_config=producer_config,
    )
    if not emitted:
        return 0
    existing = read_queue(Path(universe_path))
    existing_ids = {t.branch_task_id for t in existing}
    appended = 0
    for task in emitted:
        if task.branch_task_id in existing_ids:
            continue
        if not task.universe_id:
            # Pool producers don't know the subscriber's universe
            # at read time; stamp it from the dispatch context
            # (the directory name is the canonical universe_id).
            task.universe_id = Path(universe_path).name
        try:
            append_task(Path(universe_path), task)
            appended += 1
            existing_ids.add(task.branch_task_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "dispatcher: failed to append task %s from producer",
                task.branch_task_id,
            )
    return appended


def select_next_task(
    universe_path: Path,
    *,
    config: DispatcherConfig,
    now_iso: str | None = None,
) -> BranchTask | None:
    """Read queue, filter to pending + tier-enabled, return top score.

    Returns ``None`` on empty / no-eligible. Called event-driven at
    graph-cycle boundaries. NOT a polling loop.
    """
    queue = read_queue(universe_path)
    if not queue:
        return None
    now = now_iso or datetime.now(timezone.utc).isoformat()
    eligible: list[tuple[float, BranchTask]] = []
    for task in queue:
        if task.status != "pending":
            continue
        if not config.tier_enabled(task.trigger_source):
            continue
        s = score_task(task, now_iso=now, config=config)
        eligible.append((s, task))
    if not eligible:
        return None
    # Stable sort: primary score desc, tiebreak queued_at asc.
    eligible.sort(
        key=lambda pair: (-pair[0], pair[1].queued_at),
    )
    return eligible[0][1]


def load_dispatcher_config(universe_path: Path) -> DispatcherConfig:
    """Read ``<universe>/dispatcher_config.yaml``; defaults if missing.

    YAML keys mirror :class:`DispatcherConfig` field names. Missing
    file or missing keys silently fall back to defaults — the config
    is optional (preflight §4.1 #6).
    """
    cfg_path = Path(universe_path) / "dispatcher_config.yaml"
    if not cfg_path.exists():
        return DispatcherConfig()
    try:
        import yaml  # local import: dispatcher is hot-path-adjacent
    except ImportError:
        logger.warning(
            "pyyaml not available; using DispatcherConfig defaults "
            "for %s", universe_path,
        )
        return DispatcherConfig()
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 - broad log+fallback
        logger.warning(
            "Failed to read %s: %s; using defaults", cfg_path, exc,
        )
        return DispatcherConfig()
    if not isinstance(data, dict):
        return DispatcherConfig()

    kwargs: dict[str, Any] = {}
    for key in (
        "accept_external_requests", "accept_goal_pool",
        "accept_paid_bids", "allow_opportunistic",
        "recency_half_life_seconds", "bid_coefficient",
        "goal_affinity_coefficient", "cost_penalty_coefficient",
    ):
        if key in data:
            kwargs[key] = data[key]
    if "tier_weights" in data and isinstance(data["tier_weights"], dict):
        weights = dict(_DEFAULT_TIER_WEIGHTS)
        for k, v in data["tier_weights"].items():
            try:
                weights[k] = float(v)
            except (TypeError, ValueError):
                continue
        kwargs["tier_weights"] = weights

    return DispatcherConfig(**kwargs)
