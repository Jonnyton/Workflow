"""Compile a BranchDefinition into a LangGraph StateGraph.

Pure function: ``compile_branch(branch) -> CompiledBranch``. No side effects
beyond the returned object. Failures are programmer errors (invalid inputs)
not user errors — run ``branch.validate()`` first if needed.

The compiler synthesizes a dynamic TypedDict from ``state_schema`` with
``Annotated`` reducers per field, builds node adapters for prompt_template
and (host-approved) source_code nodes, and wires simple + conditional edges.

Design rules (from `docs/specs/community_branches_phase3.md`):
- prompt_template nodes are always safe — rendered with ``str.format_map``,
  sent via the role-based provider router.
- source_code nodes require ``approved=True`` on the NodeDefinition.
  Unapproved code raises ``UnapprovedNodeError`` at compile time, not
  runtime, so ``run_branch`` can refuse cleanly.
- Conditional edges use a predicate over a single declared output_key.
  No user-code routers in v1.
"""

from __future__ import annotations

import concurrent.futures
import logging
import operator
import re
from dataclasses import dataclass
from typing import Annotated, Any, Callable

from langgraph.graph import END, START, StateGraph

from workflow.branches import BranchDefinition, NodeDefinition

logger = logging.getLogger(__name__)


class CompilerError(Exception):
    """Raised when the compiler cannot produce a runnable graph."""


class UnapprovedNodeError(CompilerError):
    """Raised when a source_code node lacks host approval."""


class NodeTimeoutError(CompilerError):
    """Raised when a node's provider/source_code exceeds its timeout_seconds.

    Distinct from a generic CompilerError so the runner can emit a clean
    ``timeout`` event and set run status to ``failed`` with a specific
    reason, instead of the user seeing a silent stall (#61).

    ``node_id`` is exposed as an attribute so callers don't have to parse
    it out of the human-readable message.
    """

    def __init__(self, message: str, *, node_id: str = "") -> None:
        super().__init__(message)
        self.node_id = node_id


# Shared executor so every timeout-wrapped call doesn't spin up a
# fresh thread. Bounded worker count keeps a runaway graph from
# spawning unbounded threads on a slow provider.
_TIMEOUT_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None


def _get_timeout_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _TIMEOUT_EXECUTOR
    if _TIMEOUT_EXECUTOR is None:
        _TIMEOUT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="node-timeout",
        )
    return _TIMEOUT_EXECUTOR


def _run_with_timeout(
    fn: Callable[[], Any],
    *,
    timeout_s: float,
    node_id: str,
) -> Any:
    """Call ``fn()`` on a worker thread, raise NodeTimeoutError on overrun.

    When a timeout fires, the worker thread is NOT killed — Python has
    no safe way to do that. The provider call keeps running in the
    background (the provider's own subprocess/HTTP timeout is the
    backstop). We return to the graph so the overall run can fail-fast
    instead of hanging the executor.
    """
    executor = _get_timeout_executor()
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError as exc:
        raise NodeTimeoutError(
            f"Node '{node_id}' exceeded {timeout_s:.0f}s timeout. "
            "The provider call may still be running in the background; "
            "its own subprocess/HTTP timeout is the backstop.",
            node_id=node_id,
        ) from exc


_DANGEROUS_PATTERNS = (
    "os.system", "subprocess", "eval(", "exec(", "__import__",
)


def _is_cancel_exception(exc: BaseException) -> bool:
    """Duck-type check for the runner's cancel exception.

    Declared as a name-match so `graph_compiler` has no import dependency
    on `runs` (which imports `compile_branch` from here). Any exception
    class named ``RunCancelledError`` propagates past the event_sink
    catch-all; everything else is logged and swallowed.
    """
    return type(exc).__name__ == "RunCancelledError"


