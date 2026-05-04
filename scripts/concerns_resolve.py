"""Mechanical STATUS.md concerns-resolution proposal script.

Parses the `## Concerns` section of STATUS.md and proposes a verdict
for each concern based on cheap heuristics — commit-log matching,
design-note supersession, Work-table cross-reference. Writes proposals
to `output/concerns_trim_proposals.md` for the host or lead to curate.

**Does NOT edit STATUS.md.** Per project convention, STATUS.md Concerns
is host-managed; this script's job is to compute "what the commit log
says is resolved" so an agent or human doesn't have to burn context
re-deriving it.

Usage:

    python scripts/concerns_resolve.py

Exit codes:
    0 — proposals written (even if all CURRENT).
    1 — STATUS.md missing or Concerns section not found.

Heuristics (longest-match first — a concern matched by an earlier
rule isn't re-evaluated):

    1. Commit-hash mention (7-40 hex chars) — if git log --oneline
       contains that hash, propose RESOLVED with evidence.
    2. "tests" / "test coverage" / "need tests" + commit hash in
       recent log — propose RESOLVED if a commit subject matches
       "tests: cover <X>" or similar.
    3. Design-note path reference — verify path exists. If a newer
       design note mentions this one with "supersedes" / "replaces",
       propose SUPERSEDED.
    4. Task-number mention ("#N") — if Work table has no row matching
       that number AND no open task with that id, propose RESOLVED
       (landed). Otherwise CURRENT.
    5. Fallback — CURRENT with a note indicating no heuristic matched.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = REPO_ROOT / "STATUS.md"
PROPOSALS_PATH = REPO_ROOT / "output" / "concerns_trim_proposals.md"
ACTIVITY_LOG = REPO_ROOT / ".agents" / "activity.log"

CONCERN_LINE = re.compile(r"^- \[(?P<date>\d{4}-\d{2}-\d{2})\]\s*(?P<text>.+)$")
COMMIT_HASH = re.compile(r"\b([0-9a-f]{7,40})\b")
DESIGN_NOTE_PATH = re.compile(r"`(docs/design-notes/[^`]+\.md)`")
TASK_REF = re.compile(r"task #(\d+)")


@dataclass
class Concern:
    date: str
    text: str
    raw_line: str


@dataclass
class Proposal:
    concern: Concern
    verdict: str  # "RESOLVED" / "SUPERSEDED" / "CURRENT"
    evidence: str = ""
    suggested_action: str = ""
    heuristics_matched: list[str] = field(default_factory=list)


def _read_concerns_section(status_text: str) -> list[Concern]:
    """Extract concern records from STATUS.md text.

    Concerns live between `## Concerns` and the next `##` or `---`.
    Only `- [DATE] text` lines count; intervening prose is ignored.
    """
    lines = status_text.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip() == "## Concerns"
        )
    except StopIteration:
        return []

    concerns: list[Concern] = []
    for line in lines[start + 1:]:
        if line.startswith("## ") or line.strip() == "---":
            break
        match = CONCERN_LINE.match(line.rstrip())
        if match:
            concerns.append(
                Concern(
                    date=match.group("date"),
                    text=match.group("text"),
                    raw_line=line,
                )
            )
    return concerns


def _git_log_oneline(limit: int = 200) -> list[tuple[str, str]]:
    """Return [(hash, subject), ...] for the last N commits on HEAD."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--pretty=format:%H %s"],
            capture_output=True, text=True, cwd=REPO_ROOT, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    pairs: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            pairs.append((parts[0], parts[1]))
    return pairs


def _check_commit_hash(text: str, commits: list[tuple[str, str]]) -> str | None:
    """If the concern text mentions a commit hash that's in the log,
    return 'HASH SUBJECT' as evidence. None if no match."""
    for match in COMMIT_HASH.finditer(text):
        candidate = match.group(1).lower()
        for full_hash, subject in commits:
            if full_hash.lower().startswith(candidate):
                return f"{full_hash[:8]} {subject}"
    return None


