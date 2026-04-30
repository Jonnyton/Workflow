"""BUG-018: maintainer-only notes on node definitions."""

from __future__ import annotations

from workflow.api.branches import (
    _PATCH_NODES_FIELDS,
    _apply_node_spec,
    _apply_patch_op,
)
from workflow.branches import BranchDefinition, NodeDefinition


def test_node_definition_round_trips_maintainer_notes_in_dict():
    node = NodeDefinition(
        node_id="capture",
        display_name="Capture",
        prompt_template="Extract {raw}",
        maintainer_notes="Builder note: input is expected to be messy.",
    )

    rehydrated = NodeDefinition.from_dict(node.to_dict())

    assert rehydrated.maintainer_notes == node.maintainer_notes


def test_maintainer_notes_are_not_legacy_runtime_registration_fields():
    node = NodeDefinition(
        node_id="capture",
        display_name="Capture",
        source_code="def run(state): return {}",
        maintainer_notes="Builder-only implementation context.",
    )

    assert "maintainer_notes" not in node.to_node_registration()


def test_apply_node_spec_accepts_maintainer_notes():
    branch = BranchDefinition(name="Recipe tracker")

    err = _apply_node_spec(
        branch,
        {
            "node_id": "capture",
            "display_name": "Capture",
            "prompt_template": "Extract {raw}",
            "maintainer_notes": "Builder note: compare parser variants.",
        },
    )

    assert err == ""
    assert branch.node_defs[0].maintainer_notes == (
        "Builder note: compare parser variants."
    )


def test_patch_update_node_updates_maintainer_notes():
    branch = BranchDefinition(
        name="Recipe tracker",
        node_defs=[
            NodeDefinition(
                node_id="capture",
                display_name="Capture",
                prompt_template="Extract {raw}",
            )
        ],
    )

    err = _apply_patch_op(
        branch,
        {
            "op": "update_node",
            "node_id": "capture",
            "maintainer_notes": "Builder note: raw input is noisy.",
        },
    )

    assert err == ""
    assert branch.node_defs[0].maintainer_notes == (
        "Builder note: raw input is noisy."
    )


def test_patch_nodes_whitelist_allows_maintainer_notes():
    assert _PATCH_NODES_FIELDS["maintainer_notes"] is str
