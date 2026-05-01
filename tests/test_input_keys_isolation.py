"""Input-keys isolation for prompt_template nodes (BUG-007 shape).

Restores symmetry vs the code-node sandbox (``node_sandbox.py:279-282``
already filters code-node state views). Prompt_template nodes previously
read the entire state dict, so a template like ``{other_node_output}``
silently succeeded even when ``other_node_output`` wasn't in
``input_keys``. That's an implicit cross-node dependency which reduces
branch portability and hides unintentional coupling.

Contract:

- When ``input_keys`` is non-empty, ``_build_prompt_template_node``
  renders against a state view filtered to ``input_keys`` only.
  Out-of-keys placeholders raise ``CompilerError`` at runtime.
- Regardless of flag, ``collect_build_warnings(branch)`` emits one
  warning per out-of-input_keys placeholder so authors see the leak.
- When ``event_sink`` is provided, the runtime emits
  ``phase="warning"`` events per leak before the isolation error.
- ``strict_input_isolation`` remains a legacy schema field from the
  opt-in period; it no longer controls prompt-template isolation.
"""

from __future__ import annotations

import pytest

from workflow.branches import (
    BranchDefinition,
    EdgeDefinition,
    GraphNodeRef,
    NodeDefinition,
)
from workflow.graph_compiler import (
    CompilerError,
    _build_prompt_template_node,
    _out_of_input_keys,
    _placeholder_keys,
    collect_build_warnings,
    compile_branch,
)

# ─── _placeholder_keys / _out_of_input_keys (static analysis) ─────────────


def test_placeholder_keys_extracts_identifiers():
    assert _placeholder_keys("Hi {name}, topic={topic}") == ["name", "topic"]


def test_placeholder_keys_dedupes_preserving_order():
    assert _placeholder_keys("{a} {b} {a} {c} {b}") == ["a", "b", "c"]


def test_placeholder_keys_ignores_literal_braces():
    # {"json"} isn't an identifier placeholder — must be ignored.
    assert _placeholder_keys('{name} and {"doc": 1}') == ["name"]


def test_placeholder_keys_normalizes_double_braces():
    # Jinja-style {{x}} normalizes to {x} before extraction.
    assert _placeholder_keys("{{topic}} and {other}") == ["topic", "other"]


def test_placeholder_keys_empty_template():
    assert _placeholder_keys("") == []


def test_out_of_input_keys_returns_leak_list():
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="Write {topic} using {style_guide}.",
    )
    assert _out_of_input_keys(node) == ["style_guide"]


def test_out_of_input_keys_empty_when_all_declared():
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic", "style_guide"],
        prompt_template="Write {topic} using {style_guide}.",
    )
    assert _out_of_input_keys(node) == []


def test_out_of_input_keys_empty_when_no_input_keys_declared():
    """No input_keys = opted out of static isolation. Don't warn."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=[],
        prompt_template="Write {topic}.",
    )
    assert _out_of_input_keys(node) == []


# ─── collect_build_warnings (build-time surface) ──────────────────────────


def _single_node_branch(node: NodeDefinition) -> BranchDefinition:
    """Build a minimal valid branch around a single node."""
    return BranchDefinition(
        name="test",
        entry_point="n1",
        graph_nodes=[GraphNodeRef(id="n1", node_def_id="n1", position=0)],
        edges=[EdgeDefinition(from_node="n1", to_node="END")],
        node_defs=[node],
    )


def test_collect_build_warnings_surfaces_input_keys_leak():
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="Write {topic} using {style_guide}.",
    )
    warnings = collect_build_warnings(_single_node_branch(node))
    assert len(warnings) == 1
    w = warnings[0]
    assert w["kind"] == "input_keys_leak"
    assert w["node_id"] == "n1"
    assert w["placeholder"] == "style_guide"
    assert w["declared_input_keys"] == ["topic"]
    assert "style_guide" in w["message"]


def test_collect_build_warnings_one_per_placeholder():
    """Multiple leaks → multiple warnings, one per offending placeholder."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="{topic} {style} {genre} {era}",
    )
    warnings = collect_build_warnings(_single_node_branch(node))
    placeholders = [w["placeholder"] for w in warnings]
    assert placeholders == ["style", "genre", "era"]