def _check_tests_landed(
    text: str, commits: list[tuple[str, str]],
) -> str | None:
    """Concerns like 'X needs tests' resolve when a subsequent commit
    has subject starting with 'tests:' AND mentions the referenced
    commit hash OR the concern's key symbol."""
    if not re.search(r"\bneed[s]?\s+tests\b|\btest coverage\b", text, re.I):
        return None
    # Pull hashes mentioned in the concern (if any) and check recent
    # test-prefix commits for any of them.
    hashes = [m.group(1).lower() for m in COMMIT_HASH.finditer(text)]
    for full_hash, subject in commits:
        if not subject.lower().startswith("tests:"):
            continue
        # Match if any hash from the concern is referenced in a commit
        # subject OR commit body. Body inspection requires git show.
        for h in hashes:
            try:
                result = subprocess.run(
                    ["git", "show", "-s", "--format=%H%n%s%n%b", full_hash],
                    capture_output=True, text=True, cwd=REPO_ROOT, check=True,
                )
            except subprocess.CalledProcessError:
                continue
            if h in result.stdout.lower():
                return f"{full_hash[:8]} {subject}"
    return None


def _check_design_note_superseded(text: str) -> tuple[str | None, str | None]:
    """Scan each `docs/design-notes/...` path in the concern text.

    Returns (evidence, action) on SUPERSEDED verdict; (None, None) otherwise.
    """
    for match in DESIGN_NOTE_PATH.finditer(text):
        path = REPO_ROOT / match.group(1)
        if not path.exists():
            return (
                f"Referenced note {match.group(1)} does not exist",
                "Verify path is correct or concern is stale",
            )
        # Look for newer notes that mention this one with "supersedes".
        note_name = path.name
        newer_supersede = _find_superseding_note(note_name)
        if newer_supersede:
            return (
                f"{note_name} superseded by {newer_supersede}",
                f"Consider updating concern to reference {newer_supersede}",
            )
    return (None, None)


def _find_superseding_note(original_name: str) -> str | None:
    """Grep other design notes for `supersedes|supersede|replaces <original>`."""
    notes_dir = REPO_ROOT / "docs" / "design-notes"
    if not notes_dir.is_dir():
        return None
    for candidate in sorted(notes_dir.glob("*.md")):
        if candidate.name == original_name:
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Simple keyword scan — not perfect, but the cost of a false
        # positive is a human-curation prompt, not a silent edit.
        if re.search(
            rf"(supersed(es|ed by)|replaces)\s+.*{re.escape(original_name)}",
            text, re.I,
        ):
            return candidate.name
        if re.search(
            rf"{re.escape(original_name)}.*(superseded by|replaced by)",
            text, re.I,
        ):
            return candidate.name
    return None


