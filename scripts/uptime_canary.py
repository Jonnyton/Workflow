"""Uptime Canary — Layer 1 probe wrapper.

Per ``docs/design-notes/2026-04-19-uptime-canary-layered.md``.

Runs ``mcp_public_canary.probe_result`` against the canonical MCP URL,
appends one timestamped line to ``.agents/uptime.log``. Does not
mutate STATUS.md; alarm escalation is the separate ``scripts/uptime_alarm.py``'s job.

Invocation
----------
Windows Task Scheduler entry ``Workflow-Canary-L1`` invokes this every 2
minutes. Exit code mirrors the probe's: 0 green, nonzero red with reason
in the log line.

GHA usage (--once --format=gha):
    python scripts/uptime_canary.py --once --format=gha
Emits ``status=`` + ``msg=`` lines to stdout in $GITHUB_OUTPUT format.
Exit code mirrors the probe.

Stdlib only — must survive pip state dirty, tray crash, cloudflared
crash. If this canary can't run, the scheduler's "last run" error is
itself the alarm (per design-note §7).

URL precedence
--------------
1. ``--url`` CLI arg.
2. ``WORKFLOW_MCP_CANARY_URL`` env var.
3. ``https://tinyassets.io/mcp`` default (canonical public endpoint via
   Cloudflare Worker; host directive 2026-04-20 retired the direct-tunnel
   ``mcp.tinyassets.io/mcp`` as a public URL — single entry point only).
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

DEFAULT_URL = "https://tinyassets.io/mcp"
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


def _emit_gha_kv(key: str, value: str) -> None:
    """Write one $GITHUB_OUTPUT key=value entry (multiline-safe heredoc).

    Uses a per-call random UUID delimiter so probe output containing a bare
    ``CANARY_EOF`` line cannot close the heredoc early and corrupt $GITHUB_OUTPUT.
    """
    if "\n" in value or "\r" in value:
        import uuid  # stdlib; import here keeps top-level imports minimal
        delimiter = f"EOF_{uuid.uuid4().hex}"
        print(f"{key}<<{delimiter}")
        print(value)
        print(delimiter)
    else:
        print(f"{key}={value}")


def run_probe(url: str, timeout: float, fmt: str = "log") -> int:
    """Probe ``url`` once.

    ``fmt`` controls side-channel output:
    - ``"log"`` (default): append one line to LOG_PATH.
    - ``"gha"``: write ``status=`` + ``msg=`` to stdout in $GITHUB_OUTPUT format.
      Log line is still appended so the local .agents/uptime.log stays current.
    """
    ts = _now_local_iso()
    start = time.monotonic()
    try:
        probe_result(url, timeout)
    except CanaryError as exc:
        rtt_ms = int((time.monotonic() - start) * 1000)
        _append_log(_format_red(ts, url, exc.code, exc.msg, rtt_ms))
        if fmt == "gha":
            _emit_gha_kv("status", str(exc.code))
            _emit_gha_kv("msg", exc.msg)
        return exc.code
    except Exception as exc:  # defensive — canary must never crash silently
        rtt_ms = int((time.monotonic() - start) * 1000)
        msg = f"unexpected: {exc!r}"
        _append_log(_format_red(ts, url, 99, msg, rtt_ms))
        if fmt == "gha":
            _emit_gha_kv("status", "99")
            _emit_gha_kv("msg", msg)
        return 99
    rtt_ms = int((time.monotonic() - start) * 1000)
    _append_log(_format_green(ts, url, rtt_ms))
    if fmt == "gha":
        _emit_gha_kv("status", "0")
        _emit_gha_kv("msg", f"OK {url} rtt_ms={rtt_ms}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Layer-1 uptime canary.")
    ap.add_argument(
        "--url",
        default=os.environ.get("WORKFLOW_MCP_CANARY_URL", DEFAULT_URL),
        help=f"MCP endpoint URL (default: env WORKFLOW_MCP_CANARY_URL or {DEFAULT_URL})",
    )
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    ap.add_argument(
        "--once",
        action="store_true",
        help="Run a single probe and exit (default behavior; flag is an accepted no-op).",
    )
    ap.add_argument(
        "--format",
        dest="fmt",
        choices=["log", "gha"],
        default="log",
        help=(
            "Output format. 'log' (default): append to .agents/uptime.log. "
            "'gha': also emit status= + msg= lines to stdout for $GITHUB_OUTPUT capture."
        ),
    )
    args = ap.parse_args(argv)
    return run_probe(args.url, args.timeout, fmt=args.fmt)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
