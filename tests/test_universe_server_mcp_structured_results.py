"""Regression tests for direct wrappers vs MCP structured tool results."""

from __future__ import annotations

import asyncio
import json


def test_direct_wrappers_keep_json_string_contract() -> None:
    """Local callers still import wrappers directly and json.loads the result."""
    from workflow import universe_server as us

    status_raw = us.get_status()
    wiki_raw = us.wiki(action="list")

    assert isinstance(status_raw, str)
    assert isinstance(wiki_raw, str)
    assert json.loads(status_raw)["schema_version"] == 1
    assert "promoted" in json.loads(wiki_raw)


def test_mcp_tool_result_has_structured_content_and_text_content() -> None:
    """ChatGPT/Apps SDK needs structuredContent without losing text content."""
    from workflow import universe_server as us

    async def _call_status():
        return await us.mcp.call_tool("get_status", {"universe_id": ""})

    result = asyncio.run(_call_status())

    assert isinstance(result.structured_content, dict)
    assert result.structured_content["schema_version"] == 1
    assert result.content
    assert result.content[0].type == "text"
    assert json.loads(result.content[0].text)["schema_version"] == 1


def test_bug_070_wiki_and_change_context_mcp_results_are_structured(
    monkeypatch,
) -> None:
    """BUG-070: read aliases must match get_status' MCP response contract."""
    from workflow import universe_server as us
    from workflow.api import universe as universe_api

    def _fake_github_read(path, params=None):
        if path.endswith("/actions/workflows/auto-fix-bug.yml/runs"):
            return {"workflow_runs": []}, None
        return [], None

    monkeypatch.setattr(universe_api, "_github_read", _fake_github_read)

    async def _call_tools():
        return {
            "wiki": await us.mcp.call_tool("wiki", {"action": "list"}),
            "community_change_context": await us.mcp.call_tool(
                "community_change_context",
                {"filter_text": "queue", "limit": 1},
            ),
        }

    results = asyncio.run(_call_tools())

    wiki_result = results["wiki"]
    assert isinstance(wiki_result.structured_content, dict)
    assert "promoted_count" in wiki_result.structured_content
    assert wiki_result.content
    assert wiki_result.content[0].type == "text"
    assert "promoted_count" in json.loads(wiki_result.content[0].text)

    context_result = results["community_change_context"]
    assert isinstance(context_result.structured_content, dict)
    assert context_result.structured_content["kind"] == "community_change_context"
    assert context_result.content
    assert context_result.content[0].type == "text"
    assert json.loads(context_result.content[0].text)["kind"] == "community_change_context"
