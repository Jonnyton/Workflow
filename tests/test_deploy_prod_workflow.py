"""Tests for .github/workflows/deploy-prod.yml structure and DO secret names.

Covers:
  (a) YAML parses without error
  (b) workflow_dispatch trigger is present (manual test-deploy path)
  (c) workflow_run trigger fires on build-image success
  (d) Required DO secret names referenced (not legacy Hetzner names)
  (e) SSH key file and known_hosts use DO_DROPLET_HOST variable
  (f) Post-deploy canary step present
  (g) Rollback step present and conditioned on failure
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
_WORKFLOW = _REPO / ".github" / "workflows" / "deploy-prod.yml"

pytestmark = pytest.mark.skipif(
    not _YAML_AVAILABLE, reason="pyyaml not installed"
)


def _load() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _triggers(wf: dict) -> dict:
    return wf.get(True, {}) or {}


# ---------------------------------------------------------------------------
# (a) YAML parses
# ---------------------------------------------------------------------------


def test_deploy_prod_yml_parses():
    _load()


# ---------------------------------------------------------------------------
# (b) workflow_dispatch present (manual deploy path)
# ---------------------------------------------------------------------------


def test_has_workflow_dispatch_trigger():
    wf = _load()
    triggers = _triggers(wf)
    assert "workflow_dispatch" in triggers, (
        "deploy-prod must have workflow_dispatch for manual invocation"
    )


def test_workflow_dispatch_has_image_tag_input():
    wf = _load()
    triggers = _triggers(wf)
    dispatch = triggers.get("workflow_dispatch") or {}
    inputs = (dispatch.get("inputs") or {})
    assert "image_tag" in inputs, "workflow_dispatch must expose image_tag input"


# ---------------------------------------------------------------------------
# (c) workflow_run trigger fires on build-image success
# ---------------------------------------------------------------------------


def test_has_workflow_run_trigger():
    wf = _load()
    triggers = _triggers(wf)
    assert "workflow_run" in triggers


def test_workflow_run_fires_on_build_image():
    wf = _load()
    triggers = _triggers(wf)
    wr = triggers.get("workflow_run") or {}
    workflows = wr.get("workflows", [])
    assert any("Build" in w for w in workflows), \
        "workflow_run must reference the build-image workflow"


# ---------------------------------------------------------------------------
# (d) DO secret names — not legacy Hetzner names
# ---------------------------------------------------------------------------


def test_do_droplet_host_secret_referenced():
    assert "DO_DROPLET_HOST" in _text()


def test_do_ssh_user_secret_referenced():
    assert "DO_SSH_USER" in _text()


def test_do_ssh_key_secret_referenced():
    assert "DO_SSH_KEY" in _text()


def test_no_legacy_hetzner_secrets():
    text = _text()
    assert "HETZNER_HOST" not in text, "Legacy HETZNER_HOST still in deploy-prod.yml"
    assert "HETZNER_SSH_USER" not in text, "Legacy HETZNER_SSH_USER still in deploy-prod.yml"
    assert "HETZNER_SSH_KEY" not in text, "Legacy HETZNER_SSH_KEY still in deploy-prod.yml"


# ---------------------------------------------------------------------------
# (e) SSH step uses DO_DROPLET_HOST
# ---------------------------------------------------------------------------


def test_ssh_keyscan_uses_do_droplet_host():
    assert "DO_DROPLET_HOST" in _text()
    assert "hetzner_deploy" not in _text(), "Stale hetzner_deploy key filename still in workflow"


# ---------------------------------------------------------------------------
# (f) Post-deploy canary step present
# ---------------------------------------------------------------------------


def _steps(wf: dict) -> list[dict]:
    return wf.get("jobs", {}).get("deploy", {}).get("steps", [])


def test_post_deploy_canary_step_present():
    wf = _load()
    names = [s.get("name", "") for s in _steps(wf)]
    assert any("canary" in (n or "").lower() for n in names), \
        "deploy job must have a post-deploy canary step"


# ---------------------------------------------------------------------------
# (g) Rollback step present and conditioned on failure
# ---------------------------------------------------------------------------


def test_rollback_step_present():
    wf = _load()
    names = [s.get("name", "") for s in _steps(wf)]
    assert any("rollback on failure" in (n or "").lower() for n in names), \
        "deploy job must have a 'Rollback on failure' step"


def test_rollback_conditioned_on_failure():
    wf = _load()
    for step in _steps(wf):
        if "rollback on failure" in (step.get("name") or "").lower():
            cond = step.get("if", "")
            assert "failure" in cond, "rollback step must be conditioned on failure()"
            return
    pytest.fail("'Rollback on failure' step not found")
