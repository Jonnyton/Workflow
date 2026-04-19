"""Tests for scripts/concerns_resolve.py.

Verifies the proposal-only contract (never edits STATUS.md), parsing,
heuristic matching for commit-hash and design-note-supersession paths,
and the output format. Uses tmp_path fixtures with synthetic STATUS.md
variants so the tests are independent of the live Concerns state.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "concerns_resolve.py"


def _load_module(name: str, path: Path):
    import sys
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so the dataclasses decorator can find the module.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def concerns_resolve():
    return _load_module("concerns_resolve_under_test", SCRIPT_PATH)


# -------------------------------------------------------------------
# _read_concerns_section
# -------------------------------------------------------------------


def test_parses_concern_lines(concerns_resolve):
    status = (
        "# Status\n\n"
        "## Concerns\n\n"
        "- [2026-04-14] First concern.\n"
        "- [2026-04-17] Second concern with `path`.\n"
        "\n---\n"
        "## Work\n"
    )
    concerns = concerns_resolve._read_concerns_section(status)

    assert len(concerns) == 2
    assert concerns[0].date == "2026-04-14"
    assert concerns[0].text == "First concern."
    assert concerns[1].date == "2026-04-17"
    assert concerns[1].text == "Second concern with `path`."


def test_empty_section_returns_empty(concerns_resolve):
    status = "# Status\n\n## Concerns\n\n---\n## Work\n"
    assert concerns_resolve._read_concerns_section(status) == []


def test_missing_section_returns_empty(concerns_resolve):
    status = "# Status\n\n## Work\n- row\n"
    assert concerns_resolve._read_concerns_section(status) == []


def test_prose_lines_ignored(concerns_resolve):
    """Paragraphs between concerns don't confuse the parser."""
    status = (
        "## Concerns\n\n"
        "Some prose here.\n"
        "- [2026-04-18] An actual concern.\n"
        "More prose.\n"
        "---\n"
    )
    concerns = concerns_resolve._read_concerns_section(status)
    assert len(concerns) == 1
    assert concerns[0].date == "2026-04-18"


def test_section_stops_at_next_heading(concerns_resolve):
    """A later `## Heading` ends the concerns block."""
    status = (
        "## Concerns\n"
        "- [2026-04-14] in-section\n"
        "## Work\n"
        "- [2026-04-15] not-in-section\n"
    )
    concerns = concerns_resolve._read_concerns_section(status)
    assert len(concerns) == 1
    assert "in-section" in concerns[0].text


# -------------------------------------------------------------------
# Heuristics
# -------------------------------------------------------------------


def test_commit_hash_matches_resolved(concerns_resolve):
    """A concern mentioning a hash present in the fake log resolves."""
    concern = concerns_resolve.Concern(
        date="2026-04-17",
        text="589e1fb tests needed.",
        raw_line="...",
    )
    commits = [("589e1fb3b1ae5380266f605dc718784dd336d7a2", "fix: something")]
    p = concerns_resolve.evaluate_concern(concern, commits)

    assert p.verdict == "RESOLVED"
    assert "589e1fb3" in p.evidence
    assert "commit-hash-in-log" in p.heuristics_matched


def test_commit_hash_not_in_log_stays_current(concerns_resolve):
    concern = concerns_resolve.Concern(
        date="2026-04-17",
        text="abcdef1 tests needed.",
        raw_line="...",
    )
    commits = [("1111111111111111111111111111111111111111", "other")]
    p = concerns_resolve.evaluate_concern(concern, commits)

    assert p.verdict == "CURRENT"


def test_design_note_nonexistent_path_flags_stale(concerns_resolve, tmp_path):
    """A missing referenced path becomes SUPERSEDED with an advisory."""
    concern = concerns_resolve.Concern(
        date="2026-04-17",
        text="See `docs/design-notes/2099-12-31-nonexistent.md`.",
        raw_line="...",
    )
    p = concerns_resolve.evaluate_concern(concern, [])

    assert p.verdict == "SUPERSEDED"
    assert "does not exist" in p.evidence


