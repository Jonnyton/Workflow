"""Pre-commit invariant: Worker CF Access header injection is present.

Checks that `deploy/cloudflare-worker/worker.js` (when staged or when the
path is passed explicitly) contains both:
  - env.CF_ACCESS_CLIENT_ID
  - env.CF_ACCESS_CLIENT_SECRET

These lines are the safety-critical Access header injection added in f4e74f5.
Removing them would silently break the Worker-to-tunnel auth and replicate the
2026-04-20 production incident (cutover went live against a Worker without the
Access headers).

Exit codes:
  0 — invariant satisfied (or worker.js not staged/present — no-op)
  2 — invariant violated: one or both access-header reads are missing

Usage (called by pre-commit hook):
    python scripts/pre_commit_invariant_worker.py [path/to/worker.js]

When called without arguments, reads the staged content of
`deploy/cloudflare-worker/worker.js` via `git show :path`. Falls back to
reading the file from disk if not staged (e.g. manual invocation).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

WORKER_PATH = "deploy/cloudflare-worker/worker.js"
REQUIRED_READS = [
    "env.CF_ACCESS_CLIENT_ID",
    "env.CF_ACCESS_CLIENT_SECRET",
]


def _get_staged_content(path: str) -> str | None:
    """Return staged content of `path` via git show, or None if not staged."""
    try:
        result = subprocess.run(
            ["git", "show", f":{path}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        pass
    return None


def _get_disk_content(path: str) -> str | None:
    p = Path(path)
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return None


def _is_worker_staged() -> bool:
    """Return True if WORKER_PATH appears in the git staged index."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return WORKER_PATH in result.stdout.splitlines()
    except FileNotFoundError:
        pass
    return False


def check(content: str) -> list[str]:
    """Return list of missing required reads (empty = all present = pass)."""
    return [r for r in REQUIRED_READS if r not in content]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if argv:
        # Explicit path provided (e.g. in tests or manual invocation).
        path = argv[0]
        content = _get_disk_content(path)
        if content is None:
            print(f"pre-commit [worker]: {path} not found — skipping", file=sys.stderr)
            return 0
    else:
        # Called from pre-commit hook: only check when worker.js is staged.
        if not _is_worker_staged():
            return 0  # worker.js not touched in this commit — no-op
        content = _get_staged_content(WORKER_PATH)
        if content is None:
            # Staged but can't read (e.g. deletion) — skip, not our concern.
            return 0

    missing = check(content)
    if not missing:
        print(
            "pre-commit [worker]: CF Access header reads present in worker.js",
            file=sys.stderr,
        )
        return 0

    print("pre-commit [worker]: INVARIANT VIOLATED", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "  deploy/cloudflare-worker/worker.js is missing CF Access header reads:",
        file=sys.stderr,
    )
    for m in missing:
        print(f"    - {m}", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "  These reads inject CF-Access-Client-Id / CF-Access-Client-Secret onto",
        file=sys.stderr,
    )
    print(
        "  every subrequest to the mcp.tinyassets.io tunnel origin. Removing them",
        file=sys.stderr,
    )
    print(
        "  silently breaks the Worker→tunnel auth (2026-04-20 production incident).",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print(
        "  Fix: restore the CF Access header injection in proxyToTunnel().",
        file=sys.stderr,
    )
    print("  Override with --no-verify if the removal is intentional.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
