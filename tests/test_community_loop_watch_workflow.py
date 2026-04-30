"""Tests for .github/workflows/community-loop-watch.yml."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "community-loop-watch.yml"

pytestmark = pytest.mark.skipif(
    not _YAML_AVAILABLE, reason="pyyaml not installed"
)


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps(wf: dict, job: str) -> list[dict]:
    return wf.get("jobs", {}).get(job, {}).get("steps", [])


def test_alarm_sink_can_dispatch_actions():
    wf = _load()
    permissions = wf.get("permissions", {})
    assert permissions.get("actions") == "write", (
        "community-loop-watch needs actions: write to dispatch stale dependency workflows"
    )


def test_alarm_sink_dispatches_stale_dependency_workflows():
    wf = _load()
    step = next(
        (
            s for s in _steps(wf, "alarm-sink")
            if s.get("name") == "Manage community-loop-red issue"
        ),
        None,
    )
    assert step is not None, "alarm-sink must manage the community-loop-red issue"
    script = str(step.get("with", {}).get("script", ""))
    assert "createWorkflowDispatch" in script
    assert "wiki-bug-sync.yml" in script
    assert "uptime-canary.yml" in script
    assert "has not run successfully" in script
