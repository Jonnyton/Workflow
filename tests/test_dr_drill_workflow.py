"""Tests for .github/workflows/dr-drill.yml structure.

Covers:
  (a) YAML parses without error
  (b) Only workflow_dispatch trigger (never auto-runs)
  (c) Required inputs present (drill_droplet_size, backup_source, destroy_on_failure)
  (d) Required secrets referenced (DIGITALOCEAN_TOKEN, DO_SSH_KEY, DO_DROPLET_HOST, DO_SSH_USER)
  (e) Droplet provision step creates Droplet via DO API
  (f) Bootstrap step runs hetzner-bootstrap.sh
  (g) Restore step runs backup-restore.sh
  (h) Probe uses direct Droplet IP:8001 (not tunnel URL)
  (i) Pass path destroys Droplet + appends to log
  (j) Fail path opens dr-failed issue + leaves Droplet up
  (k) Runbook and log files exist
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

_REPO = Path(__file__).resolve().parent.parent
_WORKFLOW = _REPO / ".github" / "workflows" / "dr-drill.yml"
_RUNBOOK = _REPO / "docs" / "ops" / "dr-drill-runbook.md"
_LOG = _REPO / "docs" / "ops" / "dr-drill-log.md"

pytestmark = pytest.mark.skipif(
    not _YAML_AVAILABLE, reason="pyyaml not installed"
)


def _load() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _triggers(wf: dict) -> dict:
    return wf.get(True, {}) or {}


def _steps(wf: dict) -> list[dict]:
    return wf.get("jobs", {}).get("drill", {}).get("steps", [])


def _step_names(wf: dict) -> list[str]:
    return [(s.get("name") or "").lower() for s in _steps(wf)]


def _dispatch_inputs(wf: dict) -> dict:
    return _triggers(wf).get("workflow_dispatch", {}).get("inputs", {})


def _workflow_input_default(input_name: str) -> str:
    inputs = _dispatch_inputs(_load())
    assert input_name in inputs, f"{input_name} input missing"
    return str(inputs[input_name].get("default", ""))


def _runbook_input_default(input_name: str) -> str:
    text = _RUNBOOK.read_text(encoding="utf-8")
    pattern = rf"\| `{re.escape(input_name)}` \| `([^`]+)` \|"
    match = re.search(pattern, text)
    assert match, f"{input_name} default missing from DR runbook inputs table"
    return match.group(1)


def _bootstrap_step_run() -> str:
    for step in _steps(_load()):
        if step.get("name") == "Bootstrap drill Droplet":
            return step.get("run", "")
    raise AssertionError("Bootstrap drill Droplet step missing")


# ---------------------------------------------------------------------------
# (a) YAML parses
# ---------------------------------------------------------------------------

def test_dr_drill_yml_parses():
    _load()


# ---------------------------------------------------------------------------
# (b) Only workflow_dispatch trigger
# ---------------------------------------------------------------------------

def test_only_workflow_dispatch_trigger():
    wf = _load()
    triggers = _triggers(wf)
    assert "workflow_dispatch" in triggers, "must have workflow_dispatch trigger"
    assert "schedule" not in triggers, "dr-drill must NEVER auto-run on schedule"
    assert "push" not in triggers, "dr-drill must not run on push"
    assert "pull_request" not in triggers, "dr-drill must not run on PR"


# ---------------------------------------------------------------------------
# (c) Required inputs
# ---------------------------------------------------------------------------

def test_has_drill_droplet_size_input():
    wf = _load()
    inputs = _dispatch_inputs(wf)
    assert "drill_droplet_size" in inputs


def test_has_backup_source_input():
    wf = _load()
    inputs = _dispatch_inputs(wf)
    assert "backup_source" in inputs


def test_has_destroy_on_failure_input():
    wf = _load()
    inputs = _dispatch_inputs(wf)
    assert "destroy_on_failure" in inputs


# ---------------------------------------------------------------------------
# (d) Required secrets
# ---------------------------------------------------------------------------

def test_digitalocean_token_referenced():
    assert "DIGITALOCEAN_TOKEN" in _text()


def test_do_ssh_key_referenced():
    assert "DO_SSH_KEY" in _text()


def test_do_droplet_host_referenced():
    assert "DO_DROPLET_HOST" in _text()


def test_do_ssh_user_referenced():
    assert "DO_SSH_USER" in _text()


# ---------------------------------------------------------------------------
# (e) Droplet provision via DO API
# ---------------------------------------------------------------------------

def test_provisions_droplet_via_do_api():
    text = _text()
    assert "digitalocean.com/v2/droplets" in text, (
        "workflow must create a Droplet via DO API"
    )


def test_provision_step_present():
    names = _step_names(_load())
    assert any("provision" in n or "droplet" in n for n in names), (
        "must have a provision/droplet creation step"
    )


# ---------------------------------------------------------------------------
# (f) Bootstrap runs hetzner-bootstrap.sh
# ---------------------------------------------------------------------------

def test_bootstrap_step_runs_bootstrap_sh():
    text = _text()
    assert "hetzner-bootstrap.sh" in text or "bootstrap.sh" in text


def test_bootstrap_step_present():
    names = _step_names(_load())
    assert any("bootstrap" in n for n in names)


# ---------------------------------------------------------------------------
# (g) Restore step runs backup-restore.sh
# ---------------------------------------------------------------------------

def test_restore_step_present():
    names = _step_names(_load())
    assert any("restore" in n for n in names)


def test_restore_uses_backup_restore_sh():
    assert "backup-restore.sh" in _text()


# ---------------------------------------------------------------------------
# (h) Probe uses direct IP:8001 (not tunnel URL)
# ---------------------------------------------------------------------------

def test_probe_uses_direct_ip_not_tunnel():
    text = _text()
    assert "8001" in text, "probe must target port 8001 directly on drill Droplet"
    # Must NOT probe tinyassets.io (that goes through the tunnel the drill lacks).
    # The probe URL should use the drill IP variable, not the canonical URL.
    assert "mcp_probe.py" in text or "mcp_public_canary.py" in text


def test_probe_step_present():
    names = _step_names(_load())
    assert any("probe" in n for n in names)


# ---------------------------------------------------------------------------
# (i) Pass path destroys Droplet + appends to log
# ---------------------------------------------------------------------------

def test_pass_path_destroys_droplet():
    text = _text()
    assert "digitalocean.com/v2/droplets/${DROPLET_ID}" in text or \
           "droplets/${DROPLET_ID}" in text, (
        "pass path must destroy drill Droplet via DO API DELETE"
    )


def test_pass_path_appends_to_log():
    text = _text()
    assert "dr-drill-log.md" in text


# ---------------------------------------------------------------------------
# (j) Fail path opens dr-failed issue + leaves Droplet up
# ---------------------------------------------------------------------------

def test_fail_path_opens_dr_failed_issue():
    assert "dr-failed" in _text()


def test_fail_path_leaves_droplet_up_by_default():
    """By default (destroy_on_failure=false), fail path must NOT destroy."""
    text = _text()
    # The destroy-on-failure step must be conditional on the input being true.
    assert "destroy_on_failure" in text
    assert "'true'" in text or '"true"' in text


# ---------------------------------------------------------------------------
# (k) Runbook and log files exist
# ---------------------------------------------------------------------------

def test_dr_drill_runbook_exists():
    assert _RUNBOOK.exists(), f"Missing: {_RUNBOOK}"


def test_dr_drill_log_exists():
    assert _LOG.exists(), f"Missing: {_LOG}"


def test_dr_drill_runbook_mentions_quarterly():
    assert "quarterly" in _RUNBOOK.read_text(encoding="utf-8").lower()


def test_dr_drill_runbook_mentions_pass_fail():
    text = _RUNBOOK.read_text(encoding="utf-8").lower()
    assert "pass" in text and "fail" in text


def test_dr_drill_runbook_size_default_matches_workflow():
    assert _runbook_input_default("drill_droplet_size") == (
        _workflow_input_default("drill_droplet_size")
    )


def test_dr_drill_runbook_mentions_ssh_port_forward_probe():
    text = _RUNBOOK.read_text(encoding="utf-8").lower()
    assert "ssh port-forward" in text
    assert "localhost:8001" in text


# ---------------------------------------------------------------------------
# Task #66 — pipefail fix + size bump + mid-job cleanup
# ---------------------------------------------------------------------------

def test_bootstrap_step_uses_pipefail():
    """Bootstrap pipe to tee must not swallow exit code — pipefail required."""
    text = _text()
    assert "pipefail" in text, (
        "Bootstrap step must use set -euo pipefail so SSH exit code propagates through tee"
    )


def test_bootstrap_step_does_not_pipe_ssh_to_tee():
    """2026-04-22 Task #66 follow-up: the `ssh ... | tee` pattern itself
    swallowed the bootstrap exit code on two drill runs because a following
    `tail` command always exits 0 and masked the pipeline result. Fix is
    to redirect to a file, capture $?, surface last lines, then propagate.
    """
    run = _bootstrap_step_run()
    assert "| tee /tmp/bootstrap.log" not in run, (
        "ssh | tee bootstrap.log is the anti-pattern — replace with "
        "redirect + explicit exit-code capture"
    )


def test_bootstrap_step_captures_exit_code_explicitly():
    run = _bootstrap_step_run()
    assert "bootstrap_code=$?" in run, (
        "bootstrap step must capture ssh exit code into a variable"
    )
    assert ('exit "${bootstrap_code}"' in run
            or "exit ${bootstrap_code}" in run), (
        "captured bootstrap exit code must be propagated so a failed "
        "bootstrap fails the step"
    )


def test_bootstrap_step_redirects_instead_of_piping():
    run = _bootstrap_step_run()
    assert ">/tmp/bootstrap.log" in run or "> /tmp/bootstrap.log" in run, (
        "bootstrap output must be captured via redirect, not pipe"
    )


def test_bootstrap_step_surfaces_tail_before_exit():
    """The last-50-lines dump must run before the exit so operators see
    what failed, even on a red drill run."""
    run = _bootstrap_step_run()
    tail_idx = run.find("tail -50 /tmp/bootstrap.log")
    assert tail_idx >= 0, "tail of bootstrap.log must be surfaced"
    after = run[tail_idx:]
    assert ('if [ "${bootstrap_code}" -ne 0 ]' in after
            or "if [ ${bootstrap_code} -ne 0 ]" in after), (
        "exit-on-failure check must come AFTER tail so the operator "
        "sees the log before the step aborts"
    )


def test_default_drill_size_is_not_1gb():
    """s-1vcpu-1gb OOMs on apt+docker install; default must be at least 2GB."""
    wf = _load()
    inputs = _dispatch_inputs(wf)
    default_size = inputs.get("drill_droplet_size", {}).get("default", "")
    assert default_size != "s-1vcpu-1gb", (
        f"Default size {default_size!r} is known to OOM; bump to s-2vcpu-2gb or larger"
    )
    assert "2vcpu" in default_size or "2gb" in default_size.lower() or \
           default_size >= "s-2", (
        f"Default size {default_size!r} appears smaller than recommended minimum"
    )


def test_mid_job_cleanup_step_exists():
    """A cleanup step must fire even when bootstrap/restore fail (before probe runs)."""
    names = _step_names(_load())
    assert any("cleanup" in n or "mid-job" in n for n in names), (
        "Must have a cleanup step that fires on mid-job failure (before probe color is set)"
    )


def test_mid_job_cleanup_fires_on_always():
    """Cleanup step must have if: always() so it fires even when prior steps fail."""
    steps = _steps(_load())
    cleanup_steps = [s for s in steps
                     if "cleanup" in (s.get("name") or "").lower()
                     or "mid-job" in (s.get("name") or "").lower()]
    assert cleanup_steps, "no cleanup step found"
    for s in cleanup_steps:
        cond = s.get("if", "")
        assert "always()" in str(cond).lower(), (
            f"Cleanup step '{s.get('name')}' must have if: always(), got: {cond!r}"
        )


def test_mid_job_cleanup_checks_probe_color_empty():
    """Cleanup fires only when probe color is unset (mid-job fail, not normal paths)."""
    text = _text()
    # Must guard on drillprobe.outputs.color == '' to avoid double-destroy.
    assert "drillprobe.outputs.color" in text and "''" in text, (
        "Mid-job cleanup must check that drillprobe.outputs.color is empty"
    )
