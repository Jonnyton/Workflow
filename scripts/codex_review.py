#!/usr/bin/env python3
"""Programmatic Codex dispatch — offload a cross-family review to Codex's OWN
budget without spending a Claude context.

Runs `codex exec` (read-only sandbox) as a plain subprocess and writes Codex's
final verdict to a file. Meant to be launched by the Claude Code lead via a
BACKGROUND Bash call (`run_in_background`): the lead keeps working while Codex
churns on its own quota, and reads the verdict file when the job completes.

Why this instead of a Claude "liaison teammate": a teammate is another Claude
context (opus, per `latest_model_guard.py`) — it burns Claude tokens / rate-limit
to relay, which defeats the point of offloading to Codex. This wrapper spends
ZERO Claude context; Codex does the reasoning on Codex's budget. The only Claude
cost is launching the job and reading back a short verdict.

Usage (typically backgrounded):
  python scripts/codex_review.py --out review.md --prompt "<review ask>"
  python scripts/codex_review.py --out review.md --diff-base origin/main \
      --prompt "focus on the auth boundary"

The verdict file ends with a line: `VERDICT: approve|adapt|reject` plus findings.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ADVERSARIAL_PREAMBLE = (
    "You are performing an opposite-provider (cross-family) code review. Be "
    "adversarial: try to find the reason this is wrong before you approve it. "
    "Re-check the actual code and any cited sources — do not rubber-stamp. Finish "
    "with a single line 'VERDICT: approve' | 'VERDICT: adapt' | 'VERDICT: reject', "
    "then the concrete findings / required adaptations (most important first)."
)


def build_prompt(ask: str, diff_base: str | None) -> str:
    if diff_base:
        ask = (
            f"Review the changes on this branch vs `{diff_base}` — run "
            f"`git diff {diff_base}...HEAD` and read the changed files. {ask}"
        )
    return f"{ADVERSARIAL_PREAMBLE}\n\n{ask}"


def build_cmd(args: argparse.Namespace) -> list[str]:
    # Only verified `codex exec` flags. read-only is hard-coded: this path never
    # grants Codex write access. Codex can still run git/read in its sandbox.
    return [
        "codex",
        "exec",
        "-s",
        "read-only",
        "-C",
        args.cwd,
        "-o",
        args.out,
        build_prompt(args.prompt, args.diff_base),
    ]


def main() -> int:
    p = argparse.ArgumentParser(
        description="Background Codex review dispatcher (offloads to Codex's budget)."
    )
    p.add_argument("--prompt", required=True, help="The review ask / focus.")
    p.add_argument("--out", required=True, help="File to write Codex's final verdict to.")
    p.add_argument("--cwd", default=".", help="Repo/worktree root Codex reviews (default: cwd).")
    p.add_argument(
        "--diff-base",
        default=None,
        help="If set, ask Codex to review this branch's diff vs the given base branch.",
    )
    args = p.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = build_cmd(args)
    print(f"[codex_review] dispatching to Codex (read-only); verdict -> {args.out}", flush=True)
    try:
        proc = subprocess.run(cmd)
    except FileNotFoundError:
        print("[codex_review] 'codex' CLI not found on PATH.", file=sys.stderr)
        return 127
    if proc.returncode != 0:
        print(f"[codex_review] codex exec exited {proc.returncode}", file=sys.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
