from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktree_status.py"
SPEC = importlib.util.spec_from_file_location("worktree_status", SCRIPT)
assert SPEC is not None
worktree_status = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = worktree_status
SPEC.loader.exec_module(worktree_status)


def test_parse_porcelain_branch_and_detached_entries() -> None:
    text = """worktree C:/repo
HEAD abc123
branch refs/heads/main

worktree C:/repo-review
HEAD def456
detached

"""

    entries = worktree_status.parse_porcelain(text)

    assert len(entries) == 2
    assert entries[0].slug == "repo"
    assert entries[0].branch == "main"
    assert entries[1].detached is True
    assert entries[1].branch == "(detached HEAD)"


def test_classify_dirty_overrides_everything() -> None:
    assert (
        worktree_status.classify(
            dirty=True,
            purpose_exists=False,
            age_hours=100,
            upstream="none",
        )
        == "IN-FLIGHT"
    )


def test_classify_orphaned_requires_missing_purpose_old_and_untracked() -> None:
    assert (
        worktree_status.classify(
            dirty=False,
            purpose_exists=False,
            age_hours=25,
            upstream="none",
        )
        == "ORPHANED"
    )
    assert (
        worktree_status.classify(
            dirty=False,
            purpose_exists=False,
            age_hours=1,
            upstream="none",
        )
        == "NEEDS-PURPOSE"
    )


def test_classify_ready_to_remove_when_upstream_gone() -> None:
    assert (
        worktree_status.classify(
            dirty=False,
            purpose_exists=True,
            age_hours=1,
            upstream="gone",
        )
        == "READY-TO-REMOVE"
    )


def test_render_table_includes_state_branch_and_purpose() -> None:
    status = worktree_status.WorktreeStatus(
        slug="wf-demo",
        path="C:/wf-demo",
        branch="codex/demo",
        head="abc123",
        state="ACTIVE",
        age_hours=1.25,
        upstream="tracking",
        dirty=False,
        purpose_exists=True,
        purpose="demo purpose",
        memory_refs=[".claude/agent-memory/navigator/demo.md"],
    )

    table = worktree_status.render_table([status])

    assert "wf-demo" in table
    assert "ACTIVE" in table
    assert "codex/demo" in table
    assert "1" in table
    assert "demo purpose" in table


def test_memory_refs_read_from_purpose_file(tmp_path: Path) -> None:
    (tmp_path / "_PURPOSE.md").write_text(
        "\n".join(
            [
                "Purpose: demo",
                "Memory refs:",
                "- .claude/agent-memory/navigator/demo.md",
                "- .claude/agents/navigator.md",
                "- docs/audits/2026-04-27-navigator-reality-sweep-session-d.md",
                "- .agents/activity.log",
            ]
        ),
        encoding="utf-8",
    )

    assert worktree_status._memory_refs(tmp_path) == [
        ".claude/agent-memory/navigator/demo.md",
        ".claude/agents/navigator.md",
        "docs/audits/2026-04-27-navigator-reality-sweep-session-d.md",
        ".agents/activity.log",
    ]
