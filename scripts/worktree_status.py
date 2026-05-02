"""Report git worktree pickup state for multi-provider Workflow sessions.

This complements scripts/claim_check.py. claim_check owns STATUS.md file
collisions; this script owns persistent local directories created by
``git worktree add``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

STALE_AFTER_SECONDS = 24 * 60 * 60
MEMORY_REF_MARKERS = (
    ".claude/agent-memory/",
    ".claude/agents/",
    ".agents/activity.log",
    "docs/audits/",
)


@dataclass
class WorktreeEntry:
    path: str
    head: str | None
    branch_ref: str | None
    detached: bool = False

    @property
    def slug(self) -> str:
        return Path(self.path).name

    @property
    def branch(self) -> str:
        if not self.branch_ref:
            return "(detached HEAD)" if self.detached else "(unknown)"
        prefix = "refs/heads/"
        if self.branch_ref.startswith(prefix):
            return self.branch_ref[len(prefix) :]
        return self.branch_ref


@dataclass
class WorktreeStatus:
    slug: str
    path: str
    branch: str
    head: str | None
    state: str
    age_hours: float | None
    upstream: str
    dirty: bool
    purpose_exists: bool
    purpose: str
    memory_refs: list[str]


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=15,
    )


def parse_porcelain(text: str) -> list[WorktreeEntry]:
    entries: list[WorktreeEntry] = []
    current: dict[str, str | bool] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                entries.append(_entry_from_dict(current))
                current = None
            continue
        if line.startswith("worktree "):
            if current:
                entries.append(_entry_from_dict(current))
            current = {"path": line[len("worktree ") :]}
            continue
        if current is None:
            continue
        if line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current["branch_ref"] = line[len("branch ") :]
        elif line == "detached":
            current["detached"] = True
    if current:
        entries.append(_entry_from_dict(current))
    return entries


def _entry_from_dict(data: dict[str, str | bool]) -> WorktreeEntry:
    return WorktreeEntry(
        path=str(data.get("path", "")),
        head=str(data["head"]) if data.get("head") else None,
        branch_ref=str(data["branch_ref"]) if data.get("branch_ref") else None,
        detached=bool(data.get("detached", False)),
    )


def collect_worktrees(repo: Path) -> list[WorktreeEntry]:
    result = run_git(["worktree", "list", "--porcelain"], repo)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git worktree list failed")
    return parse_porcelain(result.stdout)


def build_status(entry: WorktreeEntry, now: float | None = None) -> WorktreeStatus:
    now = time.time() if now is None else now
    path = Path(entry.path)
    dirty = _is_dirty(path)
    age = _last_commit_age_hours(path, now)
    upstream = _upstream_state(path, entry)
    purpose_exists, purpose = _purpose(path)
    memory_refs = _memory_refs(path)
    state = classify(
        dirty=dirty,
        purpose_exists=purpose_exists,
        age_hours=age,
        upstream=upstream,
    )
    return WorktreeStatus(
        slug=entry.slug,
        path=entry.path,
        branch=entry.branch,
        head=entry.head,
        state=state,
        age_hours=age,
        upstream=upstream,
        dirty=dirty,
        purpose_exists=purpose_exists,
        purpose=purpose,
        memory_refs=memory_refs,
    )


def classify(
    *,
    dirty: bool,
    purpose_exists: bool,
    age_hours: float | None,
    upstream: str,
) -> str:
    if dirty:
        return "IN-FLIGHT"
    old = age_hours is not None and age_hours >= 24
    if upstream == "gone":
        return "READY-TO-REMOVE"
    if purpose_exists and not old and upstream in {"tracking", "ahead-behind"}:
        return "ACTIVE"
    if purpose_exists and old:
        return "STALE"
    if not purpose_exists and old and upstream in {"none", "gone", "detached"}:
        return "ORPHANED"
    if not purpose_exists:
        return "NEEDS-PURPOSE"
    return "ACTIVE"


def _is_dirty(path: Path) -> bool:
    result = run_git(["status", "--short"], path)
    return bool(result.stdout.strip()) if result.returncode == 0 else False


def _last_commit_age_hours(path: Path, now: float) -> float | None:
    result = run_git(["log", "-1", "--format=%ct"], path)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return max(0.0, (now - int(result.stdout.strip())) / 3600)


def _upstream_state(path: Path, entry: WorktreeEntry) -> str:
    if entry.detached or not entry.branch_ref:
        return "detached"
    branch = entry.branch
    upstream = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        path,
    )
    if upstream.returncode != 0:
        return "none"
    track = run_git(
        ["for-each-ref", "--format=%(upstream:track)", f"refs/heads/{branch}"],
        path,
    )
    if "[gone]" in track.stdout:
        return "gone"
    if track.stdout.strip():
        return "ahead-behind"
    return "tracking"


def _purpose(path: Path) -> tuple[bool, str]:
    purpose = path / "_PURPOSE.md"
    if not purpose.exists():
        return False, "-"
    for line in purpose.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip(" -")
        if stripped and stripped not in {"---", "# Purpose"}:
            return True, stripped[:90]
    return True, "(empty _PURPOSE.md)"


def _memory_refs(path: Path) -> list[str]:
    purpose = path / "_PURPOSE.md"
    if not purpose.exists():
        return []
    refs: list[str] = []
    for line in purpose.read_text(encoding="utf-8", errors="replace").splitlines():
        if any(marker in line for marker in MEMORY_REF_MARKERS):
            refs.append(line.strip(" -"))
    return refs


def render_table(statuses: list[WorktreeStatus]) -> str:
    headers = ("SLUG", "STATE", "BRANCH", "AGE_H", "MEM", "PURPOSE")
    rows = [
        (
            s.slug[:30],
            s.state,
            s.branch[:44],
            "-" if s.age_hours is None else f"{s.age_hours:.1f}",
            str(len(s.memory_refs)),
            s.purpose,
        )
        for s in statuses
    ]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*("-" * w for w in widths))]
    lines.extend(fmt.format(*row) for row in rows)
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    parser.add_argument("--provider", help="Filter by provider/branch/slug substring.")
    parser.add_argument(
        "--sweep-orphaned",
        action="store_true",
        help="Print worktree remove commands for ORPHANED entries. Dry-run only.",
    )
    args = parser.parse_args(argv)

    repo = Path.cwd()
    statuses = [build_status(entry) for entry in collect_worktrees(repo)]
    if args.provider:
        needle = args.provider.lower()
        statuses = [
            s
            for s in statuses
            if needle in s.slug.lower() or needle in s.branch.lower() or needle in s.path.lower()
        ]
    statuses.sort(key=lambda s: (s.state, s.slug))

    if args.json:
        print(json.dumps([asdict(status) for status in statuses], indent=2))
    else:
        print(render_table(statuses))

    if args.sweep_orphaned:
        print("\n# Dry-run orphan sweep commands")
        for status in statuses:
            if status.state == "ORPHANED":
                print(f"git worktree remove {status.path}")
        print("# Log any removal in .agents/worktrees.md before running it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