def test_collect_build_warnings_fires_regardless_of_strict_flag():
    """Build-time warnings are flag-independent. The legacy flag no
    longer controls runtime isolation, but persisted values should not
    affect warning visibility."""
    node_strict = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="{topic} {other}",
        strict_input_isolation=True,
    )
    node_lax = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="{topic} {other}",
        strict_input_isolation=False,
    )
    assert len(collect_build_warnings(_single_node_branch(node_strict))) == 1
    assert len(collect_build_warnings(_single_node_branch(node_lax))) == 1


def test_collect_build_warnings_empty_for_clean_branch():
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="Write about {topic}.",
    )
    assert collect_build_warnings(_single_node_branch(node)) == []


def test_collect_build_warnings_ignores_nodes_without_input_keys():
    """Undeclared contract = opted out of isolation. No warnings."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=[],
        prompt_template="{anything} {goes}",
    )
    assert collect_build_warnings(_single_node_branch(node)) == []


def test_compile_branch_emits_warnings_through_event_sink():
    """Build-time warnings must reach the event_sink so they show up
    in the per-run event log BEFORE the first node runs.

    Note: the literal-brace spec added a build-time validator that
    rejects genuinely-undeclared placeholders (absent from BOTH
    input_keys AND state_schema). To keep this a *warning* test
    (placeholder declared in state_schema but leaked outside the
    node's input_keys), we declare ``style_guide`` in state_schema —
    then the leak surfaces as an input_keys_leak warning, not a
    hard rejection.
    """
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="{topic} {style_guide}",
    )
    branch = _single_node_branch(node)
    branch.state_schema = [{"name": "style_guide", "type": "str"}]
    events: list[dict] = []

    def sink(**kwargs):
        events.append(kwargs)

    compile_branch(branch, event_sink=sink)

    warning_events = [e for e in events if e.get("phase") == "warning"]
    assert len(warning_events) == 1
    assert warning_events[0]["kind"] == "input_keys_leak"
    assert warning_events[0]["placeholder"] == "style_guide"
    assert warning_events[0]["node_id"] == "n1"


# ─── input_keys isolation runtime behavior ────────────────────────────────


def _make_prompt_fn(
    node: NodeDefinition,
    *,
    provider_call=lambda prompt, system, role="writer": f"RENDERED::{prompt}",
    event_sink=None,
):
    return _build_prompt_template_node(
        node, provider_call=provider_call, event_sink=event_sink,
    )


def test_input_keys_isolation_valid_renders_normally():
    """Placeholders inside input_keys render normally."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        output_keys=["draft"],
        prompt_template="Write about {topic}.",
    )
    fn = _make_prompt_fn(node)
    result = fn({"topic": "whales", "leaked_key": "should not reach model"})
    assert result == {"draft": "RENDERED::Write about whales."}


def test_input_keys_isolation_rejects_out_of_input_keys():
    """Placeholder outside input_keys raises CompilerError even when
    the state has that key."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        output_keys=["draft"],
        prompt_template="Write {topic} with {leaked_key}.",
    )
    fn = _make_prompt_fn(node)
    with pytest.raises(CompilerError) as exc:
        fn({"topic": "whales", "leaked_key": "should not be readable"})
    assert "leaked_key" in str(exc.value)
    assert "outside declared input_keys" in str(exc.value)


def test_input_keys_isolation_rejects_even_when_state_has_key():
    """The whole point: even if state HAS the out-of-keys value,
    input_keys isolation refuses to read it."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        output_keys=["draft"],
        prompt_template="{leaked_key}",
    )
    fn = _make_prompt_fn(node)
    with pytest.raises(CompilerError):
        fn({"topic": "whales", "leaked_key": "present but filtered out"})


