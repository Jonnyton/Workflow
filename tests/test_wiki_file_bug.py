from __future__ import annotations

import json

from workflow.api import wiki as wiki_module


def test_wiki_file_bug_rejects_truthy_unsupported_body_kwargs() -> None:
    response = json.loads(
        wiki_module._wiki_file_bug(
            title="Free-form body should be rejected",
            component="wiki",
            severity="major",
            body="unexpected body",
            content="unexpected content",
        )
    )

    assert response == {
        "error": (
            "Unsupported file_bug field(s): body, content. file_bug only accepts "
            "title, component, severity, and the structured body fields repro, "
            "observed, expected, workaround; free-form body/content is not supported."
        ),
        "hint": (
            "Use wiki(action=\"file_bug\", title=..., component=..., severity=...) "
            "and pass body details via the repro, observed, expected, and "
            "workaround fields."
        ),
    }


def test_wiki_file_bug_ignores_falsey_body_kwargs_and_default_transport_kwargs(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(wiki_module, "_wiki_pages_dir", lambda: tmp_path / "pages")
    monkeypatch.setattr(wiki_module, "_wiki_drafts_dir", lambda: tmp_path / "drafts")
    monkeypatch.setattr(wiki_module, "_append_wiki_log", lambda _msg: None)

    response = json.loads(
        wiki_module._wiki_file_bug(
            title="Falsey body kwargs stay allowed",
            component="wiki",
            severity="minor",
            body="",
            content="",
            dry_run=True,
            similarity_threshold=0.25,
            max_results=10,
            offset=0,
            max_chars=wiki_module._WIKI_READ_DEFAULT_MAX_CHARS,
        )
    )

    assert response["status"] == "filed"
    assert "warning" not in response
    assert response["path"].startswith("pages/bugs/bug-001-")
