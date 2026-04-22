"""Tests for the ENV-UNREADABLE marker plumbing.

Navigator 2026-04-22 §a/§b fix: the entrypoint and the systemd
ExecStartPre + deploy-prod sed-assertions all emit the same canonical
token so p0-outage-triage.yml can grep journalctl and self-repair
the /etc/workflow/env perm-regression class without an SSH shell.

This test file exercises:
  - docker-entrypoint.sh's ENV-UNREADABLE detection path (all sentinels empty).
  - docker-entrypoint.sh's happy path (at least one sentinel non-empty).
  - That the marker token matches across deploy-prod, entrypoint, systemd unit,
    and p0-outage-triage so auto-triage's grep stays aligned.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_ENTRYPOINT = _REPO / "deploy" / "docker-entrypoint.sh"
_SYSTEMD_UNIT = _REPO / "deploy" / "workflow-daemon.service"
_DEPLOY_YAML = _REPO / ".github" / "workflows" / "deploy-prod.yml"
_TRIAGE_YAML = _REPO / ".github" / "workflows" / "p0-outage-triage.yml"

CANONICAL_MARKER = "ENV-UNREADABLE"


def _have_bash() -> bool:
    return shutil.which("bash") is not None


# ---- entrypoint behavior --------------------------------------------------


def _run_entrypoint_via_stdin(
    *,
    exec_replacement: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run docker-entrypoint.sh with a harnessed exec line, fed via stdin.

    Avoids Windows path-translation issues — bash reads the script from
    stdin so no cross-OS argv path munging is needed. Git Bash on Windows
    does not reliably forward freshly-added env vars from Python's
    subprocess env= dict, so we prepend the env assignments directly into
    the piped script body. Also clear the sentinels in-script in case the
    parent shell inherited them.
    """
    script = _ENTRYPOINT.read_text(encoding="utf-8").replace(
        'exec "$@"', exec_replacement,
    )
    preamble_lines = [
        # Clear sentinels first so ambient-shell values don't leak through.
        "unset CLOUDFLARE_TUNNEL_TOKEN SUPABASE_DB_URL WORKFLOW_IMAGE",
    ]
    for key, value in (extra_env or {}).items():
        preamble_lines.append(f"export {key}={value!r}")
    combined = "\n".join(preamble_lines) + "\n" + script
    # Pass bytes to avoid Windows cp1252 encode errors on Unicode chars
    # (e.g. the → in our own comments).
    result = subprocess.run(
        ["bash", "-s", "--", "/bin/true"],
        input=combined.encode("utf-8"),
        capture_output=True,
        timeout=15,
    )
    return subprocess.CompletedProcess(
        args=result.args,
        returncode=result.returncode,
        stdout=result.stdout.decode("utf-8", "replace"),
        stderr=result.stderr.decode("utf-8", "replace"),
    )


@pytest.mark.skipif(not _have_bash(), reason="bash not on PATH")
def test_entrypoint_exits_with_marker_when_all_sentinels_empty():
    """All sentinels unset -> entrypoint emits ENV-UNREADABLE + exit 1."""
    result = _run_entrypoint_via_stdin(
        exec_replacement='echo "[harness] would-exec: $@"',
    )
    assert result.returncode == 1, (
        f"expected exit 1; got {result.returncode}. stderr={result.stderr!r}"
    )
    assert CANONICAL_MARKER in result.stderr, (
        f"canonical marker missing from stderr: {result.stderr!r}"
    )
    # Should name the sentinel env vars so the operator can see what was expected.
    assert "CLOUDFLARE_TUNNEL_TOKEN" in result.stderr
    assert "WORKFLOW_IMAGE" in result.stderr


