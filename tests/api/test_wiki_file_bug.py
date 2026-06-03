import json

from workflow.api.helpers import _scoped_wiki_root
from workflow.api.wiki import _ensure_wiki_scaffold, _wiki_file_bug


def test_wiki_file_bug_rejects_truthy_unsupported_body_kwargs(tmp_path):
    with _scoped_wiki_root(tmp_path):
        _ensure_wiki_scaffold(tmp_path)
        response = json.loads(
            _wiki_file_bug(
                title="Body kwargs should fail fast",
                component="workflow.api",
                severity="major",
                **{
                    "content": "Observed details routed through the wrong field.",
                    "body": "Alternate body field should also fail.",
                },
            )
        )

    assert response["error"] == "Unsupported file_bug body/content argument(s): body, content."
    assert "Use repro, observed, expected, and workaround" in response["hint"]
    assert list((tmp_path / "pages" / "bugs").glob("*.md")) == []


def test_wiki_file_bug_supported_fields_still_file(tmp_path):
    with _scoped_wiki_root(tmp_path):
        _ensure_wiki_scaffold(tmp_path)
        response = json.loads(
            _wiki_file_bug(
                title="Bug filing keeps supported body fields",
                component="workflow.api",
                severity="major",
                repro="1. Open file_bug\n2. Provide supported fields",
                observed="The filing should capture observed details.",
                expected="The filing should still succeed.",
                workaround="Use the supported arguments directly.",
            )
        )

    assert response["status"] == "filed"
    assert response["kind"] == "bug"
    assert "warning" not in response

    bug_path = tmp_path / response["path"]
    assert bug_path.exists()

    bug_text = bug_path.read_text(encoding="utf-8")
    assert "## What happened\n\nThe filing should capture observed details." in bug_text
    assert "## What was expected\n\nThe filing should still succeed." in bug_text
    assert "## Repro\n\n1. Open file_bug\n2. Provide supported fields" in bug_text
    assert "## Workaround\n\nUse the supported arguments directly." in bug_text