def _dict_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge reducer for state fields declared ``reducer="merge"``."""
    out = dict(left)
    out.update(right)
    return out


_BUILTIN_TYPES: dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "any": Any,
}


def _resolve_field_type(type_name: str) -> Any:
    """Map a state_schema ``type`` string to a Python type hint.

    Unknown types fall back to ``Any`` — the spec treats state_schema as an
    unvalidated JSON blob in Phase 2/3. Richer typing is Phase 4+.
    """
    return _BUILTIN_TYPES.get((type_name or "").strip().lower(), Any)


def _build_state_typeddict(schema: list[dict[str, Any]]) -> type:
    """Synthesize a TypedDict class from the branch's state_schema.

    Honors PLAN.md hard rule #5: fields declared with ``reducer="append"`` use
    ``Annotated[list, operator.add]``; ``reducer="merge"`` uses a shallow
    dict merger; anything else overwrites.
    """
    annotations: dict[str, Any] = {}
    for field in schema:
        name = (field.get("name") or "").strip()
        if not name:
            continue
        base_type = _resolve_field_type(field.get("type", "any"))
        reducer = (field.get("reducer") or "").strip().lower()
        if reducer == "append":
            annotations[name] = Annotated[list, operator.add]
        elif reducer == "merge":
            annotations[name] = Annotated[dict, _dict_merge]
        else:
            annotations[name] = base_type

    # Build a plain class-based TypedDict at runtime.
    # We construct it via the functional syntax because class-syntax
    # TypedDict requires name binding at class-definition time.
    from typing import TypedDict as _TypedDict

    return _TypedDict("BranchRuntimeState", annotations, total=False)  # type: ignore[operator]


# ─────────────────────────────────────────────────────────────────────────────
# Node adapters
# ─────────────────────────────────────────────────────────────────────────────


_PLACEHOLDER_RE = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")
# Matches Jinja/Handlebars-style {{ident}} placeholders. Claude.ai and many
# MCP clients emit this form by convention. We normalize to `{ident}` so
# the single regex-driven substitution below handles both forms.
_DOUBLE_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


def _normalize_placeholders(template: str) -> str:
    """Convert ``{{ident}}`` Jinja-style placeholders to Python's ``{ident}``.

    Claude.ai-authored templates typically use doubled braces by
    convention. We do the substitution ourselves (see ``_render_template``)
    so non-identifier braces — JSON examples like ``{"doc": "X"}``, code
    fences, math expressions — pass through as literal text.
    """
    if not template:
        return template
    return _DOUBLE_PLACEHOLDER_RE.sub(r"{\1}", template)


def _render_template(template: str, state: dict[str, Any]) -> str:
    """Substitute ``{ident}`` placeholders with ``state[ident]`` values.

    Unlike ``str.format_map`` we do not treat single ``{`` / ``}`` as
    special. Literal braces in JSON examples, code fences, and math
    expressions survive verbatim. Only substrings matching a valid
    identifier placeholder (``{name}``) are replaced; everything else is
    left alone.

    Raises ``KeyError`` if a valid placeholder references a state key
    that is not present — caller maps that to a ``CompilerError``.
    """
    if not template:
        return template

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in state:
            raise KeyError(key)
        return str(state[key])

    return _PLACEHOLDER_RE.sub(_sub, template)


def _missing_state_keys(template: str, state: dict[str, Any]) -> list[str]:
    normalized = _normalize_placeholders(template or "")
    refs = _PLACEHOLDER_RE.findall(normalized)
    return [k for k in refs if k not in state]


def _build_prompt_template_node(
    node: NodeDefinition,
    *,
    provider_call: Callable[..., str] | None,
    event_sink: Callable[..., None] | None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a node function that fills the prompt template and calls an
    LLM. Output is stored under the node's first ``output_keys`` entry
    (or ``<node_id>_output`` if none declared)."""

    output_key = (
        node.output_keys[0] if node.output_keys else f"{node.node_id}_output"
    )
    role = (node.model_hint or "writer").strip().lower() or "writer"
    template = node.prompt_template or ""
    timeout_s = float(node.timeout_seconds or 300.0)

    def _fn(state: dict[str, Any]) -> dict[str, Any]:
        # Normalize Jinja-style ``{{var}}`` into Python's ``{var}``.
        # Claude.ai-authored prompt_templates tend to use doubled braces
        # by convention; without this the braces are passed through to
        # the LLM as literal text.
        rendered_template = _normalize_placeholders(template)
        missing = _missing_state_keys(template, state)
        if missing:
            raise CompilerError(
                f"Node '{node.node_id}' prompt references missing "
                f"state keys: {missing}"
            )
        try:
            prompt = _render_template(rendered_template, state)
        except KeyError as exc:
            raise CompilerError(
                f"Node '{node.node_id}' prompt format failed: "
                f"missing state key {exc}"
            ) from exc

        # Emit a "starting" event BEFORE the provider call so long-running
        # LLM nodes don't look frozen to a polling client (#60). The
        # matching "ran" event fires after the call completes.
        if event_sink is not None:
            try:
                event_sink(
                    node_id=node.node_id,
                    phase="starting", role=role,
                    prompt_preview=prompt[:200],
                )
            except Exception as exc:
                if _is_cancel_exception(exc):
                    raise
                logger.exception(
                    "event_sink raised in %s (starting)", node.node_id,
                )

        if provider_call is None:
            response = f"[Mock response for {node.node_id}]"
        else:
            try:
                response = _run_with_timeout(
                    lambda: provider_call(prompt, "", role=role),
                    timeout_s=timeout_s,
                    node_id=node.node_id,
                )
            except NodeTimeoutError:
                raise
            except Exception as exc:
                logger.exception("Provider call failed in %s", node.node_id)
                raise CompilerError(
                    f"Provider call failed in node '{node.node_id}': {exc}"
                ) from exc

        if event_sink is not None:
            try:
                event_sink(
                    node_id=node.node_id,
                    phase="ran",
                    prompt=prompt, response=response, role=role,
                )
            except Exception as exc:
                if _is_cancel_exception(exc):
                    raise
                logger.exception("event_sink raised in %s", node.node_id)

        return {output_key: response}

    return _fn


