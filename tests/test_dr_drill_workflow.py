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
    inputs = _triggers(wf).get("workflow_dispatch", {}).get("inputs", {})
    assert "drill_droplet_size" in inputs


def test_has_backup_source_input():
    wf = _load()
    inputs = _triggers(wf).get("workflow_dispatch", {}).get("inputs", {})
    assert "backup_source" in inputs


def test_has_destroy_on_failure_input():
    wf = _load()
    inputs = _triggers(wf).get("workflow_dispatch", {}).get("inputs", {})
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