def test_fallback_verdict_is_current(concerns_resolve):
    concern = concerns_resolve.Concern(
        date="2026-04-14",
        text="Some vague concern with no structured signal.",
        raw_line="...",
    )
    p = concerns_resolve.evaluate_concern(concern, [])

    assert p.verdict == "CURRENT"
    assert "fallback-current" in p.heuristics_matched


# -------------------------------------------------------------------
# write_proposals format
# -------------------------------------------------------------------


def test_write_proposals_produces_expected_headers(concerns_resolve, tmp_path):
    concern = concerns_resolve.Concern(
        date="2026-04-14", text="A concern.", raw_line="...",
    )
    proposal = concerns_resolve.Proposal(
        concern=concern, verdict="CURRENT",
        evidence="", suggested_action="",
        heuristics_matched=["fallback-current"],
    )
    out = tmp_path / "proposals.md"

    concerns_resolve.write_proposals([proposal], out)

    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Concerns Trim Proposals")
    assert "**Concerns evaluated:** 1" in text
    assert "**Verdicts:** RESOLVED=0, SUPERSEDED=0, CURRENT=1" in text
    assert "## [2026-04-14] A concern." in text


def test_write_proposals_counts_all_verdicts(concerns_resolve, tmp_path):
    proposals = [
        concerns_resolve.Proposal(
            concern=concerns_resolve.Concern(date="d", text="t", raw_line=""),
            verdict=v,
        )
        for v in ["RESOLVED", "RESOLVED", "SUPERSEDED", "CURRENT"]
    ]
    out = tmp_path / "proposals.md"

    concerns_resolve.write_proposals(proposals, out)

    text = out.read_text(encoding="utf-8")
    assert "RESOLVED=2" in text
    assert "SUPERSEDED=1" in text
    assert "CURRENT=1" in text


# -------------------------------------------------------------------
# main() integration — does NOT edit STATUS.md
# -------------------------------------------------------------------


def test_main_does_not_edit_status_md(concerns_resolve, tmp_path):
    """The script's most important contract: never touches STATUS.md."""
    status = tmp_path / "STATUS.md"
    status.write_text(
        "## Concerns\n\n"
        "- [2026-04-14] A concern.\n"
        "- [2026-04-17] Another one.\n"
        "\n---\n",
        encoding="utf-8",
    )
    status_before = status.read_text(encoding="utf-8")
    status_mtime_before = status.stat().st_mtime_ns

    out = tmp_path / "proposals.md"
    rc = concerns_resolve.main(
        ["--status-path", str(status), "--output", str(out), "--no-activity-log"]
    )

    assert rc == 0
    # Never modified.
    assert status.read_text(encoding="utf-8") == status_before
    assert status.stat().st_mtime_ns == status_mtime_before
    # Output file produced.
    assert out.exists()
    assert "A concern." in out.read_text(encoding="utf-8")


def test_main_returns_nonzero_on_missing_status(concerns_resolve, tmp_path, capsys):
    missing = tmp_path / "does_not_exist.md"
    out = tmp_path / "proposals.md"

    rc = concerns_resolve.main(
        ["--status-path", str(missing), "--output", str(out), "--no-activity-log"]
    )

    assert rc == 1


def test_main_returns_nonzero_on_empty_concerns_section(concerns_resolve, tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text("## Concerns\n\n---\n## Work\n", encoding="utf-8")
    out = tmp_path / "proposals.md"

    rc = concerns_resolve.main(
        ["--status-path", str(status), "--output", str(out), "--no-activity-log"]
    )

    assert rc == 1


# -------------------------------------------------------------------
# CLI shell integration (real subprocess)
# -------------------------------------------------------------------


def test_cli_smoke_run_against_tmp_status(tmp_path):
    status = tmp_path / "STATUS.md"
    status.write_text(
        "## Concerns\n\n"
        "- [2026-04-14] Standalone concern.\n"
        "\n---\n",
        encoding="utf-8",
    )
    out = tmp_path / "proposals.md"

    import sys

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH),
         "--status-path", str(status),
         "--output", str(out),
         "--no-activity-log"],
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert "Standalone concern" in out.read_text(encoding="utf-8")