def _validate_source_code(node: NodeDefinition) -> None:
    """Gate source_code nodes: require approval + no obviously dangerous
    patterns. This is belt-and-suspenders; host approval is the primary
    defense. See spec §Risks — a proper sandbox is future work."""
    if not node.approved:
        raise UnapprovedNodeError(
            f"Node '{node.node_id}' is source_code and must be approved "
            f"by the host before running."
        )
    src = node.source_code or ""
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in src:
            raise CompilerError(
                f"Node '{node.node_id}' source_code contains disallowed "
                f"pattern: '{pattern}'"
            )


def _build_source_code_node(
    node: NodeDefinition,
    *,
    event_sink: Callable[..., None] | None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a node function that exec()s the approved source_code.

    The source must define a callable named ``run(state)`` returning a dict.
    Keeps the runtime surface small and matches the existing extensions
    sandbox contract for node registration.
    """
    _validate_source_code(node)
    src = node.source_code
    timeout_s = float(node.timeout_seconds or 300.0)

    local_scope: dict[str, Any] = {}
    try:
        exec(src, {"__builtins__": __builtins__}, local_scope)  # noqa: S102
    except Exception as exc:
        raise CompilerError(
            f"Node '{node.node_id}' source_code failed to load: {exc}"
        ) from exc
    runner = local_scope.get("run")
    if not callable(runner):
        raise CompilerError(
            f"Node '{node.node_id}' source_code must define `def run(state)`."
        )

    def _fn(state: dict[str, Any]) -> dict[str, Any]:
        # #60: emit a starting event so long-running source_code nodes
        # don't look frozen to polling clients.
        if event_sink is not None:
            try:
                event_sink(
                    node_id=node.node_id,
                    phase="starting", source_code=True,
                )
            except Exception as exc:
                if _is_cancel_exception(exc):
                    raise
                logger.exception(
                    "event_sink raised in %s (starting)", node.node_id,
                )
        try:
            result = _run_with_timeout(
                lambda: runner(state),
                timeout_s=timeout_s,
                node_id=node.node_id,
            )
        except NodeTimeoutError:
            raise
        except Exception as exc:
            logger.exception("source_code node %s raised", node.node_id)
            raise CompilerError(
                f"Node '{node.node_id}' raised at runtime: {exc}"
            ) from exc
        if not isinstance(result, dict):
            raise CompilerError(
                f"Node '{node.node_id}' must return a dict, "
                f"got {type(result).__name__}."
            )
        if event_sink is not None:
            try:
                event_sink(
                    node_id=node.node_id,
                    phase="ran",
                    source_code=True, output=result,
                )
            except Exception as exc:
                if _is_cancel_exception(exc):
                    raise
                logger.exception("event_sink raised in %s", node.node_id)
        return result

    return _fn


def _build_node(
    node: NodeDefinition,
    *,
    provider_call: Callable[..., str] | None,
    event_sink: Callable[..., None] | None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Dispatch a NodeDefinition to the right adapter."""
    has_template = bool((node.prompt_template or "").strip())
    has_source = bool((node.source_code or "").strip())
    if has_template and has_source:
        raise CompilerError(
            f"Node '{node.node_id}' has both prompt_template and "
            f"source_code — exactly one must be set."
        )
    if has_source:
        return _build_source_code_node(node, event_sink=event_sink)
    if has_template:
        return _build_prompt_template_node(
            node, provider_call=provider_call, event_sink=event_sink,
        )
    # No body means a pass-through node (e.g. START/END placeholder).
    def _passthrough(state: dict[str, Any]) -> dict[str, Any]:
        if event_sink is not None:
            try:
                event_sink(node_id=node.node_id, passthrough=True)
            except Exception as exc:
                if _is_cancel_exception(exc):
                    raise
                logger.exception("event_sink raised in %s", node.node_id)
        return {}
    return _passthrough


# ─────────────────────────────────────────────────────────────────────────────
# Conditional edge predicate
# ─────────────────────────────────────────────────────────────────────────────


def _build_conditional_router(
    source_node: NodeDefinition | None,
    conditions: dict[str, str],
) -> Callable[[dict[str, Any]], str]:
    """Return a LangGraph-compatible router function.

    Reads a single declared output_key from state, maps its string value
    through ``conditions``. Fallback to the first conditional target if the
    key is missing — avoids hanging the graph on a bad node.
    """
    output_key = ""
    if source_node and source_node.output_keys:
        output_key = source_node.output_keys[0]

    fallback = next(iter(conditions.values()), END)

    def _route(state: dict[str, Any]) -> str:
        if not output_key:
            return fallback
        value = state.get(output_key, "")
        if not isinstance(value, str):
            value = str(value)
        return conditions.get(value, fallback)

    return _route


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CompiledBranch:
    """Result of compiling a BranchDefinition.

    ``state_type`` is the synthesized TypedDict — useful for validating
    user-provided inputs before invoking the graph.
    ``graph`` is the uncompiled ``StateGraph``; callers attach their own
    checkpointer via ``graph.compile(checkpointer=...)`` so the runner can
    use a shared SqliteSaver.
    ``node_ids_in_order`` is the declared node ordering from graph_nodes.
    """

    graph: StateGraph
    state_type: type
    branch: BranchDefinition
    node_ids_in_order: list[str]


def compile_branch(
    branch: BranchDefinition,
    *,
    provider_call: Callable[..., str] | None = None,
    event_sink: Callable[..., None] | None = None,
) -> CompiledBranch:
    """Compile a validated BranchDefinition into a StateGraph.

    Parameters
    ----------
    branch
        The branch to compile. Must have passed ``branch.validate()``.
    provider_call
        Synchronous LLM caller with signature ``(prompt, system, *, role)
        -> str``. When ``None``, prompt_template nodes return a mock
        string (useful for tests).
    event_sink
        Optional callable invoked after each node executes with
        per-node diagnostics. Used by the runner to record
        ``RunStepEvent`` rows.

    Returns
    -------
    CompiledBranch
        An uncompiled StateGraph + synthesized TypedDict. The caller
        attaches a checkpointer via ``graph.compile(checkpointer=...)``
        and invokes with the synthesized state type.
    """
    errors = branch.validate()
    if errors:
        raise CompilerError(
            "Cannot compile invalid branch:\n  - " + "\n  - ".join(errors)
        )

    state_type = _build_state_typeddict(branch.state_schema or [])
    graph: StateGraph = StateGraph(state_type)

    node_by_id: dict[str, NodeDefinition] = {
        n.node_id: n for n in branch.node_defs
    }

    node_ids_in_order = [gn.id for gn in branch.graph_nodes]

    # Add graph nodes to the StateGraph. Each graph_node points at a
    # node_def via ``node_def_id`` (usually the same as ``id``).
    for gn in branch.graph_nodes:
        def_id = gn.node_def_id or gn.id
        node_def = node_by_id.get(def_id)
        if node_def is None:
            raise CompilerError(
                f"Graph node '{gn.id}' references unknown node_def_id "
                f"'{def_id}'."
            )
        fn = _build_node(
            node_def, provider_call=provider_call, event_sink=event_sink,
        )
        graph.add_node(gn.id, fn)

    # Entry point: connect START to the declared entry node.
    if branch.entry_point:
        graph.add_edge(START, branch.entry_point)

    # Simple edges.
    for edge in branch.edges:
        src = START if edge.from_node == "START" else edge.from_node
        dst = END if edge.to_node == "END" else edge.to_node
        if src == START and branch.entry_point == edge.to_node:
            # Already wired via add_edge(START, entry_point) above.
            continue
        graph.add_edge(src, dst)

    # Conditional edges.
    for cedge in branch.conditional_edges:
        source_def = node_by_id.get(cedge.from_node)
        conditions = {
            label: (END if tgt == "END" else tgt)
            for label, tgt in cedge.conditions.items()
        }
        router = _build_conditional_router(source_def, conditions)
        graph.add_conditional_edges(cedge.from_node, router, conditions)

    return CompiledBranch(
        graph=graph,
        state_type=state_type,
        branch=branch,
        node_ids_in_order=node_ids_in_order,
    )
