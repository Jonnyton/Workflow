"""recursion_limit_override exposure (Tier-1 Step 6).

Guards that the default LangGraph recursion limit is raised from 25 to
100 AND that callers can override via ``recursion_limit_override``.
"""
from __future__ import annotations

import inspect

from workflow import runs


class TestDefaultBumped:
    def test_default_recursion_limit_is_100(self):
        assert runs.DEFAULT_RECURSION_LIMIT == 100

    def test_default_is_above_langgraph_stock_25(self):
        assert runs.DEFAULT_RECURSION_LIMIT > 25


class TestExecuteBranchSignature:
    def test_execute_branch_accepts_recursion_limit_override(self):
        sig = inspect.signature(runs.execute_branch)
        assert "recursion_limit_override" in sig.parameters
        param = sig.parameters["recursion_limit_override"]
        assert param.default is None  # optional, defaults to stock default

    def test_execute_branch_async_accepts_recursion_limit_override(self):
        sig = inspect.signature(runs.execute_branch_async)
        assert "recursion_limit_override" in sig.parameters
        param = sig.parameters["recursion_limit_override"]
        assert param.default is None

    def test_invoke_graph_accepts_recursion_limit(self):
        sig = inspect.signature(runs._invoke_graph)
        assert "recursion_limit" in sig.parameters
        param = sig.parameters["recursion_limit"]
        assert param.default == runs.DEFAULT_RECURSION_LIMIT


class TestOverrideThreading:
    """The override value must flow into the app.invoke config. We patch
    compile_branch so we don't need a real provider/checkpointer; the
    test asserts the threading is correct by spying on the config.
    """

    def test_override_flows_through_to_invoke_config(self, monkeypatch, tmp_path):
        captured_configs: list[dict] = []

        class _FakeApp:
            def invoke(self, state, config):
                captured_configs.append(config)
                return state

        class _FakeCompiledGraph:
            def compile(self, checkpointer):
                return _FakeApp()

        class _FakeCompiled:
            graph = _FakeCompiledGraph()

        monkeypatch.setattr(runs, "compile_branch", lambda *a, **k: _FakeCompiled())

        # Stub the saver context manager to a trivial no-op.
        class _FakeSaver:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            @staticmethod
            def from_conn_string(_path):
                return _FakeSaver()

        import langgraph.checkpoint.sqlite as saver_mod
        monkeypatch.setattr(saver_mod, "SqliteSaver", _FakeSaver)

        # Stub status updates + event sinks — we only care about config.
        monkeypatch.setattr(runs, "update_run_status", lambda *a, **k: None)
        monkeypatch.setattr(runs, "is_cancel_requested", lambda *a, **k: False)
        monkeypatch.setattr(runs, "record_event", lambda *a, **k: None)

        # Minimal branch stub — compile_branch is patched, so shape doesn't
        # actually matter. Just needs to not blow up during attribute access.
        class _StubBranch:
            branch_def_id = "x"
            node_defs = []
            graph_nodes = []

        runs._invoke_graph(
            tmp_path,
            run_id="test-run",
            branch=_StubBranch(),
            inputs={"a": 1},
            provider_call=None,
            recursion_limit=250,
        )

        assert captured_configs, "app.invoke was not called"
        cfg = captured_configs[0]
        assert cfg["recursion_limit"] == 250
        assert cfg["configurable"]["thread_id"] == "test-run"
