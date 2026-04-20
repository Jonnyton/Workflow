"""Uptime Canary — Layer 1 probe wrapper.

Per ``docs/design-notes/2026-04-19-uptime-canary-layered.md``.

Runs ``mcp_public_canary.probe_result`` against the live MCP URL, appends
one timestamped line to ``.agents/uptime.log``. Does not mutate STATUS.md;
alarm escalation is the separate ``scripts/uptime_alarm.py``'s job.

Invocation
----------
Windows Task Scheduler entry ``Workflow-Canary-L1`` invokes this every 2
minutes. Exit code mirrors the probe's: 0 green, nonzero red with reason
in the log line.

Stdlib only — must survive pip state dirty, tray crash, cloudflared
crash. If this canary can't run, the scheduler's "last run" error is
itself the alarm (per design-note §7).

URL precedence
--------------
1. ``--url`` CLI arg.
2. ``WORKFLOW_MCP_CANARY_URL`` env var.
3. ``https://mcp.tinyassets.io/mcp`` default (the current live route; the
   apex ``tinyassets.io/mcp`` URL from the design-note is the BROKEN one
   that caused the P0 outage).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
import time
from pathlib import Path

# Make the script importable regardless of CWD — Task Scheduler runs from
# the system32 directory by default.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from mcp_public_canary import CanaryError, probe_result  # noqa: E402

DEFAULT_URL = "https://mcp.tinyassets.io/mcp"
DEFAULT_TIMEOUT = 10.0
LOG_PATH = _REPO_ROOT / ".agents" / "uptime.log"
LOG_ROTATE_BYTES = 10 * 1024 * 1024


def _now_local_iso() -> str:
    """ISO-8601 with local timezone — matches design-note §2 format."""
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _rotate_if_needed(path: Path) -> None:
    try:
        if path.is_file() and path.stat().st_size > LOG_ROTATE_BYTES:
            backup = path.with_suffix(path.suffix + ".1")
            if backup.exists():
                backup.unlink()
            path.rename(backup)
    except OSError:
        # Rotation is best-effort; never fail the canary because rotation did.
        pass


def _append_log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed(LOG_PATH)
    with LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def _format_green(ts: str, url: str, rtt_ms: int) -> str:
    return f"{ts} GREEN layer=1 url={url} rtt_ms={rtt_ms}"


def _format_red(ts: str, url: str, exit_code: int, reason: str, rtt_ms: int) -> str:
    # Collapse newlines + strip the ``[canary] `` prefix so one probe = one line.
    reason_oneline = reason.replace("\n", " ").replace("\r", " ")
    return (
        f"{ts} RED   layer=1 url={url} exit={exit_code} "
        f"rtt_ms={rtt_ms} reason={reason_oneline!r}"
    )


def run_probe(url: str, timeout: float) -> int:
    ts = _now_local_iso()
    start = time.monotonic()
    try:
        probe_result(url, timeout)
    except CanaryError as exc:
        rtt_ms = int((time.monotonic() - start) * 1000)
        _append_log(_format_red(ts, url, exc.code, exc.msg, rtt_ms))
        return exc.code
    except Exception as exc:  # defensive — canary must never crash silently
        rtt_ms = int((time.monotonic() - start) * 1000)
        _append_log(_format_red(ts, url, 99, f"unexpected: {exc!r}", rtt_ms))
        return 99
    rtt_ms = int((time.monotonic() - start) * 1000)
    _append_log(_format_green(ts, url, rtt_ms))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Layer-1 uptime canary.")
    ap.add_argument(
        "--url",
        default=os.environ.get("WORKFLOW_MCP_CANARY_URL", DEFAULT_URL),
        help=f"MCP endpoint URL (default: env WORKFLOW_MCP_CANARY_URL or {DEFAULT_URL})",
    )
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = ap.parse_args(argv)
    return run_probe(args.url, args.timeout)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
