"""Cloud-side node-executor worker — real 24/7 uptime for node execution.

Motivation
----------
Today's droplet container runs ``python -m workflow.universe_server`` which
is MCP-server-only. It answers protocol handshakes, it lists tools, it
returns ``get_status`` output — but it does NOT execute queued
BranchTasks. Execution depends on the host's Windows tray running
``fantasy_daemon``. When the host's laptop is off, queued requests
pile up at ``pending_requests`` forever.

Evidence from live prod 2026-04-22:
  last_activity=2026-04-20T05:44Z (~2d stale)
  pending_requests=3
  activity_log=0 entries
  phase=offline/dormant-starved

This module closes that gap. It runs as a sibling container to the MCP
daemon, identifies itself as ``cloud-droplet`` (distinct from the host's
``host`` identity), and supervises a ``fantasy_daemon`` subprocess
against the active universe. The subprocess's normal claim→execute→
finalize loop picks up queued tasks via ``dispatcher.select_next_task``
+ ``branch_tasks.claim_task``. The claim is file-locked so the host's
tray + the cloud worker can run concurrently without double-claiming.

Why supervise a subprocess instead of re-implementing the claim loop?
  - ``fantasy_daemon._run_graph`` is ~500 lines tightly coupled to
    SqliteSaver, dashboard events, knowledge graph, heartbeat. Replicating
    it in-process would be a substantial refactor.
  - The subprocess inherits ``/etc/workflow/env`` (via compose env_file)
    so OPENAI_API_KEY + UNIVERSE_SERVER_* all flow through cleanly.
  - Supervision is simple: restart on exit, exponential backoff on
    repeated failures. The GHA p0-outage-triage watchdog-hotloop class
    already covers the pathological case if backoff hits its ceiling.

Concurrency safety
------------------
``workflow.branch_tasks.claim_task`` is file-locked via a sidecar .lock
file (see ``workflow/branch_tasks.py:_file_lock``). Two fantasy_daemon
processes on different hosts claiming tasks in the same universe dir
will race for the lock; the loser sees ``status != "pending"`` and
returns None. No double-claim is possible.

The cloud worker identifies itself via ``UNIVERSE_SERVER_HOST_USER=
cloud-droplet`` so activity log entries distinguish laptop-host runs
from cloud-droplet runs. Default ``host`` is the laptop; ``cloud-droplet``
is this supervisor's subprocess.

LLM routing
-----------
The subprocess inherits ``OPENAI_API_KEY`` from the env file. No new
secrets are required. Optionally, host can set ``FANTASY_DAEMON_LLM_TYPES``
or ``WORKFLOW_PIN_WRITER`` on the cloud side to pin a cheap model and
let the host's tray handle the expensive runs when it's online — that
configuration is orthogonal to this supervisor and applies naturally
via ``/etc/workflow/env``.

Stdlib only.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Defaults tuned for a droplet-scale workload.
DEFAULT_IDLE_BACKOFF_S = 10.0     # Seconds to sleep after a clean exit.
DEFAULT_CRASH_BACKOFF_S = 5.0     # Initial backoff on non-zero exit.
DEFAULT_MAX_BACKOFF_S = 300.0     # 5-min ceiling on exponential backoff.
DEFAULT_BACKOFF_MULT = 2.0        # Doubling per consecutive crash.
DEFAULT_POLL_INTERVAL_S = 0.5     # Subprocess monitor poll granularity.

# Host identity. Matches AGENTS.md §Configuration →
# UNIVERSE_SERVER_HOST_USER semantics. We default to "cloud-droplet"
# so activity-log entries are distinguishable from the laptop's "host"
# identity.
DEFAULT_HOST_USER = "cloud-droplet"


def _resolve_universe_path() -> Path:
    """Return the universe path the subprocess should operate on.

    Precedence (first non-empty wins):
      1. ``WORKFLOW_UNIVERSE`` env var (explicit override).
      2. ``$WORKFLOW_DATA_DIR/$UNIVERSE_SERVER_DEFAULT_UNIVERSE``.
      3. First directory under ``WORKFLOW_DATA_DIR`` that has a
         ``PROGRAM.md`` (auto-selects the active universe in the common
         "one universe" droplet deployment).
      4. ``$WORKFLOW_DATA_DIR/default-universe`` as a last-resort fallback.
    """
    explicit = os.environ.get("WORKFLOW_UNIVERSE", "").strip()
    if explicit:
        return Path(explicit)

    from workflow.storage import data_dir
    base = data_dir()

    default_uid = os.environ.get("UNIVERSE_SERVER_DEFAULT_UNIVERSE", "").strip()
    if default_uid:
        candidate = base / default_uid
        if candidate.is_dir():
            return candidate

    if base.is_dir():
        for entry in sorted(base.iterdir()):
            if entry.is_dir() and (entry / "PROGRAM.md").exists():
                return entry

    return base / "default-universe"


def _cloud_host_user() -> str:
    """Host-user identity for activity log entries.

    Operators can override via ``UNIVERSE_SERVER_HOST_USER`` but the
    default is ``cloud-droplet`` so the droplet's activity is trivially
    distinguishable from the laptop's ``host`` entries in ``get_status``.
    """
    override = os.environ.get("UNIVERSE_SERVER_HOST_USER", "").strip()
    return override or DEFAULT_HOST_USER


def _build_subprocess_env() -> dict[str, str]:
    """Construct the env dict the fantasy_daemon subprocess inherits.

    Starts from the parent env, overlays the cloud-specific host-user
    identity. Keeps OPENAI_API_KEY + WORKFLOW_* + dispatcher flags +
    LLM routing vars in place (inherited from parent / env file).
    """
    env = dict(os.environ)
    env["UNIVERSE_SERVER_HOST_USER"] = _cloud_host_user()
    # Make sure unified execution is on — dispatcher pick is gated on
    # this flag. It defaults on in production but we force it here so
    # cloud worker behavior is deterministic regardless of env file.
    env.setdefault("WORKFLOW_UNIFIED_EXECUTION", "1")
    return env


def _spawn_fantasy_daemon(
    universe: Path,
    *,
    python: str = sys.executable,
    module: str = "fantasy_daemon",
    extra_args: list[str] | None = None,
) -> subprocess.Popen:
    """Spawn ``python -m fantasy_daemon --universe <path> --no-tray``.

    Returns the ``Popen`` handle. Caller owns lifecycle.
    """
    args = [
        python, "-m", module,
        "--universe", str(universe),
        "--no-tray",
    ]
    if extra_args:
        args.extend(extra_args)
    env = _build_subprocess_env()
    logger.info(
        "spawning fantasy_daemon: universe=%s host_user=%s",
        universe, env.get("UNIVERSE_SERVER_HOST_USER"),
    )
    return subprocess.Popen(args, env=env)


def _compute_backoff(
    crash_count: int,
    *,
    base: float,
    mult: float,
    ceiling: float,
) -> float:
    """Exponential backoff: ``min(base * mult^(crash_count-1), ceiling)``.

    crash_count=1 → base, crash_count=2 → base*mult, etc. Capped so a
    long-running outage doesn't push retry gaps into hours.
    """
    if crash_count <= 0:
        return 0.0
    delay = base * (mult ** (crash_count - 1))
    return min(delay, ceiling)


class SupervisorState:
    """Runtime state for the supervisor loop. Testable without spawning.

    Tracks consecutive crashes + last exit status so the loop can
    compute correct backoff + recognize "clean shutdown vs. crash".
    """

    def __init__(self) -> None:
        self.crash_count = 0
        self.total_spawns = 0
        self.total_clean_exits = 0
        self.total_crashes = 0

    def record_exit(self, returncode: int) -> None:
        self.total_spawns += 1
        if returncode == 0:
            self.crash_count = 0
            self.total_clean_exits += 1
        else:
            self.crash_count += 1
            self.total_crashes += 1

    def summary(self) -> str:
        return (
            f"spawns={self.total_spawns} "
            f"clean={self.total_clean_exits} "
            f"crashes={self.total_crashes} "
            f"consec={self.crash_count}"
        )


def run_supervisor(
    universe: Path,
    *,
    idle_backoff: float = DEFAULT_IDLE_BACKOFF_S,
    crash_backoff: float = DEFAULT_CRASH_BACKOFF_S,
    max_backoff: float = DEFAULT_MAX_BACKOFF_S,
    backoff_mult: float = DEFAULT_BACKOFF_MULT,
    poll_interval: float = DEFAULT_POLL_INTERVAL_S,
    max_iterations: int | None = None,
    spawn_fn=None,
    sleep_fn=None,
) -> SupervisorState:
    """Run the supervisor loop until max_iterations or SIGTERM.

    Each iteration:
      1. Spawn fantasy_daemon against the universe.
      2. Wait for it to exit.
      3. Record exit as clean or crash.
      4. Sleep idle_backoff (clean) or crash_backoff*mult^(crashes-1) (crash).

    ``max_iterations`` is an injection seam for tests — leave None in
    production for an unbounded loop. ``spawn_fn`` + ``sleep_fn`` are
    test seams so the loop can be exercised without subprocess I/O.
    None defaults resolve to the module-level ``_spawn_fantasy_daemon``
    + ``time.sleep`` at call time (not import time), so tests can
    monkeypatch the module attribute freely.
    """
    if spawn_fn is None:
        spawn_fn = _spawn_fantasy_daemon
    if sleep_fn is None:
        sleep_fn = time.sleep

    state = SupervisorState()
    iteration = 0

    # SIGTERM handling: clean exit on compose stop / systemctl stop.
    # Sets a flag the loop checks between iterations.
    stopping = {"flag": False}

    def _handle_sigterm(signum, frame):
        logger.info("cloud_worker: received signal %s — shutting down", signum)
        stopping["flag"] = True

    # Install handler only when running as __main__; tests call
    # run_supervisor directly and manage their own signals.
    if threading_is_main():
        try:
            signal.signal(signal.SIGTERM, _handle_sigterm)
            signal.signal(signal.SIGINT, _handle_sigterm)
        except (ValueError, OSError):
            # Signals unavailable in certain embed contexts.
            pass

    while True:
        if stopping["flag"]:
            logger.info("cloud_worker: stop requested; exiting supervisor loop")
            break
        if max_iterations is not None and iteration >= max_iterations:
            break
        iteration += 1

        try:
            proc = spawn_fn(universe)
        except OSError as exc:
            logger.error("cloud_worker: spawn failed: %s", exc)
            state.crash_count += 1
            state.total_crashes += 1
            delay = _compute_backoff(
                state.crash_count,
                base=crash_backoff, mult=backoff_mult, ceiling=max_backoff,
            )
            logger.info("cloud_worker: backoff %.1fs after spawn failure (consec=%d)",
                        delay, state.crash_count)
            sleep_fn(delay)
            continue

        # Poll until subprocess exits, while respecting stop signal.
        returncode: int | None = None
        while True:
            if stopping["flag"]:
                logger.info("cloud_worker: terminating subprocess on stop signal")
                try:
                    proc.terminate()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    logger.warning("cloud_worker: subprocess did not exit; killing")
                    try:
                        proc.kill()
                    except OSError:
                        pass
                returncode = proc.returncode if proc.returncode is not None else -1
                break
            rc = proc.poll()
            if rc is not None:
                returncode = rc
                break
            sleep_fn(poll_interval)

        state.record_exit(returncode if returncode is not None else -1)
        logger.info(
            "cloud_worker: subprocess exited rc=%s (%s); %s",
            returncode,
            "clean" if returncode == 0 else "crash",
            state.summary(),
        )

        if stopping["flag"]:
            break

        if returncode == 0:
            delay = idle_backoff
        else:
            delay = _compute_backoff(
                state.crash_count,
                base=crash_backoff, mult=backoff_mult, ceiling=max_backoff,
            )
        logger.info("cloud_worker: sleeping %.1fs before next spawn", delay)
        sleep_fn(delay)

    return state


def threading_is_main() -> bool:
    """Return True when called from the main thread.

    signal.signal() only works from the main thread. We guard the
    handler install so tests that invoke run_supervisor from a worker
    thread don't trip.
    """
    import threading
    return threading.current_thread() is threading.main_thread()


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="workflow.cloud_worker",
        description="Cloud-side supervisor for 24/7 node execution.",
    )
    parser.add_argument(
        "--universe",
        default="",
        help="Explicit universe path. Default: WORKFLOW_UNIVERSE / "
             "first-PROGRAM.md / WORKFLOW_DATA_DIR/default-universe.",
    )
    parser.add_argument(
        "--idle-backoff", type=float, default=DEFAULT_IDLE_BACKOFF_S,
        help=f"Seconds to sleep after a clean daemon exit (default: "
             f"{DEFAULT_IDLE_BACKOFF_S}).",
    )
    parser.add_argument(
        "--crash-backoff", type=float, default=DEFAULT_CRASH_BACKOFF_S,
        help=f"Initial backoff on crash (default: {DEFAULT_CRASH_BACKOFF_S}).",
    )
    parser.add_argument(
        "--max-backoff", type=float, default=DEFAULT_MAX_BACKOFF_S,
        help=f"Backoff ceiling (default: {DEFAULT_MAX_BACKOFF_S}).",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="Stop after this many supervisor iterations (testing only).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="DEBUG-level logging.",
    )
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    universe = Path(args.universe) if args.universe else _resolve_universe_path()
    if not universe.exists():
        logger.warning("cloud_worker: universe dir does not exist yet: %s", universe)
        logger.warning("cloud_worker: fantasy_daemon will create it on first run")

    logger.info(
        "cloud_worker: starting supervisor host=%s universe=%s host_user=%s",
        socket.gethostname(), universe, _cloud_host_user(),
    )

    state = run_supervisor(
        universe,
        idle_backoff=args.idle_backoff,
        crash_backoff=args.crash_backoff,
        max_backoff=args.max_backoff,
        max_iterations=args.max_iterations,
    )
    logger.info("cloud_worker: supervisor exited; %s", state.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
