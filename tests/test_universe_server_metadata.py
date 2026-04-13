from __future__ import annotations

import asyncio

from workflow.universe_server import mcp


def _list_tools():
    return asyncio.run(mcp.list_tools(run_middleware=False))


def _list_prompts():
    return asyncio.run(mcp.list_prompts(run_middleware=False))


class TestUniverseServerMetadata:
    def test_tool_metadata_is_directory_ready(self):
        tools = {tool.name: tool for tool in _list_tools()}

        universe = tools["universe"]
        assert universe.title == "Universe Operations"
        assert {"universe", "daemon", "fiction", "collaboration"} <= universe.tags
        assert universe.annotations.readOnlyHint is False
        assert universe.annotations.destructiveHint is False
        assert universe.annotations.idempotentHint is False
        assert universe.annotations.openWorldHint is True
        assert 'action="inspect"' in universe.description

        extensions = tools["extensions"]
        assert extensions.title == "Graph Extensions"
        assert {"extensions", "nodes", "plugins", "customization"} <= extensions.tags
        assert extensions.annotations.readOnlyHint is False
        assert extensions.annotations.destructiveHint is False
        assert extensions.annotations.idempotentHint is False
        assert extensions.annotations.openWorldHint is False
        assert "extension_guide" in extensions.description

    def test_prompt_metadata_is_present(self):
        prompts = {prompt.name: prompt for prompt in _list_prompts()}

        control_station = prompts["control_station"]
        assert control_station.title == "Control Station Guide"
        assert {"control", "daemon", "multiplayer", "operations"} <= control_station.tags
        assert "Universe Server" in control_station.description

        extension_guide = prompts["extension_guide"]
        assert extension_guide.title == "Extension Authoring Guide"
        assert {"extensions", "nodes", "plugins", "workflow"} <= extension_guide.tags
        assert "LangGraph nodes" in extension_guide.description
