"""Structure tests for .github/workflows/uptime-canary.yml."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

_REPO = Path(__file__).resolve().parent.parent
_WORKFLOW = _REPO / ".github" / "workflows" / "uptime-canary.yml"

pytestmark = pytest.mark.skipif(
    not _YAML_AVAILABLE, reason="pyyaml not installed"
)


def _load() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _jobs() -> dict:
    return _load().get("jobs", {})


def _alarm_gate_step() -> dict:
    steps = _jobs()["alarm-sink"]["steps"]
    return next(step for step in steps if step.get("id") == "gate")


def test_probe_runs_after_failed_deploy_workflow_run():
    """Failed deploy-prod runs must still trigger a real endpoint probe."""
    probe = _jobs()["probe"]
    assert "if" not in probe, (
        "Do not skip the Layer-1 probe on failed deploy-prod workflow_run events; "
        "otherwise alarm-sink receives empty outputs and can report a false green."
    )


def test_alarm_sink_fails_closed_when_probe_outputs_are_missing():
    gate = _alarm_gate_step()
    env = gate["env"]
    script = gate["with"]["script"]

    assert env["PROBE_RESULT"] == "${{ needs.probe.result }}"
    assert "const effectiveOverall = overall || 'red';" in script
    assert "Probe job produced no overall output" in script
    assert "if (effectiveOverall === 'red')" in script
