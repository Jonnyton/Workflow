"""Directory-safe MCP surface for public host listings.

This module exposes narrow tools intended for reviewed host directories such
as Claude's Connectors Directory and ChatGPT Apps. The legacy
``workflow.universe_server`` surface remains available at ``/mcp`` for custom
MCP clients. This directory surface is intentionally smaller: no catch-all
``action`` arguments, explicit read/write boundaries, and explicit tool
annotations for host review.
"""

from __future__ import annotations

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from workflow.api.extensions import _extensions_impl
from workflow.api.market import goals as _goals_impl
from workflow.api.status import get_status as _get_status_impl
from workflow.api.universe import _universe_impl
from workflow.api.wiki import wiki as _wiki_impl

directory_mcp = FastMCP(
    "workflow-directory",
    instructions=(
        "Workflow helps users discover durable workflow goals, inspect "
        "universes, browse the public knowledge wiki, and submit bounded "
        "requests into the Workflow daemon loop. Use these tools only when "
        "the user asks for Workflow, durable AI workflow design, shared "
        "workflow goals, or project wiki/status information."
    ),
    version="0.1.0",
)


@directory_mcp.tool(
    title="Get Workflow Status",
    tags={"status", "workflow", "diagnostics"},
    annotations=ToolAnnotations(
        title="Get Workflow Status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_workflow_status(universe_id: str = "") -> str:
    """Return daemon status, routing evidence, and safety caveats.

    Args:
        universe_id: Optional universe scope. Empty uses the active universe.
    """
    return _get_status_impl(universe_id=universe_id)


@directory_mcp.tool(
    title="List Workflow Universes",
    tags={"universes", "workflow", "browse"},
    annotations=ToolAnnotations(
        title="List Workflow Universes",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def list_workflow_universes(limit: int = 30) -> str:
    """List available Workflow universes without changing state.

    Args:
        limit: Maximum number of universes to return.
    """
    return _universe_impl(action="list", limit=limit)


@directory_mcp.tool(
    title="Inspect Workflow Universe",
    tags={"universes", "workflow", "inspect"},
    annotations=ToolAnnotations(
        title="Inspect Workflow Universe",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def inspect_workflow_universe(universe_id: str = "") -> str:
    """Inspect one Workflow universe and summarize durable state.

    Args:
        universe_id: Optional universe scope. Empty uses the active universe.
    """
    return _universe_impl(action="inspect", universe_id=universe_id)


@directory_mcp.tool(
    title="List Workflow Goals",
    tags={"goals", "workflow", "browse"},
    annotations=ToolAnnotations(
        title="List Workflow Goals",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def list_workflow_goals(tags: str = "", author: str = "", limit: int = 50) -> str:
    """List shared Workflow goals.

    Args:
        tags: Optional comma-separated tag filter.
        author: Optional author filter.
        limit: Maximum number of goals to return.
    """
    return _goals_impl(action="list", tags=tags, author=author, limit=limit)


@directory_mcp.tool(
    title="Search Workflow Goals",
    tags={"goals", "workflow", "search"},
    annotations=ToolAnnotations(
        title="Search Workflow Goals",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def search_workflow_goals(query: str, limit: int = 20) -> str:
    """Search Workflow goals by name, description, or tag.

    Args:
        query: Search text.
        limit: Maximum number of goals to return.
    """
    return _goals_impl(action="search", query=query, limit=limit)


@directory_mcp.tool(
    title="Get Workflow Goal",
    tags={"goals", "workflow", "inspect"},
    annotations=ToolAnnotations(
        title="Get Workflow Goal",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_workflow_goal(goal_id: str) -> str:
    """Return one Workflow goal and its bound branches.

    Args:
        goal_id: Goal identifier to inspect.
    """
    return _goals_impl(action="get", goal_id=goal_id)


@directory_mcp.tool(
    title="Search Workflow Wiki",
    tags={"wiki", "knowledge", "workflow", "search"},
    annotations=ToolAnnotations(
        title="Search Workflow Wiki",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def search_workflow_wiki(query: str, category: str = "", max_results: int = 10) -> str:
    """Search the Workflow public knowledge wiki.

    Args:
        query: Search text.
        category: Optional wiki category filter.
        max_results: Maximum number of wiki hits to return.
    """
    return _wiki_impl(
        action="search",
        query=query,
        category=category,
        max_results=max_results,
    )

@directory_mcp.tool(
    title="Read Workflow Wiki Page",
    tags={"wiki", "knowledge", "workflow", "read"},
    annotations=ToolAnnotations(
        title="Read Workflow Wiki Page",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def read_workflow_wiki_page(page: str) -> str:
    """Read one Workflow wiki page.

    Args:
        page: Wiki page slug or path.
    """
    return _wiki_impl(action="read", page=page)


@directory_mcp.tool(
    title="List Workflow Runs",
    tags={"runs", "workflow", "browse"},
    annotations=ToolAnnotations(
        title="List Workflow Runs",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def list_workflow_runs(status: str = "", limit: int = 20) -> str:
    """List recent Workflow branch runs without starting or stopping work.

    Args:
        status: Optional run status filter.
        limit: Maximum number of runs to return.
    """
    return _extensions_impl(action="list_runs", status=status, limit=limit)


@directory_mcp.tool(
    title="Propose Workflow Goal",
    tags={"goals", "workflow", "create"},
    annotations=ToolAnnotations(
        title="Propose Workflow Goal",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def propose_workflow_goal(
    name: str,
    description: str = "",
    tags: str = "",
    visibility: str = "public",
) -> str:
    """Create a shared Workflow goal proposal.

    Args:
        name: Human-readable goal name.
        description: Optional goal description.
        tags: Optional comma-separated tags.
        visibility: Visibility value accepted by Workflow, usually public.
    """
    return _goals_impl(
        action="propose",
        name=name,
        description=description,
        tags=tags,
        visibility=visibility,
    )


@directory_mcp.tool(
    title="Submit Workflow Request",
    tags={"requests", "workflow", "queue"},
    annotations=ToolAnnotations(
        title="Submit Workflow Request",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def submit_workflow_request(
    text: str,
    universe_id: str = "",
    request_type: str = "scene_direction",
    branch_id: str = "",
) -> str:
    """Queue a bounded request for the Workflow daemon.

    Args:
        text: Request text to queue.
        universe_id: Optional target universe. Empty uses the active universe.
        request_type: Workflow request type.
        branch_id: Optional target branch identifier.
    """
    return _universe_impl(
        action="submit_request",
        universe_id=universe_id,
        text=text,
        request_type=request_type,
        branch_id=branch_id,
    )
