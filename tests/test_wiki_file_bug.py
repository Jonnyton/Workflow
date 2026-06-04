from __future__ import annotations

import json
import sys
import types

import pytest

import workflow
import workflow.wiki
from workflow.api import wiki as wiki_api


class _StubReceipt:
    def to_response(self) -> dict[str, str]:
        return {"status": "stubbed"}


def _install_file_bug_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    investigation_module = types.ModuleType("workflow.bug_investigation")
    investigation_module._maybe_enqueue_investigation = lambda **kwargs: None
    investigation_module.format_investigation_comment = (
        lambda **kwargs: "\n\n## Investigation\n\nstub\n"
    )

    receipt_module = types.ModuleType("workflow.wiki.trigger_receipts")
    receipt_module.create_pending = lambda **kwargs: _StubReceipt()
    receipt_module.mark_failed = lambda receipt, error: receipt
    receipt_module.mark_queued = lambda receipt, dispatcher_request_id: receipt
    receipt_module.mark_skipped = lambda receipt, reason: receipt

    monkeypatch.setitem(sys.modules, "workflow.bug_investigation", investigation_module)
    monkeypatch.setitem(sys.modules, "workflow.wiki.trigger_receipts", receipt_module)
    monkeypatch.setattr(workflow, "bug_investigation", investigation_module, raising=False)
    monkeypatch.setattr(workflow.wiki, "trigger_receipts", receipt_module, raising=False)


@pytest.mark.parametrize("field", ["content", "body"])
def test_wiki_file_bug_rejects_truthy_unsupported_body_kwargs(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    def _unexpected_path_access():
        raise AssertionError("file_bug should fail before filesystem access")

    monkeypatch.setattr(wiki_api, "_wiki_pages_dir", _unexpected_path_access)
    monkeypatch.setattr(wiki_api, "_wiki_drafts_dir", _unexpected_path_access)

    response = json.loads(
        wiki_api._wiki_file_bug(
            title="Title-only filing",
            component="workflow.api",
            severity="major",
            **{field: "raw body text"},
        )
    )

    assert response["error"] == (
        f"Unsupported file_bug field(s): {field}. file_bug does not accept raw "
        "content/body text; use title with structured body fields "
        "(repro, observed, expected, workaround) instead."
    )
    assert "content/body" in response["hint"]


@pytest.mark.parametrize("field", ["content", "body"])
@pytest.mark.parametrize("value", ["", None, False, 0, [], {}])
def test_wiki_file_bug_accepts_falsy_unsupported_body_kwargs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    field: str,
    value,
) -> None:
    _install_file_bug_stubs(monkeypatch)
    monkeypatch.setattr(wiki_api, "_wiki_pages_dir", lambda: tmp_path / "pages")
    monkeypatch.setattr(wiki_api, "_wiki_drafts_dir", lambda: tmp_path / "drafts")
    monkeypatch.setattr(wiki_api, "_append_wiki_log", lambda msg: None)
    monkeypatch.setattr(wiki_api, "_default_universe", lambda: "default")
    monkeypatch.setattr(wiki_api, "_universe_dir", lambda universe_id: tmp_path / universe_id)

    response = json.loads(
        wiki_api._wiki_file_bug(
            title="Falsy unsupported kwargs stay ignored",
            component="workflow.api",
            severity="minor",
            observed="Observed behavior for the regression test.",
            expected="Expected behavior for the regression test.",
            **{field: value},
        )
    )

    assert response["status"] == "filed"
    assert "warning" not in response
    assert (tmp_path / response["path"]).exists()
