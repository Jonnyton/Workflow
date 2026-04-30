"""Tests for .github/workflows/auto-fix-bug.yml structure.

Static YAML-parse tests - no GHA runner needed. Validates the key
invariants: auth paths, disable toggle, graceful-skip, branch naming,
permissions, concurrency group, trigger condition.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "auto-fix-bug.yml"


@pytest.fixture(scope="module")
def wf() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------


def test_triggers_on_issues_labeled(wf):
    # PyYAML parses bare `on:` as boolean True key.
    triggers = wf.get(True, wf.get("on", {}))
    assert "issues" in triggers, "Workflow must trigger on issues"
    assert "labeled" in triggers["issues"].get("types", []), (
        "Workflow must trigger on issues.labeled"
    )


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_has_contents_write(wf):
    perms = wf.get("permissions", {})
    assert perms.get("contents") == "write", "contents: write needed to push branch"


def test_has_issues_write(wf):
    perms = wf.get("permissions", {})
    assert perms.get("issues") == "write", "issues: write needed to add labels + comments"


def test_has_pull_requests_write(wf):
    perms = wf.get("permissions", {})
    assert perms.get("pull-requests") == "write", "pull-requests: write needed to open PRs"


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_concurrency_scoped_to_issue(wf):
    conc = wf["jobs"]["fix"].get("concurrency", {})
    group = conc.get("group", "")
    assert "matrix.issue.issue_number" in group, (
        "Concurrency group must be scoped per-issue to prevent parallel fix attempts"
    )


# ---------------------------------------------------------------------------
# Job filter
# ---------------------------------------------------------------------------


def test_job_filters_on_auto_bug_label(wf):
    discover_step = wf["jobs"]["discover"]["steps"][0]
    script = str(discover_step.get("with", {}).get("script", ""))
    assert "auto-bug" in script, (
        "Discover step must include the legacy 'auto-bug' label for compatibility"
    )


# ---------------------------------------------------------------------------
# Disable toggle
# ---------------------------------------------------------------------------


def test_disable_flag_checked(wf):
    steps = wf["jobs"]["fix"]["steps"]
    check_step = next(
        (s for s in steps if s.get("id") == "check-disabled"), None
    )
    assert check_step is not None, "Must have a check-disabled step"
    run_script = check_step.get("run", "")
    assert "AUTO_FIX_DISABLED" in run_script, (
        "check-disabled step must reference AUTO_FIX_DISABLED variable"
    )


def test_needs_human_label_on_disabled(wf):
    steps = wf["jobs"]["fix"]["steps"]
    disabled_step = next(
        (s for s in steps
         if "disabled" in str(s.get("if", "")) and "needs-human" in str(s)),
        None,
    )
    assert disabled_step is not None, (
        "Must add needs-human label when AUTO_FIX_DISABLED=true"
    )


# ---------------------------------------------------------------------------
# Auth detection
# ---------------------------------------------------------------------------


def test_auth_step_exists(wf):
    steps = wf["jobs"]["fix"]["steps"]
    auth_step = next((s for s in steps if s.get("id") == "auth"), None)
    assert auth_step is not None, "Must have an auth detection step"


def test_auth_step_checks_oauth_token(wf):
    steps = wf["jobs"]["fix"]["steps"]
    auth_step = next(s for s in steps if s.get("id") == "auth")
    run_script = auth_step.get("run", "")
    assert "CLAUDE_CODE_OAUTH_TOKEN" in run_script, (
        "Auth step must check CLAUDE_CODE_OAUTH_TOKEN first"
    )


def test_auth_step_checks_api_key_fallback(wf):
    steps = wf["jobs"]["fix"]["steps"]
    auth_step = next(s for s in steps if s.get("id") == "auth")
    run_script = auth_step.get("run", "")
    assert "ANTHROPIC_API_KEY" in run_script, (
        "Auth step must check ANTHROPIC_API_KEY as fallback"
    )


# ---------------------------------------------------------------------------
# Graceful-skip (no auth)
# ---------------------------------------------------------------------------


def test_graceful_skip_step_exists(wf):
    steps = wf["jobs"]["fix"]["steps"]
    skip_step = next(
        (s for s in steps
         if "mode" in str(s.get("if", "")) and "none" in str(s.get("if", ""))),
        None,
    )
    assert skip_step is not None, (
        "Must have a graceful-skip step when auth mode == none"
    )


def test_graceful_skip_adds_needs_human(wf):
    steps = wf["jobs"]["fix"]["steps"]
    skip_step = next(
        (s for s in steps
         if "mode" in str(s.get("if", "")) and "none" in str(s.get("if", ""))),
        None,
    )
    assert skip_step is not None
    script = str(skip_step.get("with", {}).get("script", ""))
    assert "needs-human" in script, (
        "Graceful-skip step must add needs-human label"
    )


# ---------------------------------------------------------------------------
# Claude action steps
# ---------------------------------------------------------------------------


def test_oauth_step_uses_claude_code_action(wf):
    steps = wf["jobs"]["fix"]["steps"]
    oauth_step = next(
        (s for s in steps if "oauth" in str(s.get("if", "")) and "uses" in s),
        None,
    )
    assert oauth_step is not None, "Must have an OAuth-authenticated Claude action step"
    assert "claude-code-action" in oauth_step.get("uses", ""), (
        "OAuth step must use anthropics/claude-code-action"
    )


def test_no_api_key_step_uses_claude_code_action(wf):
    steps = wf["jobs"]["fix"]["steps"]
    api_step = next(
        (s for s in steps if "api_key" in str(s.get("if", "")) and "uses" in s),
        None,
    )
    assert api_step is None, (
        "Default daemon writers must not use API-key-authenticated Claude action steps"
    )


def test_branch_naming_convention(wf):
    steps = wf["jobs"]["fix"]["steps"]
    oauth_step = next((s for s in steps if s.get("id") == "claude-oauth"), None)
    assert oauth_step is not None, "Must have a Claude OAuth step"
    with_block = oauth_step.get("with", {})
    assert with_block.get("branch_prefix") == "auto-change/"
    assert "issue-${{ steps.meta.outputs.issue_number }}" == with_block.get(
        "branch_name_template"
    ), (
        "Branch must follow auto-change/issue-<N> naming convention"
    )


def test_pr_title_includes_auto_fix_prefix(wf):
    steps = wf["jobs"]["fix"]["steps"]
    meta_step = next((s for s in steps if s.get("id") == "meta"), None)
    assert meta_step is not None
    script = str(meta_step.get("with", {}).get("script", ""))
    assert "[auto-change]" in script, "PR title must start with [auto-change]"


def test_pr_body_references_fixes_keyword(wf):
    steps = wf["jobs"]["fix"]["steps"]
    oauth_step = next((s for s in steps if s.get("id") == "claude-oauth"), None)
    assert oauth_step is not None, "Must have a Claude OAuth step"
    prompt = str(oauth_step.get("with", {}).get("prompt", ""))
    assert "Fixes #${{ steps.meta.outputs.issue_number }}" in prompt, (
        "Claude prompt must require PR body to reference the issue with Fixes #N"
    )
