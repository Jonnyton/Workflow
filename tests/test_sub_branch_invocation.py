"""Tests for the sub-branch invocation primitive.

Covers:
- validate() catches bad invoke_branch_spec / await_run_spec shapes
- _build_invoke_branch_node: blocking mode populates output_mapping
- _build_invoke_branch_node: async mode writes run_id
- _build_await_branch_run_node: polls until terminal and maps output
- await_branch_run: timeout raises TimeoutError
- await_branch_run: missing run_id_field in state raises RuntimeError
- compile_branch: missing base_path raises CompilerError for invoke nodes
- recursion depth cap raises CompilerError at compile time
- poll_child_run_status: returns immediately for completed run
- poll_child_run_status: raises KeyError for unknown run_id
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from workflow.branches import (
    BranchDefinition,
    EdgeDefinition,
    GraphNodeRef,
    NodeDefinition,
)
from workflow.graph_compiler import (
    CompilerError,
    _build_await_branch_run_node,
    _build_invoke_branch_node,
)
from workflow.runs import MAX_INVOKE_BRANCH_DEPTH, poll_child_run_status

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _simple_branch(node_def: NodeDefinition, entry: str = "n1") -> BranchDefinition:
    return BranchDefinition(
        branch_def_id="b1",
        name="test",
        entry_point=entry,
        node_defs=[node_def],
        graph_nodes=[GraphNodeRef(id=entry, node_def_id=node_def.node_id)],
        state_schema=[
            {"name": "child_run_id", "type": "str"},
            {"name": "result", "type": "str"},
        ],
    )


# ─── validate() shape checks ──────────────────────────────────────────────────

class TestValidateInvokeBranchSpec:
    def test_missing_branch_def_id_is_error(self):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={"wait_mode": "blocking"},
        )
        b = _simple_branch(nd)
        errs = b.validate()
        assert any("branch_def_id" in e for e in errs)

    def test_invalid_wait_mode_is_error(self):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={"branch_def_id": "child", "wait_mode": "fire_and_forget"},
        )
        b = _simple_branch(nd)
        errs = b.validate()
        assert any("wait_mode" in e for e in errs)

    def test_valid_spec_no_error(self):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={
                "branch_def_id": "child",
                "inputs_mapping": {},
                "output_mapping": {},
                "wait_mode": "blocking",
            },
        )
        b = _simple_branch(nd)
        errs = [
            e for e in b.validate()
            if "invoke_branch_spec" in e or "branch_def_id" in e or "wait_mode" in e
        ]
        assert not errs

    def test_invoke_spec_plus_template_is_error(self):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            prompt_template="hello",
            invoke_branch_spec={"branch_def_id": "child", "wait_mode": "blocking"},
        )
        b = _simple_branch(nd)
        errs = b.validate()
        assert any("mutually exclusive" in e for e in errs)


class TestValidateAwaitRunSpec:
    def test_missing_run_id_field_is_error(self):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            await_run_spec={"output_mapping": {}},
        )
        b = _simple_branch(nd)
        errs = b.validate()
        assert any("run_id_field" in e for e in errs)

    def test_valid_spec_no_error(self):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            await_run_spec={"run_id_field": "child_run_id", "output_mapping": {}},
        )
        b = _simple_branch(nd)
        errs = [e for e in b.validate() if "await_run_spec" in e or "run_id_field" in e]
        assert not errs

    def test_await_spec_plus_source_code_is_error(self):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            source_code="x = 1",
            approved=True,
            await_run_spec={"run_id_field": "child_run_id"},
        )
        b = _simple_branch(nd)
        errs = b.validate()
        assert any("mutually exclusive" in e for e in errs)


# ─── compile_branch: missing base_path ────────────────────────────────────────

class TestCompileBranchMissingBasePath:
    def test_invoke_branch_node_without_base_path_raises(self):
        from workflow.graph_compiler import compile_branch

        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={
                "branch_def_id": "child",
                "wait_mode": "blocking",
                "inputs_mapping": {},
                "output_mapping": {},
            },
        )
        b = BranchDefinition(
            branch_def_id="b1", name="test", entry_point="n1",
            node_defs=[nd],
            graph_nodes=[GraphNodeRef(id="n1", node_def_id="n1")],
            edges=[EdgeDefinition(from_node="n1", to_node="END")],
        )
        with pytest.raises(CompilerError, match="base_path"):
            compile_branch(b)

    def test_await_run_node_without_base_path_raises(self):
        from workflow.graph_compiler import compile_branch

        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            await_run_spec={"run_id_field": "child_run_id", "output_mapping": {}},
        )
        b = BranchDefinition(
            branch_def_id="b1", name="test", entry_point="n1",
            node_defs=[nd],
            graph_nodes=[GraphNodeRef(id="n1", node_def_id="n1")],
            state_schema=[{"name": "child_run_id", "type": "str"}],
            edges=[EdgeDefinition(from_node="n1", to_node="END")],
        )
        with pytest.raises(CompilerError, match="base_path"):
            compile_branch(b)


# ─── _build_invoke_branch_node: blocking ──────────────────────────────────────

class TestInvokeBranchBlocking:
    def test_blocking_populates_output_mapping(self, tmp_path, monkeypatch):
        from workflow.runs import RUN_STATUS_COMPLETED, RunOutcome

        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={
                "branch_def_id": "child",
                "inputs_mapping": {"parent_q": "q"},
                "output_mapping": {"result": "answer"},
                "wait_mode": "blocking",
            },
        )

        child_outcome = RunOutcome(
            run_id="child-run-1",
            status=RUN_STATUS_COMPLETED,
            output={"answer": "42"},
            error="",
        )

        child_branch_mock = MagicMock()
        child_branch_mock.validate.return_value = []

        _child_raw = {"branch_def_id": "child", "name": "c", "node_defs": [], "edges": []}
        with (
            patch("workflow.author_server.get_branch_definition", return_value=_child_raw),
            patch("workflow.branches.BranchDefinition.from_dict", return_value=child_branch_mock),
            patch("workflow.runs.execute_branch", return_value=child_outcome) as mock_exec,
        ):
            fn = _build_invoke_branch_node(nd, base_path=tmp_path, event_sink=None)
            result = fn({"parent_q": "what is 6x7?"})

        assert result == {"result": "42"}
        mock_exec.assert_called_once()
        _, call_kwargs = mock_exec.call_args
        assert call_kwargs["inputs"] == {"q": "what is 6x7?"}


class TestInvokeBranchAsync:
    def test_async_writes_run_id(self, tmp_path, monkeypatch):
        from workflow.runs import RUN_STATUS_QUEUED, RunOutcome

        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={
                "branch_def_id": "child",
                "inputs_mapping": {},
                "output_mapping": {"child_run_id": "ignored"},
                "wait_mode": "async",
            },
        )

        queued_outcome = RunOutcome(
            run_id="async-child-99",
            status=RUN_STATUS_QUEUED,
            output={},
            error="",
        )

        child_branch_mock = MagicMock()
        child_branch_mock.validate.return_value = []

        _child_raw = {"branch_def_id": "child", "name": "c", "node_defs": [], "edges": []}
        with (
            patch("workflow.author_server.get_branch_definition", return_value=_child_raw),
            patch("workflow.branches.BranchDefinition.from_dict", return_value=child_branch_mock),
            patch("workflow.runs.execute_branch_async", return_value=queued_outcome),
        ):
            fn = _build_invoke_branch_node(nd, base_path=tmp_path, event_sink=None)
            result = fn({})

        assert result == {"child_run_id": "async-child-99"}


# ─── _build_await_branch_run_node ─────────────────────────────────────────────

class TestAwaitBranchRunNode:
    def test_populates_output_from_completed_child(self, tmp_path):
        from workflow.runs import RUN_STATUS_COMPLETED

        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            await_run_spec={
                "run_id_field": "child_run_id",
                "output_mapping": {"result": "answer"},
                "timeout_seconds": 5.0,
            },
        )

        child_record = {
            "run_id": "child-99",
            "status": RUN_STATUS_COMPLETED,
            "output": {"answer": "hello"},
        }

        with patch("workflow.runs.poll_child_run_status", return_value=child_record) as mock_poll:
            fn = _build_await_branch_run_node(nd, base_path=tmp_path, event_sink=None)
            result = fn({"child_run_id": "child-99"})

        assert result == {"result": "hello"}
        mock_poll.assert_called_once_with(tmp_path, "child-99", timeout_seconds=5.0)

    def test_missing_run_id_raises_runtime_error(self, tmp_path):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            await_run_spec={
                "run_id_field": "child_run_id",
                "output_mapping": {},
            },
        )
        fn = _build_await_branch_run_node(nd, base_path=tmp_path, event_sink=None)
        with pytest.raises(RuntimeError, match="child_run_id"):
            fn({"child_run_id": ""})

    def test_timeout_propagates(self, tmp_path):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            await_run_spec={
                "run_id_field": "child_run_id",
                "output_mapping": {},
                "timeout_seconds": 0.01,
            },
        )
        with patch("workflow.runs.poll_child_run_status", side_effect=TimeoutError("timed out")):
            fn = _build_await_branch_run_node(nd, base_path=tmp_path, event_sink=None)
            with pytest.raises(TimeoutError):
                fn({"child_run_id": "some-run"})


# ─── recursion depth cap ──────────────────────────────────────────────────────

class TestRecursionDepthCap:
    def test_depth_at_cap_raises_compiler_error(self, tmp_path):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={
                "branch_def_id": "child",
                "wait_mode": "blocking",
                "inputs_mapping": {},
                "output_mapping": {},
            },
        )
        with pytest.raises(CompilerError, match="recursion depth cap"):
            _build_invoke_branch_node(
                nd, base_path=tmp_path, event_sink=None,
                depth=MAX_INVOKE_BRANCH_DEPTH,
            )

    def test_depth_below_cap_is_ok(self, tmp_path):
        nd = NodeDefinition(
            node_id="n1", display_name="N1",
            invoke_branch_spec={
                "branch_def_id": "child",
                "wait_mode": "blocking",
                "inputs_mapping": {},
                "output_mapping": {},
            },
        )
        # Should not raise
        fn = _build_invoke_branch_node(
            nd, base_path=tmp_path, event_sink=None,
            depth=MAX_INVOKE_BRANCH_DEPTH - 1,
        )
        assert callable(fn)


# ─── poll_child_run_status ────────────────────────────────────────────────────

class TestPollChildRunStatus:
    def test_returns_immediately_for_completed_run(self, tmp_path):
        from workflow.runs import (
            RUN_STATUS_COMPLETED,
            create_run,
            initialize_runs_db,
            update_run_status,
        )

        initialize_runs_db(tmp_path)
        run_id = create_run(
            tmp_path,
            branch_def_id="b1",
            thread_id="thread-poll",
            run_name="poll-test",
            actor="tester",
            inputs={},
        )
        update_run_status(tmp_path, run_id, status=RUN_STATUS_COMPLETED, finished_at=time.time())

        record = poll_child_run_status(tmp_path, run_id, timeout_seconds=5.0)
        assert record["status"] == RUN_STATUS_COMPLETED
        assert record["run_id"] == run_id

    def test_raises_key_error_for_unknown_run(self, tmp_path):
        from workflow.runs import initialize_runs_db

        initialize_runs_db(tmp_path)
        with pytest.raises(KeyError, match="not found"):
            poll_child_run_status(tmp_path, "nonexistent-run", timeout_seconds=1.0)

    def test_raises_timeout_for_stuck_run(self, tmp_path):
        from workflow.runs import (
            RUN_STATUS_RUNNING,
            create_run,
            initialize_runs_db,
            update_run_status,
        )

        initialize_runs_db(tmp_path)
        run_id = create_run(
            tmp_path,
            branch_def_id="b1",
            thread_id="thread-stuck",
            run_name="stuck",
            actor="tester",
            inputs={},
        )
        update_run_status(tmp_path, run_id, status=RUN_STATUS_RUNNING)

        with pytest.raises(TimeoutError):
            poll_child_run_status(tmp_path, run_id, timeout_seconds=0.05, poll_interval=0.01)
