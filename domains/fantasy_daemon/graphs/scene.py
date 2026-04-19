"""Scene graph -- the core creative loop.

Topology: orient -> plan -> draft -> commit -> (accept: END | second_draft: draft)

The conditional edge ``route_after_commit`` implements the never-block rule:
at most one revision loop (second_draft), then accept regardless.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from domains.fantasy_daemon.phases.commit import commit
from domains.fantasy_daemon.phases.draft import draft
from domains.fantasy_daemon.phases.orient import orient
from domains.fantasy_daemon.phases.plan import plan
from domains.fantasy_daemon.state.scene_state import SceneState


def route_after_commit(state: SceneState) -> str:
    """Route after commit: accept, attempt one revision, or end.

    Never blocks on human input.  At most one second_draft attempt.

    Returns
    -------
    str
        ``'__end__'`` if accepted or revision already used.
        ``'draft'`` if second_draft requested and not yet attempted.
    """
    if state["verdict"] == "accept":
        return END
    if state["verdict"] == "second_draft" and not state["second_draft_used"]:
        return "draft"
    # "revert" or second_draft already used -- never block, end the scene
    return END


def build_scene_graph() -> StateGraph:
    """Construct the Scene StateGraph (uncompiled).

    Returns
    -------
    StateGraph
        Uncompiled graph.  Caller compiles with a checkpointer.
    """
    graph = StateGraph(SceneState)

    # Nodes
    graph.add_node("orient", orient)
    graph.add_node("plan", plan)
    graph.add_node("draft", draft)
    graph.add_node("commit", commit)

    # Linear flow
    graph.set_entry_point("orient")
    graph.add_edge("orient", "plan")
    graph.add_edge("plan", "draft")
    graph.add_edge("draft", "commit")

    # Conditional exit after commit
    graph.add_conditional_edges(
        "commit",
        route_after_commit,
        {
            END: END,
            "draft": "draft",
        },
    )

    return graph
