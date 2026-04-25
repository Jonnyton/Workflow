"""Tests for workflow/bug_investigation.py — Task #33 Phase 1 skeleton."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch


def _reload_module(goal_id: str):
    """Reload bug_investigation with a patched env var so the module-level
    constant re-evaluates.
    """
    with patch.dict("os.environ", {"WORKFLOW_BUG_INVESTIGATION_GOAL_ID": goal_id}):
        if "workflow.bug_investigation" in sys.modules:
            del sys.modules["workflow.bug_investigation"]
        mod = importlib.import_module("workflow.bug_investigation")
    return mod


class TestIsAutoTriggerEnabled:
    def test_disabled_when_env_unset(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("WORKFLOW_BUG_INVESTIGATION_GOAL_ID", None)
            # Reimport to pick up missing env
            mod = _reload_module("")
            assert mod.is_auto_trigger_enabled() is False

    def test_enabled_when_env_set(self):
        mod = _reload_module("goal-abc-123")
        assert mod.is_auto_trigger_enabled() is True

    def test_disabled_when_env_empty_string(self):
        mod = _reload_module("")
        assert mod.is_auto_trigger_enabled() is False


class TestBuildRunPayload:
    def _call(self, frontmatter: dict) -> dict:
        mod = _reload_module("")
        return mod.build_run_payload(frontmatter)

    def test_extracts_all_expected_keys(self):
        fm = {
            "bug_id": "BUG-042",
            "title": "Widget explodes",
            "component": "widget",
            "severity": "critical",
            "kind": "bug",
            "observed": "boom",
            "expected": "no boom",
            "repro": "click widget",
            "workaround": "don't click",
        }
        payload = self._call(fm)
        assert payload == fm

    def test_missing_keys_default_to_empty_string(self):
        payload = self._call({"bug_id": "BUG-001", "title": "Oops"})
        for key in ("component", "severity", "kind", "observed", "expected",
                    "repro", "workaround"):
            assert payload[key] == "", f"expected empty string for missing {key!r}"

    def test_extra_keys_are_excluded(self):
        fm = {
            "bug_id": "BUG-002",
            "title": "X",
            "reporter": "alice",   # extra key
            "filed_at": "2026-04-24",  # extra key
        }
        payload = self._call(fm)
        assert "reporter" not in payload
        assert "filed_at" not in payload

    def test_payload_keys_are_stable(self):
        """The 9 canonical keys are always present regardless of input."""
        payload = self._call({})
        assert set(payload.keys()) == {
            "bug_id", "title", "component", "severity", "kind",
            "observed", "expected", "repro", "workaround",
        }


class TestFormatInvestigationComment:
    def _call(self, run_id: str, **kwargs) -> str:
        from workflow.bug_investigation import format_investigation_comment
        return format_investigation_comment(run_id, **kwargs)

    def test_contains_run_id(self):
        result = self._call("run-abc-123")
        assert "run-abc-123" in result

    def test_default_status_is_queued(self):
        result = self._call("run-xyz")
        assert "status=queued" in result

    def test_custom_status(self):
        result = self._call("run-xyz", status="running")
        assert "status=running" in result

    def test_has_investigation_heading(self):
        result = self._call("run-xyz")
        assert "## Investigation" in result

    def test_starts_with_double_newline(self):
        result = self._call("run-xyz")
        assert result.startswith("\n\n")


class TestFormatPatchPacketComment:
    def _call(self, patch_packet: dict) -> str:
        from workflow.bug_investigation import format_patch_packet_comment
        return format_patch_packet_comment(patch_packet)

    def test_empty_dict_returns_empty_string(self):
        assert self._call({}) == ""

    def test_all_none_values_returns_empty_string(self):
        assert self._call({
            "minimal_repro": None,
            "root_cause": None,
            "test_plan": None,
            "implementation_sketch": None,
        }) == ""

    def test_has_patch_packet_heading_when_nonempty(self):
        result = self._call({"root_cause": "off-by-one"})
        assert "## Patch Packet" in result

    def test_includes_present_sections(self):
        result = self._call({
            "root_cause": "bad index",
            "test_plan": "add regression test",
        })
        assert "### Root Cause" in result
        assert "bad index" in result
        assert "### Test Plan" in result
        assert "add regression test" in result

    def test_omits_missing_sections(self):
        result = self._call({"root_cause": "x"})
        assert "Minimal Repro" not in result
        assert "Implementation Sketch" not in result

    def test_all_four_sections_present(self):
        pp = {
            "minimal_repro": "a",
            "root_cause": "b",
            "test_plan": "c",
            "implementation_sketch": "d",
        }
        result = self._call(pp)
        assert "### Minimal Repro" in result
        assert "### Root Cause" in result
        assert "### Test Plan" in result
        assert "### Implementation Sketch" in result