@pytest.mark.skipif(not _have_bash(), reason="bash not on PATH")
def test_entrypoint_passes_through_when_one_sentinel_set():
    """At least one sentinel non-empty -> entrypoint proceeds past the check."""
    result = _run_entrypoint_via_stdin(
        exec_replacement='echo "[harness] would-exec: $@"',
        extra_env={"WORKFLOW_IMAGE": "ghcr.io/jonnyton/workflow-daemon:abc123"},
    )
    assert result.returncode == 0, (
        f"expected happy-path exit 0; got {result.returncode}. "
        f"stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    assert CANONICAL_MARKER not in result.stderr, (
        "marker should NOT fire when a sentinel is set"
    )
    assert "would-exec" in result.stdout


@pytest.mark.skipif(not _have_bash(), reason="bash not on PATH")
def test_entrypoint_marker_goes_to_stderr_not_stdout():
    """journalctl captures both streams, but the marker belongs on stderr."""
    result = _run_entrypoint_via_stdin(
        exec_replacement='echo "would-exec"',
    )
    # Marker on stderr only.
    assert CANONICAL_MARKER in result.stderr
    assert CANONICAL_MARKER not in result.stdout


# ---- marker alignment across surfaces -------------------------------------


def test_systemd_unit_execstartpre_emits_canonical_marker():
    text = _SYSTEMD_UNIT.read_text(encoding="utf-8")
    assert "ExecStartPre=" in text, "ExecStartPre directive missing"
    assert CANONICAL_MARKER in text, (
        "systemd unit ExecStartPre must emit canonical ENV-UNREADABLE marker"
    )


def test_deploy_prod_yaml_sed_sites_emit_canonical_marker():
    text = _DEPLOY_YAML.read_text(encoding="utf-8")
    # The canonical marker must be present in the failure paths of all three
    # sed sites (scrub one-liner, deploy heredoc, rollback heredoc) plus the
    # standalone assertion step.
    occurrences = text.count(CANONICAL_MARKER)
    # Expect at least 4: scrub + deploy heredoc + standalone assertion + rollback.
    # (Comment mentions may add more; that's fine. Just guard the floor.)
    assert occurrences >= 4, (
        f"expected ≥4 canonical marker occurrences in deploy-prod.yml; "
        f"got {occurrences}. Check that each sed site emits it on regression."
    )


def test_triage_yaml_greps_for_canonical_marker():
    text = _TRIAGE_YAML.read_text(encoding="utf-8")
    # The auto-repair step must grep for the exact token.
    single = f"grep -q '{CANONICAL_MARKER}'"
    double = f'grep -q "{CANONICAL_MARKER}"'
    assert single in text or double in text, (
        "p0-outage-triage must grep for the canonical ENV-UNREADABLE token "
        "so auto-repair fires on the 2026-04-21 class"
    )


def test_triage_auto_repair_runs_chown_chmod():
    text = _TRIAGE_YAML.read_text(encoding="utf-8")
    # The auto-repair must apply the exact mitigation.
    assert "chown root:workflow /etc/workflow/env" in text
    assert "chmod 640 /etc/workflow/env" in text


def test_triage_auto_repair_is_gated_on_marker():
    """The repair must only run inside a conditional branch that checked for
    the marker -- otherwise we're applying mitigations blindly on every triage.
    """
    text = _TRIAGE_YAML.read_text(encoding="utf-8")
    # Find the auto-repair step block and confirm it's wrapped in the grep
    # conditional. Simple structural check: the chown line appears only
    # within the `if echo ... | grep` block.
    lines = text.splitlines()
    in_grep_block = False
    chown_seen_outside_block = False
    for line in lines:
        if "grep -q 'ENV-UNREADABLE'" in line or 'grep -q "ENV-UNREADABLE"' in line:
            in_grep_block = True
            continue
        if in_grep_block and line.strip().startswith("else"):
            in_grep_block = False
            continue
        if in_grep_block and line.strip().startswith("fi"):
            in_grep_block = False
            continue
        if "chown root:workflow /etc/workflow/env" in line and not in_grep_block:
            chown_seen_outside_block = True
    assert not chown_seen_outside_block, (
        "chown must only run inside the ENV-UNREADABLE grep conditional"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