def test_legacy_strict_false_still_rejects_leaked_state():
    """BUG-007: strict_input_isolation is legacy metadata; a declared
    input_keys contract is enforced even when the flag is false."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        output_keys=["draft"],
        prompt_template="Write {topic} with {leaked_key}.",
        strict_input_isolation=False,
    )
    fn = _make_prompt_fn(node)
    with pytest.raises(CompilerError) as exc:
        fn({"topic": "whales", "leaked_key": "style-guide"})
    assert "leaked_key" in str(exc.value)
    assert "outside declared input_keys" in str(exc.value)


def test_runtime_warning_emits_before_isolation_error():
    """Runtime still tells the operator about leaks via event_sink
    before rejecting the prompt."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        output_keys=["draft"],
        prompt_template="{topic} {leaked}",
        strict_input_isolation=False,
    )
    events: list[dict] = []

    def sink(**kwargs):
        events.append(kwargs)

    fn = _make_prompt_fn(node, event_sink=sink)
    with pytest.raises(CompilerError):
        fn({"topic": "whales", "leaked": "style"})

    warning_events = [e for e in events if e.get("phase") == "warning"]
    assert len(warning_events) == 1
    assert warning_events[0]["kind"] == "input_keys_leak"
    assert warning_events[0]["placeholder"] == "leaked"


def test_no_runtime_warning_when_clean():
    """No leaks -> no warnings."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        output_keys=["draft"],
        prompt_template="Write {topic}.",
        strict_input_isolation=False,
    )
    events: list[dict] = []

    def sink(**kwargs):
        events.append(kwargs)

    fn = _make_prompt_fn(node, event_sink=sink)
    fn({"topic": "whales"})
    warning_events = [e for e in events if e.get("phase") == "warning"]
    assert warning_events == []


def test_without_declared_input_keys_is_permissive():
    """If input_keys is empty, the node has not declared a state
    contract, so rendering uses the normal state view."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=[],
        output_keys=["draft"],
        prompt_template="Write {topic}.",
        strict_input_isolation=True,
    )
    fn = _make_prompt_fn(node)
    result = fn({"topic": "whales"})
    assert result == {"draft": "RENDERED::Write whales."}


def test_isolated_prompt_still_raises_on_genuinely_missing_input_keys():
    """A placeholder declared in input_keys but absent from state raises
    the generic missing-state error."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic", "never_defined"],
        output_keys=["draft"],
        prompt_template="{topic} {never_defined}",
        strict_input_isolation=False,
    )
    fn = _make_prompt_fn(node)
    with pytest.raises(CompilerError) as exc:
        fn({"topic": "whales"})
    assert "outside declared input_keys" not in str(exc.value)
    assert "never_defined" in str(exc.value)


# ─── schema persistence ───────────────────────────────────────────────────


def test_strict_input_isolation_roundtrips_through_to_dict():
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        input_keys=["topic"],
        prompt_template="{topic}",
        strict_input_isolation=True,
    )
    d = node.to_dict()
    assert d["strict_input_isolation"] is True
    restored = NodeDefinition.from_dict(d)
    assert restored.strict_input_isolation is True


def test_strict_input_isolation_default_false():
    """Legacy schema default remains False for persisted metadata."""
    node = NodeDefinition(node_id="n1", display_name="n1")
    assert node.strict_input_isolation is False


def test_node_registration_shape_excludes_strict_flag():
    """Legacy NodeRegistration dict is a stable sandbox contract —
    strict_input_isolation is legacy prompt-template metadata and should
    not leak into that surface."""
    node = NodeDefinition(
        node_id="n1",
        display_name="n1",
        strict_input_isolation=True,
    )
    reg = node.to_node_registration()
    assert "strict_input_isolation" not in reg