def _check_task_resolved(text: str) -> tuple[str | None, str | None]:
    """Concern mentions 'task #N'. Return (evidence, action) if the
    task number appears in a recent commit subject (landed)."""
    for match in TASK_REF.finditer(text):
        task_num = match.group(1)
        try:
            result = subprocess.run(
                ["git", "log", "-50", "--pretty=format:%s", f"--grep=#{task_num}"],
                capture_output=True, text=True, cwd=REPO_ROOT, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        for subj in result.stdout.splitlines():
            if subj.strip():
                return (
                    f"Task #{task_num} referenced in commit: {subj.strip()}",
                    f"Verify task #{task_num} actually resolved; may be a "
                    f"partial reference.",
                )
    return (None, None)


def evaluate_concern(
    concern: Concern, commits: list[tuple[str, str]],
) -> Proposal:
    """Apply heuristics in order of confidence. First match wins."""
    p = Proposal(concern=concern, verdict="CURRENT")

    # 1. Commit-hash mention in log.
    evidence = _check_commit_hash(concern.text, commits)
    if evidence:
        p.verdict = "RESOLVED"
        p.evidence = f"Commit mentioned in concern is in log: {evidence}"
        p.suggested_action = (
            "Verify referenced commit actually resolved the concern "
            "(commit presence alone is weak evidence). If yes, delete "
            "this concern line from STATUS.md."
        )
        p.heuristics_matched.append("commit-hash-in-log")
        return p

    # 2. "needs tests" + subsequent tests: commit.
    evidence = _check_tests_landed(concern.text, commits)
    if evidence:
        p.verdict = "RESOLVED"
        p.evidence = f"Tests commit landed referencing concern: {evidence}"
        p.suggested_action = (
            "Verify the test commit actually covers the contract in "
            "question. If yes, delete."
        )
        p.heuristics_matched.append("tests-landed")
        return p

    # 3. Design note superseded.
    sup_evidence, sup_action = _check_design_note_superseded(concern.text)
    if sup_evidence:
        p.verdict = "SUPERSEDED"
        p.evidence = sup_evidence
        p.suggested_action = sup_action or ""
        p.heuristics_matched.append("design-note-superseded")
        return p

    # 4. Task # landed via commit subject grep.
    task_evidence, task_action = _check_task_resolved(concern.text)
    if task_evidence:
        p.verdict = "RESOLVED"
        p.evidence = task_evidence
        p.suggested_action = task_action or ""
        p.heuristics_matched.append("task-ref-in-commit")
        return p

    # 5. Fallback.
    p.evidence = "No automated heuristic matched"
    p.suggested_action = (
        "Manual review needed. Concern remains CURRENT until a "
        "future heuristic pass or manual resolution."
    )
    p.heuristics_matched.append("fallback-current")
    return p


def write_proposals(proposals: list[Proposal], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().astimezone()
    ts = now.strftime("%Y-%m-%dT%H:%M:%S%z")

    counts = {"RESOLVED": 0, "SUPERSEDED": 0, "CURRENT": 0}
    for p in proposals:
        counts[p.verdict] = counts.get(p.verdict, 0) + 1

    lines = [
        "# Concerns Trim Proposals",
        "",
        f"**Generated:** {ts}",
        "**Source:** STATUS.md `## Concerns` section at HEAD",
        f"**Concerns evaluated:** {len(proposals)}",
        f"**Verdicts:** RESOLVED={counts['RESOLVED']}, "
        f"SUPERSEDED={counts['SUPERSEDED']}, CURRENT={counts['CURRENT']}",
        "",
        "This file is machine-generated by `scripts/concerns_resolve.py`. "
        "It proposes — it does not edit STATUS.md. Host or lead curates "
        "based on the proposals below.",
        "",
        "---",
        "",
    ]
    for p in proposals:
        lines.extend([
            f"## [{p.concern.date}] {p.concern.text}",
            "",
            f"- **Verdict:** {p.verdict}",
            f"- **Evidence:** {p.evidence}",
            f"- **Heuristics matched:** {', '.join(p.heuristics_matched)}",
            f"- **Suggested action:** {p.suggested_action}",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def append_activity_log(proposals: list[Proposal]) -> None:
    """Append a single timestamped summary line to .agents/activity.log."""
    if not ACTIVITY_LOG.parent.exists():
        return
    counts = {"RESOLVED": 0, "SUPERSEDED": 0, "CURRENT": 0}
    for p in proposals:
        counts[p.verdict] = counts.get(p.verdict, 0) + 1
    now = dt.datetime.now().astimezone()
    ts = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = (
        f"\n{ts} [concerns_resolve] Evaluated {len(proposals)} concerns: "
        f"RESOLVED={counts['RESOLVED']}, "
        f"SUPERSEDED={counts['SUPERSEDED']}, "
        f"CURRENT={counts['CURRENT']}. "
        f"Proposals at {PROPOSALS_PATH.relative_to(REPO_ROOT)}.\n"
    )
    try:
        with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Propose trim verdicts for STATUS.md Concerns.",
    )
    parser.add_argument(
        "--status-path",
        type=Path,
        default=STATUS_PATH,
        help="Path to STATUS.md (default: repo STATUS.md).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROPOSALS_PATH,
        help="Where to write proposals (default: output/concerns_trim_proposals.md).",
    )
    parser.add_argument(
        "--no-activity-log",
        action="store_true",
        help="Skip appending a summary line to .agents/activity.log.",
    )
    args = parser.parse_args(argv)

    if not args.status_path.exists():
        print(f"ERROR: {args.status_path} not found", file=sys.stderr)
        return 1

    status_text = args.status_path.read_text(encoding="utf-8")
    concerns = _read_concerns_section(status_text)
    if not concerns:
        print(
            f"No concerns found under `## Concerns` in {args.status_path}",
            file=sys.stderr,
        )
        return 1

    commits = _git_log_oneline(limit=200)
    proposals = [evaluate_concern(c, commits) for c in concerns]
    write_proposals(proposals, args.output)
    if not args.no_activity_log:
        append_activity_log(proposals)

    try:
        display_path = args.output.relative_to(REPO_ROOT)
    except ValueError:
        display_path = args.output
    print(f"Wrote {len(proposals)} proposal(s) to {display_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
