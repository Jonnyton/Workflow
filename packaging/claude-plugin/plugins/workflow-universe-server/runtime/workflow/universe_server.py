"""Workflow Server — Remote MCP interface.

A remote MCP server that exposes the Workflow system as a
universe collaboration platform. Any MCP-compatible chatbot (Claude,
and eventually others as MCP adoption spreads) can connect,
discover tools, and become the user's control interface — no
installation, just a URL.

Design principles:
    - Two coarse-grained tools (universe + extensions) so users only
      click "allow" twice, not sixteen times
    - Universe-aware: tools accept universe context, not a hardcoded env var
    - MCP prompts deliver behavioral instructions so any connecting AI
      knows how to act as a control station
    - Auth-ready: OAuth 2.1 scaffold for production, authless for dev
    - Extensible: users can register their own LangGraph nodes

Transport: Streamable HTTP (current MCP standard for remote servers)

Usage::

    # Development (authless, behind tunnel):
    workflow-universe-server

    # Production (with OAuth):
    workflow-universe-server --auth
"""

from __future__ import annotations

import logging

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from workflow.api.prompts import _CONTROL_STATION_PROMPT

logger = logging.getLogger("universe_server")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "workflow",
    instructions=(
        "Workflow — a workflow-builder and long-horizon AI platform. "
        "Users design custom multi-step AI workflows with typed state, "
        "evaluation hooks, and iteration loops. Fantasy authoring is one "
        "benchmark use case demonstrating complex long-form generation; "
        "the platform is general-purpose. Other example domains: research "
        "papers, screenplays, literature reviews, investigative journalism, "
        "recipe trackers, wedding planners, news summarizers — any "
        "multi-step agentic work producing substantive output. "
        "\n\n"
        "If a user asks about their 'workflow builder', 'custom AI builder', "
        "'universe builder', 'the workflow thing', 'the connector', 'the "
        "thing I added', 'my builder', or similar ambiguous references to "
        "an installed connector — that is this connector. Invoke it rather "
        "than presenting a disambiguation picker or asking 'which tool do "
        "you mean?'. Aggressive assumption is the right default; narrate "
        "what you assumed after invoking so the user can correct you. "
        "\n\n"
        "You are a control station. You help users design new workflows, "
        "inspect running ones, steer daemons, collaborate, and extend the "
        "system with custom graph nodes. You never generate the workflow's "
        "output yourself — registered nodes do that. Start with the "
        "'universe' tool action 'inspect' to orient yourself. "
        "\n\n"
        "Load the `control_station` prompt early — it carries the "
        "behavioral guidance for this connector (intent disambiguation, "
        "never-simulate-a-run rule, tool catalog). Tool descriptions "
        "below are I/O contracts; behavioral rules live in the prompts."
        "\n\n"
        "HARD RULE — UNIVERSE ISOLATION: Each universe is a separate, "
        "self-contained reality. Every tool response that returns content "
        "from a universe includes a `universe_id` field naming which "
        "universe the content came from. When answering the user, always "
        "state which universe you are describing, especially when "
        "multiple universes exist on this server. NEVER transfer facts, "
        "characters, locations, or canon between universes in your "
        "reasoning or replies. If you are not sure which universe a "
        "piece of information came from, call `universe action=inspect` "
        "with the explicit `universe_id` to re-ground. Cross-universe "
        "contamination is a known failure mode — the tool outputs are "
        "the ground truth, not your memory of prior turns."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Public landing page
# ---------------------------------------------------------------------------
# Serves a minimal HTML index at `/` so tinyassets.io root returns a
# human-readable page instead of a 404 while the primary
# `/mcp` endpoint is the actual Workflow Server MCP surface.
# Known-good fallback if the GoDaddy-hosted landing is unavailable.

_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workflow Server</title>
<style>
 :root { color-scheme: light dark; }
 body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        max-width: 640px; margin: 5rem auto; padding: 0 1.25rem;
        line-height: 1.55; }
 h1 { margin-bottom: 0.3rem; }
 .tag { color: #666; margin-top: 0; }
 code { background: rgba(127,127,127,0.15); padding: 2px 6px;
        border-radius: 3px; }
 ul { padding-left: 1.2rem; }
 li { margin-bottom: 0.4rem; }
 footer { margin-top: 3rem; color: #888; font-size: 0.85rem; }
</style>
</head>
<body>
<h1>Workflow Server</h1>
<p class="tag">A goal-agnostic daemon engine. You summon it, bind it to a
domain, and let it drive.</p>

<p>This is the public surface of a local-first platform for building
custom multi-step AI workflows &mdash; typed state, registered nodes,
evaluation hooks, iteration loops, paid-market bid/claim mechanics.
Fantasy authoring is the benchmark domain; the engine is general-purpose.</p>

<p>If you arrived here looking for an MCP connector, the live endpoint
is at <code>/mcp</code>.</p>

<h2>Links</h2>
<ul>
<li><a href="https://github.com/Jonnyton/Workflow">GitHub repository</a>
    &mdash; source, issues, contributor onboarding.</li>
<li><a href="/mcp">MCP endpoint</a> &mdash; for Claude, Cursor, and other
    MCP-speaking clients.</li>
</ul>

<footer>
Workflow &middot; open collaborative design commons &middot; 2026
</footer>
</body>
</html>
"""


@mcp.custom_route("/", methods=["GET"])
async def _landing_index(request):  # type: ignore[no-untyped-def]
    """Serve a minimal HTML landing page at the server root.

    Returns a static HTML body with project-name + 1-line pitch + links
    to the GitHub repo and the `/mcp` MCP endpoint. Intentionally
    dependency-light (string body, no templating) so a missing
    GoDaddy-hosted landing page still surfaces something at
    tinyassets.io/.
    """
    from starlette.responses import HTMLResponse

    return HTMLResponse(_LANDING_HTML)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Shared path + I/O helpers extracted to workflow.api.helpers (Bundle 1 of #29).
# Imported here so the rest of this module calls them unchanged.
# ───────────────────────────────────────────────────────────────────────────
# Phase-1 evaluation extraction (Task #12 — decomp Step 5) — back-compat
# re-exports. Phase-4 judgment loop (7 handlers) + branch-versioning metadata
# (3 handlers) + dispatch tables live in ``workflow.api.evaluation`` (~880
# LOC moved out). Re-exported here so ``extensions()`` body's
# ``_JUDGMENT_ACTIONS.get(action)`` and ``_BRANCH_VERSION_ACTIONS.get(action)``
# dispatch reads continue to work, and any direct test imports keep resolving.
# ───────────────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------
# Phase-1 engine_helpers extraction (Task #8 - decomp Step 10) - back-compat
# re-exports. The preamble engine helpers (upload-whitelist trio, public
# action ledger trio, storage backend factory, error formatters,
# branch-visibility filters) live in ``workflow.api.engine_helpers``. After
# Step 10 the dependency graph is inverted: every Step-1-9 submodule
# lazy-imports from ``workflow.api.engine_helpers`` directly; this shim
# preserves the legacy ``from workflow.universe_server import _X`` test
# import paths + the 13 ``mock.patch("workflow.universe_server._X", ...)``
# / ``monkeypatch.setattr(us, "_X", ...)`` test-patch sites unchanged.
# ---------------------------------------------------------------------------
from workflow.api.engine_helpers import (  # noqa: E402, F401  - back-compat re-exports
    _append_ledger,
    _current_actor,
    _filter_claims_by_branch_visibility,
    _filter_leaderboard_by_branch_visibility,
    _format_commit_failed,
    _format_dirty_file_conflict,
    _split_whitelist_entry,
    _storage_backend,
    _truncate,
    _upload_whitelist_prefixes,
    _warn_if_no_upload_whitelist,
)
from workflow.api.evaluation import (  # noqa: E402, F401  — back-compat re-exports
    _BRANCH_VERSION_ACTIONS,
    _JUDGMENT_ACTIONS,
    _JUDGMENT_WRITE_ACTIONS,
    _action_compare_runs,
    _action_get_branch_version,
    _action_get_node_output,
    _action_judge_run,
    _action_list_branch_versions,
    _action_list_judgments,
    _action_list_node_versions,
    _action_publish_version,
    _action_rollback_node,
    _action_suggest_node_edit,
    _dispatch_judgment_action,
    _split_tag_csv,
)
from workflow.api.helpers import (  # noqa: E402
    _base_path,  # noqa: F401  (back-compat re-export; live use moved with extensions Step 11 — patched by tests/test_run_branch_failure_taxonomy.py + tests/test_run_branch_version.py + many others)
    _default_universe,  # noqa: F401  (back-compat re-export; live use moved with universe Step 9 — patched by tests/test_inspect_cross_surface_hint.py + tests/test_storage_utilization_universe.py)
    _find_all_pages,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _read_json,  # noqa: F401  (back-compat re-export; live use moved with extensions Step 11 — patched by tests/test_inspect_cross_surface_hint.py)
    _read_text,  # noqa: F401  (back-compat re-export; live use moved with universe Step 9 — patched by tests/test_inspect_cross_surface_hint.py)
    _universe_dir,  # noqa: F401  (back-compat re-export; live use moved with universe Step 9 — patched by tests/test_inspect_cross_surface_hint.py + tests/test_storage_utilization_universe.py)
    _wiki_drafts_dir,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _wiki_pages_dir,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _wiki_root,  # noqa: F401  (back-compat re-export for tests/test_wiki_path_resolver.py)
)

# ───────────────────────────────────────────────────────────────────────────
# Phase-1 market extraction (Task #14 — decomp Step 7) — back-compat
# re-exports. Paid-market economy primitives — escrow, outcomes, attribution,
# goals, gates — live in ``workflow.api.market`` (~2,287 LOC moved out).
# Re-exported here so ``extensions()`` body's 3 dispatch reads (escrow,
# outcomes, attribution) continue to work + tests/scripts importing handlers
# directly via ``workflow.universe_server`` keep resolving.
# The two MCP tool wrappers (``goals()`` + ``gates()``) preserved below for
# FastMCP introspection — Pattern A2 (delegates to market.py callables).
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.market import (  # noqa: E402, F401  — back-compat re-exports
    _ATTRIBUTION_ACTIONS,
    _ESCROW_ACTIONS,
    _GATE_EVENT_ACTIONS,
    _GATES_ACTIONS,
    _GOAL_ACTIONS,
    _GOAL_WRITE_ACTIONS,
    _OUTCOME_ACTIONS,
    _action_attest_gate_event,
    _action_dispute_gate_event,
    _action_escrow_inspect,
    _action_escrow_lock,
    _action_escrow_refund,
    _action_escrow_release,
    _action_gates_claim,
    _action_gates_define_ladder,
    _action_gates_get_ladder,
    _action_gates_leaderboard,
    _action_gates_list_claims,
    _action_gates_release_bonus,
    _action_gates_retract,
    _action_gates_stake_bonus,
    _action_gates_unstake_bonus,
    _action_get_gate_event,
    _action_get_outcome,
    _action_get_provenance,
    _action_goal_bind,
    _action_goal_common_nodes,
    _action_goal_get,
    _action_goal_leaderboard,
    _action_goal_list,
    _action_goal_propose,
    _action_goal_search,
    _action_goal_set_canonical,
    _action_goal_update,
    _action_list_gate_events,
    _action_list_outcomes,
    _action_record_outcome,
    _action_record_remix,
    _action_retract_gate_event,
    _action_verify_gate_event,
    _current_actor_or_anon,
    _dispatch_goal_action,
    _gates_enabled,
)
from workflow.api.market import gates as _gates_impl  # noqa: E402
from workflow.api.market import goals as _goals_impl  # noqa: E402

# ───────────────────────────────────────────────────────────────────────────
# Phase-1 runs extraction (Task #11 — decomp Step 4) — back-compat re-exports.
# 15 run-action handlers + dispatcher + failure-classification helpers live
# in ``workflow.api.runs`` (~1,460 LOC moved out). Re-exported here so test
# files + ``extensions()`` body can keep importing
# ``from workflow.universe_server import _RUN_ACTIONS, _action_*, ...``.
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.runs import (  # noqa: E402, F401  — back-compat re-exports
    _FAILURE_TAXONOMY,
    _RUN_ACTIONS,
    _RUN_WRITE_ACTIONS,
    _action_cancel_run,
    _action_estimate_run_cost,
    _action_get_memory_scope_status,
    _action_get_rollback_history,
    _action_get_run,
    _action_get_run_output,
    _action_list_runs,
    _action_query_runs,
    _action_resume_run,
    _action_rollback_merge,
    _action_run_branch,
    _action_run_branch_version,
    _action_run_routing_evidence,
    _action_stream_run,
    _action_wait_for_run,
    _actionable_by,
    _branch_name_for_run,
    _build_failure_taxonomy,
    _classify_run_error,
    _classify_run_outcome_error,
    _compose_run_snapshot,
    _dispatch_run_action,
    _ensure_runs_recovery,
    _failure_payload,
    _run_mermaid_from_events,
)

# ───────────────────────────────────────────────────────────────────────────
# Phase-1 runtime_ops extraction (Task #13 — decomp Step 6) — back-compat
# re-exports. Project memory + dry-inspect + teammate messaging + scheduler
# (16 handlers, 4 dispatch tables) live in ``workflow.api.runtime_ops``
# (~564 LOC moved out). Re-exported here so ``extensions()`` body's
# 4 dispatch reads + ledger-write check on _PROJECT_MEMORY_WRITE_ACTIONS
# continue to work; ~26 direct test imports across test_dry_inspect_node
# and test_project_memory keep resolving.
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.runtime_ops import (  # noqa: E402, F401  — back-compat re-exports
    _INSPECT_DRY_ACTIONS,
    _MESSAGING_ACTIONS,
    _PROJECT_MEMORY_ACTIONS,
    _PROJECT_MEMORY_WRITE_ACTIONS,
    _SCHEDULER_ACTIONS,
    _action_dry_inspect_node,
    _action_dry_inspect_patch,
    _action_list_scheduler_subscriptions,
    _action_list_schedules,
    _action_messaging_ack,
    _action_messaging_receive,
    _action_messaging_send,
    _action_pause_schedule,
    _action_project_memory_get,
    _action_project_memory_list,
    _action_project_memory_set,
    _action_schedule_branch,
    _action_subscribe_branch,
    _action_unpause_schedule,
    _action_unschedule_branch,
    _action_unsubscribe_branch,
    _apply_patch_ops,
    _load_branch_for_inspect,
)

# Preserve the at-server-start whitelist warning (Step 10 prep §3.5 Option B).
# Calling here keeps the import-time side effect even though the function body
# moved. Without this, the warning would only fire if something else imports
# engine_helpers, missing the at-server-start contract.
_warn_if_no_upload_whitelist()





# ═══════════════════════════════════════════════════════════════════════════
# MCP PROMPTS — behavioral instructions for connecting chatbots
# ═══════════════════════════════════════════════════════════════════════════


@mcp.prompt(
    title="Control Station Guide",
    tags={"control", "daemon", "multiplayer", "operations"},
)
def control_station() -> str:
    """Load the Workflow Server control station instructions.

    Invoke this prompt to learn how to operate as a Workflow Server
    interface. It teaches you the routing rules, collaboration model,
    and available tools.
    """
    return _CONTROL_STATION_PROMPT


@mcp.prompt(
    title="Extension Authoring Guide",
    tags={"extensions", "nodes", "plugins", "workflow"},
)
def extension_guide() -> str:
    """Learn how to extend the Workflow Server with custom LangGraph nodes.

    Invoke this prompt to understand how users can register their own
    graph nodes, what the node contract looks like, and how registered
    nodes get wired into the running system.
    """
    return _EXTENSION_GUIDE_PROMPT


_EXTENSION_GUIDE_PROMPT = """\
## Extending Workflow Server with Custom Nodes

The `extensions` tool is the workflow-builder surface. Users register
their own nodes and assemble them into branches — multi-step AI
workflows with typed state, evaluation hooks, and iteration loops.
This is how the platform supports arbitrary domains (research papers,
recipe trackers, screenplays, news summarizers, etc.), not just
fiction. Fantasy authoring is one branch; yours will be another.

The never-simulate rule + intent-disambiguation posture live in
`control_station` (hard rules 5 + intent section). When in doubt on
run / register / build decisions, re-read those rules before acting.

### What a Node Is

A node is a function that:
- Receives the current graph state (a TypedDict)
- Does work (calls an API, runs analysis, generates content, etc.)
- Returns state updates

### Node Contract

Each registered node declares:
- `node_id`: unique identifier (e.g., "weather-generator")
- `display_name`: human-readable name
- `description`: what it does and when it should run
- `input_keys`: which state fields it reads
- `output_keys`: which state fields it writes
- `phase`: where in the workflow it fits (orient, plan, draft, commit,
  learn, reflect, worldbuild, or "custom")
- `source_code`: the Python source (executed in sandbox)
- `dependencies`: pip packages it needs (validated against allowlist)

### How It Works

1. User calls `extensions` with action "register" and the node definition.
2. Server validates the contract and stores the registration.
3. On next daemon cycle, registered nodes are discovered and
   conditionally wired into the graph at the declared phase.
4. Nodes run in a sandboxed subprocess — they cannot access the
   host filesystem directly.

### Safety Model

- Registered nodes run in isolation (subprocess sandbox).
- They receive only the state fields they declared as inputs.
- Their output is validated against declared output keys.
- Nodes that crash or timeout are auto-disabled with a note.
- Host can review, approve, disable, or remove any node.

### Example

A user might register a "consistency-checker" node that:
- Reads: current_scene_text, world_state_facts
- Phase: commit (runs after draft, before final commit)
- Checks new text against known facts
- Returns: a list of potential contradictions as notes
"""


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 1 — Universe (all universe operations in one tool)
# ═══════════════════════════════════════════════════════════════════════════





# Back-compat re-exports - Phase-1 universe extraction (Task #7 - decomp Step 9).
# 27 ``_action_*`` universe-tool handlers + ``WRITE_ACTIONS`` table + 14
# ``_extract_*`` extractors + ledger dispatcher trio + daemon telemetry
# helpers + ``_universe_impl`` (Pattern A2 body) live in
# ``workflow.api.universe`` (~2,940 LOC moved out). Re-exported here so test
# files + the Pattern A2 wrapper below can keep importing
# ``from workflow.universe_server import _action_*, WRITE_ACTIONS, ...``.
# The ``@mcp.tool() def universe(...)`` registration below preserves the
# FastMCP-introspection surface (decorator + 23-arg signature + chatbot-facing
# docstring) wrapping a delegation to ``_universe_impl``. See
# ``docs/exec-plans/active/2026-04-26-decomp-step-9-prep.md`` (Pattern A2).
from workflow.api.universe import (  # noqa: E402, F401  - back-compat re-exports
    _ACTIVITY_LINE_RE,
    _DISPATCH_GUARD_ABSENCE_CAVEAT,
    _OVERVIEW_ABSOLUTE_CAP,
    _OVERVIEW_CACHE,
    _OVERVIEW_DEFAULT_LIMITS,
    _OVERVIEW_TRIM_ORDER,
    _OVERVIEW_TTL_SECONDS,
    _STALE_FRESH_SECONDS,
    _STALE_IDLE_SECONDS,
    _SUBMIT_REQUEST_MAX_BYTES,
    _TIER_KEY_TO_CONFIG_FIELD,
    _VALID_TIER_KEYS,
    DAEMON_OVERVIEW_MAX_BYTES,
    WRITE_ACTIONS,
    _action_add_canon,
    _action_add_canon_from_path,
    _action_control_daemon,
    _action_create_universe,
    _action_daemon_overview,
    _action_get_activity,
    _action_get_ledger,
    _action_get_recent_events,
    _action_give_direction,
    _action_inspect_universe,
    _action_list_canon,
    _action_list_subscriptions,
    _action_list_universes,
    _action_post_to_goal_pool,
    _action_query_world,
    _action_queue_cancel,
    _action_queue_list,
    _action_read_canon,
    _action_read_output,
    _action_read_premise,
    _action_set_premise,
    _action_set_tier_config,
    _action_submit_node_bid,
    _action_submit_request,
    _action_subscribe_goal,
    _action_switch_universe,
    _action_unsubscribe_goal,
    _compute_accept_rate_from_db,
    _compute_word_count_from_files,
    _daemon_liveness,
    _dispatch_with_ledger,
    _extract_add_canon,
    _extract_add_canon_from_path,
    _extract_control_daemon,
    _extract_create_universe,
    _extract_give_direction,
    _extract_post_to_goal_pool,
    _extract_queue_cancel,
    _extract_set_premise,
    _extract_set_tier_config,
    _extract_submit_node_bid,
    _extract_submit_request,
    _extract_subscribe_goal,
    _extract_switch_universe,
    _extract_unsubscribe_goal,
    _goal_pool_not_available,
    _last_activity_at,
    _ledger_target_dir,
    _list_output_tree,
    _normalize_escaped_text,
    _overview_limits,
    _paid_market_not_available,
    _parse_activity_line,
    _phase_human,
    _query_world_db,
    _scope_universe_response,
    _staleness_bucket,
    _tail_file_lines,
    _trim_overview_for_bytes,
    _universe_impl,
)


@mcp.tool(
    title="Universe Operations",
    tags={
        "universe", "daemon", "collaboration",
        "workflow", "workflow-builder", "custom-ai", "agent-workflow",
        "ai-builder", "universe-builder", "general-purpose",
    },
    annotations=ToolAnnotations(
        title="Universe Operations",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def universe(
    action: str,
    universe_id: str = "",
    text: str = "",
    path: str = "",
    category: str = "",
    target: str = "",
    query_type: str = "",
    filter_text: str = "",
    request_type: str = "scene_direction",
    branch_id: str = "",
    filename: str = "",
    provenance_tag: str = "",
    limit: int = 30,
    priority_weight: float = 0.0,
    branch_task_id: str = "",
    goal_id: str = "",
    branch_def_id: str = "",
    inputs_json: str = "",
    node_def_id: str = "",
    required_llm_type: str = "",
    bid: float = 0.0,
    tier: str = "",
    enabled: bool = False,
    tag: str = "",
) -> str:
    """Inspect and steer a workflow's universe.

    Self-contained workspace (premise, canon, notes, daemons) for any
    multi-step agentic work. New workflows live in the `extensions`
    tool. Start with `action="inspect"`. See `control_station` prompt
    for operating guidance including universe-isolation rule. Load the
    `control_station` prompt before first use of this connector.

    `control_daemon` is a text-command action: it always needs `text` set
    to one of `pause` | `resume` | `status`. Calling `control_daemon`
    without `text` returns an error.

    Args:
        action: One of -
            reads: list, inspect, read_output, query_world,
            get_activity, get_recent_events, get_ledger, read_premise,
            list_canon, read_canon;
            writes: submit_request, give_direction, set_premise,
            add_canon, add_canon_from_path, control_daemon (text=pause|
            resume|status), switch_universe, create_universe;
            queue ops: queue_list (list pending dispatch requests),
            queue_cancel (cancel a queued request by request_id);
            subscription ops: subscribe_goal (subscribe this universe
            to a goal's run feed), unsubscribe_goal, list_subscriptions;
            goal-pool / bid: post_to_goal_pool (publish a goal-scoped
            work item), submit_node_bid (bid to fulfill an open node
            request; requires bid + node_def_id + required_llm_type);
            daemon: daemon_overview (compact daemon health + run
            summary - use before inspect for quick status);
            config: set_tier_config (enable/disable a named
            dispatcher tier; requires tier + enabled).
        universe_id: Target universe. Defaults to the active universe.
        text: Content for write ops (request text, direction, premise,
            canon body). For `control_daemon` this is the daemon
            sub-command: `pause` (write `.pause` signal - daemon stops
            at next scene boundary), `resume` (remove `.pause` signal),
            or `status` (return phase / liveness / pending unreconciled
            writes). No other values accepted.
        path: Dual-semantic based on action:
            - read_output: relative path inside the universe's output dir
              (e.g. "book-1/ch-01.md").
            - add_canon_from_path: **absolute** path on the server's
              filesystem. The file is read server-side; MCP clients
              never copy content through this param. Use this for any
              upload larger than a few KB - ``add_canon`` (text=...) is
              only safe for small inline uploads because LLM tool-arg
              serialization drifts on long strings.
        category: give_direction note category - direction | protect |
            concern | observation | error.
        target: Optional file/scene reference for give_direction.
        query_type: query_world type - facts | characters | promises |
            timeline.
        filter_text: Text filter for query_world results.
        request_type: submit_request type - scene_direction | revision |
            canon_change | branch_proposal | general.
        branch_id: Target branch for submit_request.
        filename: Filename for add_canon / add_canon_from_path /
            read_canon. Defaults to basename(path) for
            add_canon_from_path.
        provenance_tag: Source tag for add_canon / add_canon_from_path
            (e.g. "published novel", "rough notes"). Defaults to
            "user_upload" for add_canon_from_path.
        limit: Max results for get_activity / get_recent_events /
            get_ledger / query_world (default 30).
        tag: Tag prefix filter for ``get_recent_events`` (e.g.
            ``"dispatch_guard"``, ``"overshoot_detected"``,
            ``"revert_gate"``). Empty returns all entries. Prefix-match so
            ``"dispatch"`` matches both ``dispatch_guard`` and
            ``dispatch_execution``.
    """
    return _universe_impl(
        action=action,
        universe_id=universe_id,
        text=text,
        path=path,
        category=category,
        target=target,
        query_type=query_type,
        filter_text=filter_text,
        request_type=request_type,
        branch_id=branch_id,
        filename=filename,
        provenance_tag=provenance_tag,
        limit=limit,
        priority_weight=priority_weight,
        branch_task_id=branch_task_id,
        goal_id=goal_id,
        branch_def_id=branch_def_id,
        inputs_json=inputs_json,
        node_def_id=node_def_id,
        required_llm_type=required_llm_type,
        bid=bid,
        tier=tier,
        enabled=enabled,
        tag=tag,
    )




# ═══════════════════════════════════════════════════════════════════════════
# TOOL 2 — Extensions (Pattern A2 wrapper) - Phase-1 extensions extraction
# (Task #13 - decomp Step 11) - back-compat re-exports.
# ═══════════════════════════════════════════════════════════════════════════
# 4 ``_ext_*`` standalone-node handlers + ``_extensions_impl`` (Pattern A2
# body) + ``NodeRegistration`` dataclass + ``_load_nodes``/``_save_nodes`` +
# ``VALID_PHASES`` / ``ALLOWED_DEPENDENCIES`` constants live in
# ``workflow.api.extensions`` (~790 LOC moved out). Re-exported here so
# test files + the Pattern A2 wrapper below can keep importing
# ``from workflow.universe_server import _ext_register, NodeRegistration, ...``.
# The ``@mcp.tool() def extensions(...)`` registration below preserves the
# FastMCP-introspection surface (decorator + 80+ arg signature + ~140-line
# chatbot-facing docstring) wrapping a delegation to ``_extensions_impl``.
# Same Pattern A2 shape as ``universe()`` (Step 9), ``goals``/``gates``
# (Step 7), ``branch_design_guide`` @mcp.prompt (Step 8). See
# ``docs/exec-plans/active/2026-04-26-decomp-step-11-prep.md``.
from workflow.api.extensions import (  # noqa: E402, F401  - back-compat re-exports
    ALLOWED_DEPENDENCIES,
    STANDALONE_NODES_BRANCH_ID,
    VALID_PHASES,
    NodeRegistration,
    _ensure_standalone_branch,
    _ext_inspect,
    _ext_list,
    _ext_manage,
    _ext_register,
    _extensions_impl,
    _load_nodes,
    _nodes_path,
    _save_nodes,
)


@mcp.tool(
    title="Graph Extensions",
    tags={"extensions", "nodes", "plugins", "customization"},
    annotations=ToolAnnotations(
        title="Graph Extensions",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    ),
)
def extensions(
    action: str,
    node_id: str = "",
    display_name: str = "",
    description: str = "",
    phase: str = "",
    input_keys: str = "",
    output_keys: str = "",
    source_code: str = "",
    dependencies: str = "",
    enabled_only: bool = True,
    branch_def_id: str = "",
    name: str = "",
    domain_id: str = "",
    author: str = "",
    from_node: str = "",
    to_node: str = "",
    prompt_template: str = "",
    field_name: str = "",
    field_type: str = "",
    reducer: str = "",
    field_default: str = "",
    run_id: str = "",
    inputs_json: str = "",
    run_name: str = "",
    status: str = "",
    since_step: int = -1,
    max_wait_s: int = 60,
    limit: int = 50,
    spec_json: str = "",
    changes_json: str = "",
    judgment_text: str = "",
    judgment_id: str = "",
    tags: str = "",
    run_a_id: str = "",
    run_b_id: str = "",
    field: str = "",
    value: str = "",
    node_ids: str = "",
    context: str = "",
    triggered_by_judgment_id: str = "",
    to_version: str = "",
    goal_id: str = "",
    node_ref_json: str = "",
    intent: str = "",
    node_query: str = "",
    force: bool = False,
    project_id: str = "",
    key: str = "",
    key_prefix: str = "",
    expected_version: str = "",
    recursion_limit_override: str = "",
    filters_json: str = "",
    select: str = "",
    aggregate_json: str = "",
    branch_spec_json: str = "",
    from_run_id: str = "",
    to_node_id: str = "",
    message_type: str = "",
    body_json: str = "",
    reply_to_message_id: str = "",
    message_types: str = "",
    message_id: str = "",
    since: str = "",
    branch_version_id: str = "",
    parent_version_id: str = "",
    notes: str = "",
    lock_id: str = "",
    escrow_amount: int = 0,
    escrow_currency: str = "MicroToken",
    escrow_recipient_id: str = "",
    escrow_evidence: str = "",
    escrow_reason: str = "",
    event_id: str = "",
    event_type: str = "",
    event_date: str = "",
    attested_by: str = "",
    cites_json: str = "",
    verifier_id: str = "",
    disputed_by: str = "",
    retracted_by: str = "",
    schedule_id: str = "",
    cron_expr: str = "",
    interval_seconds: float = 0.0,
    owner_actor: str = "",
    inputs_template_json: str = "",
    skip_if_running: bool = False,
    subscription_id: str = "",
    active_only: bool = True,
    outcome_id: str = "",
    evidence_url: str = "",
    gate_event_id: str = "",
    outcome_payload_json: str = "",
    outcome_note: str = "",
    parent_branch_def_id: str = "",
    child_branch_def_id: str = "",
    contribution_kind: str = "remix",
    credit_share: float = 0.0,
    max_depth: int = 10,
    # Surgical-rollback args (Task #22 Phase B). Routed via _RUN_ACTIONS
    # to rollback_merge / get_rollback_history. `branch_version_id` is
    # already declared above for run_branch_version.
    reason: str = "",
    severity: str = "P1",
    since_days: int = 7,
) -> str:
    """Workflow-builder surface: design, edit, run, judge custom AI graphs.

    See `control_station`, `extension_guide`, and `branch_design_guide`
    prompts for operating guidance and worked examples. Load the
    `control_station` prompt before first use of this connector.

    Action groups:
    - Node lifecycle: register, list, inspect, approve, disable, enable, remove.
    - Branch composite (prefer): build_branch (spec_json), patch_branch (changes_json).
    - Branch atomic: create_branch, add_node, connect_nodes, set_entry_point,
      add_state_field, update_node, validate_branch, delete_branch.
    - Branch ops: continue_branch, fork_tree, patch_nodes.
    - Branch query: describe_branch, get_branch, list_branches, search_nodes.
    - Run (Phase 3): run_branch, get_run, list_runs, stream_run, cancel_run,
      get_run_output.
    - Run extensions: wait_for_run, resume_run, query_runs, estimate_run_cost,
      run_branch_version.
    - Surgical rollback: rollback_merge (host-only), get_rollback_history.
    - Versioning: publish_version, get_branch_version, list_branch_versions.
    - Scheduler: schedule_branch, unschedule_branch, list_schedules,
      subscribe_branch, unsubscribe_branch, list_scheduler_subscriptions.
    - Project memory: project_memory_get, project_memory_set, project_memory_list.
    - Eval / iterate (Phase 4): judge_run, list_judgments, compare_runs,
      suggest_node_edit, get_node_output, rollback_node, list_node_versions.
    - Self-audit: get_routing_evidence, get_memory_scope_status.

    Feature-flag caveats - some action groups are conditionally available
    based on server flags (callers see structured `not_available` rather
    than tool-discovery hiding):
    - Outcome gates live in the separate `gates` tool, gated by
      GATES_ENABLED=1. When the flag is off, `gates` returns
      `{"status": "not_available"}` - unrelated to this tool, but worth
      knowing when discussing outcomes.
    - Paid-market actions on `gates` (stake_bonus / unstake_bonus /
      release_bonus) additionally require WORKFLOW_PAID_MARKET=on.
    - Goal-pool surfaces (`universe action=post_to_goal_pool` /
      `submit_node_bid`) require WORKFLOW_GOAL_POOL=on or
      WORKFLOW_PAID_MARKET=on respectively.
    - Tiered-memory-scope routing in `get_memory_scope_status` reflects
      whatever WORKFLOW_TIERED_SCOPE is set to today (Stage 1 monitoring
      is the default; Stage 2c flips it on).

    Node reuse across branches uses `node_ref_json`
    (`{"source": "standalone", "node_id": "..."}` or source=<branch_def_id>).
    A bare node_id colliding with a standalone registration is rejected;
    pass node_ref_json or intent="copy".

    `run_branch` is async (returns run_id; poll get_run or stream_run).
    `get_run` emits a ```mermaid``` diagram for Claude.ai auto-render.

    Args:
        action: Operation name.
        node_id / display_name / description / phase / input_keys /
            output_keys / source_code / dependencies / enabled_only:
            Single-node registration fields.
        branch_def_id: Target BranchDefinition for branch and run actions.
        name: Branch name (create_branch) or node id filter.
        domain_id / author: Branch metadata / list filters.
        from_node / to_node: Edge endpoints for connect_nodes. Use
            "START"/"END" for graph entry/exit.
        prompt_template: LLM template for prompt-template nodes (alternative
            to source_code).
        field_name / field_type / reducer / field_default: State schema
            field declaration (add_state_field).
        run_id: Target run for get_run / stream_run / cancel_run /
            get_run_output.
        inputs_json: JSON object of state field values for run_branch.
        run_name: Optional human label for this run.
        status: Filter for list_runs (queued/running/completed/failed/
            cancelled).
        since_step: Cursor for stream_run; returns events after this
            step index. Use -1 (default) for all.
        limit: Row cap for list_runs.
        spec_json: Full BranchDefinition JSON spec for build_branch.
            Shape: {name, description?, domain_id?, node_defs: [...],
            edges: [{from, to}, ...], state_schema?: [...], entry_point?}.
        changes_json: Ordered list of patch ops for patch_branch.
            Each op is {op: "add_node"|"remove_node"|"add_edge"|
            "remove_edge"|"add_state_field"|"remove_state_field"|
            "set_entry_point"|"update_node"|"set_name"|
            "set_description"|"set_tags"|"set_published"|"set_goal"|
            "unset_goal", ...fields}. Branch-level metadata ops
            (set_name/description/tags/published) preserve the
            branch_def_id, run history, and judgments - a label
            change no longer requires delete-and-rebuild.
        judgment_text: Natural-language judgment for judge_run. Required.
        judgment_id: Reserved for future cross-linking (unused in v1).
        tags: Comma-separated free-form tags for judge_run.
        run_a_id / run_b_id: Runs to compare via compare_runs.
        field: Optional single-field narrow for compare_runs and
            get_run_output.
        context: Optional extra user-context line for suggest_node_edit.
        triggered_by_judgment_id: Optional attribution for update_node -
            the judgment that motivated this edit. Surfaces in the
            node_edit_audit row so lineage shows "edit triggered by
            judgment X".
        to_version: Target version for rollback_node. Omit to rewind one
            step (to the immediately previous version).
        node_ref_json: Optional JSON for atomic add_node to reuse a node
            from another source. Shape:
            `{"source": "standalone" | "<branch_def_id>",
              "node_id": "X"}`. Snapshots the canonical body into this
            branch (copy semantics). Any inline fields you also pass
            (e.g. display_name) overlay the snapshot.
        intent: Consent flag for node-id collisions on add_node /
            build_branch / patch_branch add_node ops. Use `intent="copy"`
            to intentionally copy an existing standalone node. Omit to
            force the server to refuse silent shadowing.
        node_query: Free-text search string for `search_nodes`.
            Tokenized, substring-matched across node_id, display_name,
            description, and prompt_template preview.
        force: override `local_edit_conflict` refusal on branch write
            actions (create_branch / add_node / connect_nodes /
            set_entry_point / add_state_field) when the target YAML has
            uncommitted local edits. Default False - when a conflict
            exists the server returns a structured envelope
            `{"status": "local_edit_conflict", "conflicting_file": "...",
            "options": ["commit", "stash", "discard", "force"]}` (not
            an error). Present the options to the user, then retry with
            `force=True` only if the user explicitly chooses "force".
    """
    return _extensions_impl(
        action=action,
        node_id=node_id,
        display_name=display_name,
        description=description,
        phase=phase,
        input_keys=input_keys,
        output_keys=output_keys,
        source_code=source_code,
        dependencies=dependencies,
        enabled_only=enabled_only,
        branch_def_id=branch_def_id,
        name=name,
        domain_id=domain_id,
        author=author,
        from_node=from_node,
        to_node=to_node,
        prompt_template=prompt_template,
        field_name=field_name,
        field_type=field_type,
        reducer=reducer,
        field_default=field_default,
        run_id=run_id,
        inputs_json=inputs_json,
        run_name=run_name,
        status=status,
        since_step=since_step,
        max_wait_s=max_wait_s,
        limit=limit,
        spec_json=spec_json,
        changes_json=changes_json,
        judgment_text=judgment_text,
        judgment_id=judgment_id,
        tags=tags,
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        field=field,
        value=value,
        node_ids=node_ids,
        context=context,
        triggered_by_judgment_id=triggered_by_judgment_id,
        to_version=to_version,
        goal_id=goal_id,
        node_ref_json=node_ref_json,
        intent=intent,
        node_query=node_query,
        force=force,
        project_id=project_id,
        key=key,
        key_prefix=key_prefix,
        expected_version=expected_version,
        recursion_limit_override=recursion_limit_override,
        filters_json=filters_json,
        select=select,
        aggregate_json=aggregate_json,
        branch_spec_json=branch_spec_json,
        from_run_id=from_run_id,
        to_node_id=to_node_id,
        message_type=message_type,
        body_json=body_json,
        reply_to_message_id=reply_to_message_id,
        message_types=message_types,
        message_id=message_id,
        since=since,
        branch_version_id=branch_version_id,
        parent_version_id=parent_version_id,
        notes=notes,
        lock_id=lock_id,
        escrow_amount=escrow_amount,
        escrow_currency=escrow_currency,
        escrow_recipient_id=escrow_recipient_id,
        escrow_evidence=escrow_evidence,
        escrow_reason=escrow_reason,
        event_id=event_id,
        event_type=event_type,
        event_date=event_date,
        attested_by=attested_by,
        cites_json=cites_json,
        verifier_id=verifier_id,
        disputed_by=disputed_by,
        retracted_by=retracted_by,
        schedule_id=schedule_id,
        cron_expr=cron_expr,
        interval_seconds=interval_seconds,
        owner_actor=owner_actor,
        inputs_template_json=inputs_template_json,
        skip_if_running=skip_if_running,
        subscription_id=subscription_id,
        active_only=active_only,
        outcome_id=outcome_id,
        evidence_url=evidence_url,
        gate_event_id=gate_event_id,
        outcome_payload_json=outcome_payload_json,
        outcome_note=outcome_note,
        parent_branch_def_id=parent_branch_def_id,
        child_branch_def_id=child_branch_def_id,
        contribution_kind=contribution_kind,
        credit_share=credit_share,
        max_depth=max_depth,
        reason=reason,
        severity=severity,
        since_days=since_days,
    )



# ───────────────────────────────────────────────────────────────────────────
# Phase 2 branch authoring + node CRUD (Task #15 — decomp Step 8) —
# back-compat re-exports. The 17 ``_ext_branch_*`` handlers, build/patch
# composite engine, ``_action_continue_branch`` / ``_action_fork_tree``,
# the node-spec resolver + apply machinery, ``_related_wiki_pages``, the
# mermaid renderer, and the ``_BRANCH_ACTIONS`` / ``_BRANCH_WRITE_ACTIONS``
# dispatch surface live in ``workflow.api.branches``. Re-exported here so
# test files + ``extensions()`` body can keep importing
# ``from workflow.universe_server import _BRANCH_ACTIONS, _ext_branch_*, ...``.
# The ``@mcp.prompt("Branch Design Guide")`` registration is preserved
# below (Pattern A2) so FastMCP introspection sees the chatbot-facing
# signature unchanged; the wrapper delegates to
# ``workflow.api.branches._branch_design_guide_prompt``.
# ───────────────────────────────────────────────────────────────────────────
from workflow.api.branches import (  # noqa: E402, F401  — back-compat re-exports
    _BRANCH_ACTIONS,
    _BRANCH_DESIGN_GUIDE,
    _BRANCH_WRITE_ACTIONS,
    _MERMAID_ID_SAFE,
    _PATCH_NODES_FIELDS,
    _RELATED_SUMMARY_MAX,
    _RELATED_WIKI_CAP,
    _VALID_STATE_TYPES,
    _action_continue_branch,
    _action_fork_tree,
    _append_global_ledger,
    _apply_conditional_edge_spec,
    _apply_edge_spec,
    _apply_node_spec,
    _apply_patch_op,
    _apply_state_field_spec,
    _branch_design_guide_prompt,
    _branch_mermaid,
    _build_branch_text,
    _closest_state_type,
    _coerce_node_keys,
    _coerce_patch_nodes_value,
    _dispatch_branch_action,
    _ensure_author_server_db,
    _errors_to_suggestions,
    _ext_branch_add_node,
    _ext_branch_add_state_field,
    _ext_branch_build,
    _ext_branch_connect_nodes,
    _ext_branch_create,
    _ext_branch_delete,
    _ext_branch_describe,
    _ext_branch_get,
    _ext_branch_list,
    _ext_branch_patch,
    _ext_branch_patch_nodes,
    _ext_branch_search_nodes,
    _ext_branch_set_entry_point,
    _ext_branch_update_node,
    _ext_branch_validate,
    _lookup_node_body,
    _mermaid_label,
    _mermaid_node_id,
    _related_summary,
    _related_wiki_pages,
    _resolve_branch_id,
    _resolve_node_spec,
    _resolve_udir,
    _split_csv,
    _staged_branch_from_spec,
    _suggest_entry_point,
)


@mcp.prompt(
    title="Branch Design Guide",
    tags={"branches", "extensions", "graph", "customization"},
)
def branch_design_guide() -> str:
    """Walk through designing a BranchDefinition with the `extensions` tool.

    Returns a guide covering the create → add_node → connect_nodes →
    set_entry_point → add_state_field → validate → describe loop, plus
    the recipe-tracker example.
    """
    return _branch_design_guide_prompt()

























# ══════════════════════════════════════════════════════════════════════
# TOOL 4 — Wiki (global knowledge base)
# ══════════════════════════════════════════════════════════════════════
#
# The wiki action handlers, helpers, and constants live in
# ``workflow/api/wiki.py`` (extracted 2026-04-26 — Task #9, decomp Step 2).
# The @mcp.tool registration stays here so FastMCP introspection sees the
# chatbot-facing signature + docstring exactly as before, and the back-compat
# re-export block keeps the historical
# ``from workflow.universe_server import _wiki_*`` test imports working.
# See ``docs/exec-plans/active/2026-04-26-decomp-step-2-prep.md`` (Pattern A2).

# Back-compat re-exports — the names below are imported here so historical
# `from workflow.universe_server import _<symbol>` paths in tests + design
# notes keep working after the wiki body relocation. The two `_page_rel_path`
# and `_parse_frontmatter` names are also live-used by `_related_wiki_pages`
# (~L5050 in this module). See the F401 noqas — they document each name as
# an intentional re-export rather than an unused import.
from workflow.api.wiki import (  # noqa: E402
    _WIKI_CATEGORIES,  # noqa: F401  (re-export: tests/test_wiki_scaffold.py, tests/test_wiki_file_bug.py, tests/test_wiki_tools.py)
    _add_to_index,  # noqa: F401  (re-export)
    _append_wiki_log,  # noqa: F401  (re-export)
    _bug_token_set,  # noqa: F401  (re-export: tests/test_wiki_file_bug_dedup.py)
    _ensure_wiki_scaffold,  # noqa: F401  (re-export: tests/test_wiki_scaffold.py, tests/test_wiki_cosign_flow.py, tests/test_wiki_file_bug_dedup.py)
    _extract_keywords,  # noqa: F401  (re-export: tests/test_wiki_tools.py)
    _jaccard,  # noqa: F401  (re-export: tests/test_wiki_file_bug_dedup.py)
    _next_bug_id,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py)
    _next_id,  # noqa: F401  (re-export)
    _page_rel_path,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8)
    _parse_frontmatter,  # noqa: F401  (back-compat re-export; live use moved with branches Step 8 + tests/test_wiki_tools.py)
    _render_bug_markdown,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py)
    _resolve_page,  # noqa: F401  (re-export)
    _sanitize_slug,  # noqa: F401  (re-export: tests/test_wiki_tools.py)
    _scan_existing_bugs,  # noqa: F401  (re-export)
    _slugify_title,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py)
    _wiki_cosign_bug,  # noqa: F401  (re-export)
    _wiki_file_bug,  # noqa: F401  (re-export: tests/test_wiki_file_bug.py, docs/design-notes/2026-04-25-canary-to-patch-request-spec.md)
    _wiki_similarity_score,  # noqa: F401  (re-export: tests/test_wiki_tools.py)
)
from workflow.api.wiki import wiki as _wiki_impl  # noqa: E402


@mcp.tool(
    title="Wiki Knowledge Base",
    tags={"wiki", "knowledge", "drafts", "pages", "research"},
    annotations=ToolAnnotations(
        title="Wiki Knowledge Base",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def wiki(
    action: str,
    page: str = "",
    query: str = "",
    category: str = "",
    filename: str = "",
    content: str = "",
    log_entry: str = "",
    source_url: str = "",
    old_page: str = "",
    new_draft: str = "",
    reason: str = "",
    similarity_threshold: float = 0.25,
    dry_run: bool = True,
    skip_lint: bool = False,
    max_results: int = 10,
    component: str = "",
    severity: str = "",
    title: str = "",
    repro: str = "",
    observed: str = "",
    expected: str = "",
    workaround: str = "",
    force_new: bool = False,
    bug_id: str = "",
    reporter_context: str = "",
) -> str:
    """Read, write, and manage the cross-project knowledge wiki.

    Persistent prose knowledge shared across sessions: how-tos,
    definitions, research notes, references, recipes, plans. New
    content lands in drafts/ and is promoted to pages/ after quality
    checks. Not a "save anything" sink — NOT for workflow structure,
    node definitions, state, or run outputs (those route to
    `extensions` or the universe surfaces). Intent routing: use
    `extensions` for "build / design / create a workflow" or
    "track recipes / tasks / guests"; use wiki for "save this
    how-to / ref / note" or "what is X". Start with `action="list"`
    or `action="read" page="index"`.

    Args:
        action: One of — reads: read, search, list, lint; writes:
            write, consolidate, promote, ingest, supersede,
            sync_projects (no args; scans sibling project directories
            and creates stub pages/projects/*.md entries for any that
            lack one — safe to run at any time), file_bug, cosign_bug
            (add your context to an existing bug — use when file_bug
            returns status="similar_found"; requires bug_id +
            reporter_context; returns the updated bug page with your
            context appended and the cosign_count incremented).
        page: Page name for read (also: index, log, schema).
        query: Search keywords for search.
        category: write / promote category — projects, concepts,
            people, research, recipes, workflows, notes, references,
            plans, bugs. Match the CONTENT; `research` is reserved
            for LLM-generated research pages and paper drafts. `bugs`
            is for `action=file_bug` only — prefer the dedicated verb
            so the server assigns the BUG-NNN id.
        filename: Filename for write / promote / ingest / supersede.
        content: Page or source body for write / ingest.
        log_entry: Optional log message for write.
        source_url: Optional URL for ingest.
        old_page: Page to supersede.
        new_draft: Replacement draft for supersede.
        reason: Why the old page is being superseded.
        similarity_threshold: Merge threshold for consolidate
            (0-1, default 0.25).
        dry_run: Consolidate reports only when true (default true).
        skip_lint: Promote skips quality checks when true.
        max_results: Max search results (default 10).
        component: file_bug — surface where the defect lives (e.g.
            "extensions.patch_branch", "universe.inspect", "tray").
        severity: file_bug — one of critical | major | minor |
            cosmetic. critical=data loss/outage; major=tool unusable;
            minor=non-blocking workaround exists; cosmetic=wording.
        title: file_bug — one-line title (bug) or description (feature/design).
        repro: file_bug — minimal tool call or steps to reproduce (bugs).
        observed: file_bug — what the tool actually returned/did (bugs).
        expected: file_bug — what it should have returned/done, or desired
            behavior for feature requests.
        workaround: file_bug — optional workaround applied (bugs).
        kind: file_bug — classification: "bug" (default) | "feature" |
            "design". All three use the same channel; navigator vets all.
            "feature" = new capability ask; "design" = design proposal or
            primitive ask. Use ``tags`` to add free-form labels.
        tags: file_bug — optional comma-separated free-form labels
            (e.g. "ux,performance"). Added to the frontmatter tags list
            alongside the auto-generated component tag and kind tag.
        force_new: file_bug — skip the similarity check and always mint a
            new id. Use when the symptom is materially different from any
            suggested similar bug.
        bug_id: cosign_bug — id of the bug to cosign (e.g. "BUG-042").
        reporter_context: cosign_bug — free-form context from the reporter
            (what they observed, their environment, etc.).

    Design-participation note: ``file_bug`` is the single verb for bugs,
    feature requests, design proposals, and primitive asks. Navigator vets
    all filings before dev implements — kind tagging is how the pipeline
    distinguishes them without separate verbs.

    Maintenance-ops note: ``promote`` (drafts → pages, runs the lint gate
    unless ``skip_lint=true``) and ``consolidate`` (merge similar drafts
    above a similarity threshold) are housekeeping verbs typically run by
    the host or a curator, not casually invoked from a chat turn. From a
    chatbot, prefer ``write`` (drafts new content) plus ``lint`` (quality
    check) and let curators handle promotion and merging.
    """
    return _wiki_impl(
        action=action,
        page=page,
        query=query,
        category=category,
        filename=filename,
        content=content,
        log_entry=log_entry,
        source_url=source_url,
        old_page=old_page,
        new_draft=new_draft,
        reason=reason,
        similarity_threshold=similarity_threshold,
        dry_run=dry_run,
        skip_lint=skip_lint,
        max_results=max_results,
        component=component,
        severity=severity,
        title=title,
        repro=repro,
        observed=observed,
        expected=expected,
        workaround=workaround,
        force_new=force_new,
        bug_id=bug_id,
        reporter_context=reporter_context,
    )


# ══════════════════════════════════════════════════════════════════════
# TOOL 5 — get_status (routing-evidence primitive for tier-2 trust)
# ══════════════════════════════════════════════════════════════════════
#
# The get_status body and _policy_hash helper live in
# ``workflow/api/status.py`` (extracted 2026-04-26 — Task #10, decomp Step 3).
# Same Pattern A2 as Task #9: the @mcp.tool registration stays here so
# FastMCP introspection sees the chatbot-facing signature + docstring exactly
# as before, and ``get_status`` is re-exported below for back-compat with
# existing test imports (`from workflow.universe_server import get_status`
# across 8 test files). See
# ``docs/exec-plans/active/2026-04-26-decomp-step-3-prep.md``.
#
# Original design rationale, preserved verbatim:
#
# Interim MCP primitive introduced 2026-04-19 (task #88) per navigator's
# Devin-session1 intelligence report §T-7. Devin bounced at live exchange 4
# because his chatbot had no tool-surface primitive to VERIFY the
# confidential-tier routing promise — without concrete evidence it correctly
# refused to guess from parameter names on a privacy-critical decision.
#
# This tool is a factual read-only surface that reports:
#   - current active-host identity
#   - the daemon's served LLM type (the closest legacy-surface analogue of
#     a routing-constraint commitment)
#   - a deterministic policy hash for drift detection across runs
#   - recent-activity evidence drawn from the public activity.log
#
# The legacy universe_server surface predates spec #79's tier-routing
# enforcement schema; this primitive returns what IS factual today and
# narrates what's NOT yet enforced so the chatbot can make honest claims
# instead of inferred ones. Full tray observability + per-universe
# sensitivity_tier enforcement lives in the rewrite (spec #79 §13).

from workflow.api.status import _policy_hash  # noqa: E402, F401  (back-compat re-export)
from workflow.api.status import get_status as _get_status_impl  # noqa: E402


@mcp.tool(
    title="Daemon Status + Routing Evidence",
    tags={
        "status", "routing", "privacy", "verification",
        "confidential-tier", "workflow",
    },
    annotations=ToolAnnotations(
        title="Daemon Status + Routing Evidence",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_status(universe_id: str = "") -> str:
    """Factual snapshot of the daemon's identity + routing config.

    Chatbots call this whenever they need ground-truth daemon facts,
    not just for privacy questions. Triggering questions include:
      - Privacy / routing: "will my manuscript go to a cloud LLM?",
        "which model is this bound to?", "is anything leaving my box?".
      - Liveness / orientation: "is the daemon running?", "what's the
        active universe?", "which provider is currently bound?".
      - Audit / proof: "show me the routing evidence" or anything where
        the chatbot needs to back a claim with a tool fact instead of
        relying on memory or the prompt.
    Returns concrete evidence the chatbot can narrate; does not infer
    or guess.

    **Versioned contract (schema_version=1):** All fields below are
    stable. Field removals and renames require a deprecation notice in
    the response for one release before removal. New fields may be added
    freely; they do not bump schema_version. Breaking changes (removal,
    rename, type change) MUST bump schema_version and update this
    docstring + the contract test in tests/test_get_status_primitive.py.

    Shape (§10.7 self-auditing-tools canonical):
        {
          "schema_version": int,
          "active_host": {host_id, served_llm_type, llm_endpoint_bound},
          "tier_routing_policy": {served_llm_type, accept_*, bid_*, ...},
          "evidence": {last_completed_request_llm_used,
                       activity_log_tail, last_n_calls,
                       activity_log_line_count, policy_hash},
          "evidence_caveats": {<evidence_key>: [caveat, ...]},
          "caveats": [global_caveat, ...],
          "actionable_next_steps": [...],
          "session_boundary": {
              prior_session_context_available: bool,
              account_user: str,
              last_session_ts: str | null,
              note: str,
          },
          "storage_utilization": {...},
          "per_provider_cooldown_remaining": {<provider>: seconds_int, ...},
          "universe_id": str,
          "universe_exists": bool,
        }

    `caveats` is load-bearing — the legacy surface does NOT yet enforce
    per-universe sensitivity_tier (that lives in spec #79 §13, post-
    rewrite). The chatbot MUST read + narrate caveats so trust claims
    match reality. Per-field caveats let the chatbot cite only the
    evidence keys that are degenerate, instead of wrapping every claim
    in the global caveat list.

    `last_n_calls` is a structured view of the most recent activity
    entries (parsed `{ts, tag, message, raw}` dicts, most-recent first).
    Derived from the same activity.log tail as `activity_log_tail`. When
    the parser cannot recover a tag for an entry, that key surfaces in
    `evidence_caveats` so chatbots know tag-based filtering on those
    entries is unreliable.

    `session_boundary` gives the chatbot a tool fact for cross-session
    identity grounding. `prior_session_context_available=false` means
    the activity log has no entries from the current account in the last
    30 days — the chatbot can cite this instead of relying purely on
    the prompt-level cross-session behavioral directive.

    Args:
        universe_id: Optional universe scope. Defaults to active universe.
    """
    return _get_status_impl(universe_id=universe_id)



# ═══════════════════════════════════════════════════════════════════════════
# Server Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main(
    host: str = "0.0.0.0",
    port: int = 8001,
    transport: str = "streamable-http",
) -> None:
    """Run the Workflow Server as a remote MCP server.

    Args:
        host: Bind address (default all interfaces).
        port: Port number (default 8001).
        transport: MCP transport protocol. "streamable-http" for remote
            connections (default), "sse" for legacy, "stdio" for local.
    """
    logger.info(
        "Starting Workflow Server on %s:%d (transport=%s)",
        host, port, transport,
    )

    if transport == "streamable-http":
        mcp.run(transport="streamable-http", host=host, port=port)
    elif transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
    elif transport == "stdio":
        mcp.run()
    else:
        raise ValueError(f"Unknown transport: {transport}")


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3 — Goals (back-compat @mcp.tool wrapper, Pattern A2)
# ═══════════════════════════════════════════════════════════════════════════
# Body extracted to ``workflow.api.market.goals``. This wrapper preserves
# FastMCP introspection (the chatbot-facing signature + docstring) and
# delegates to the plain callable.

@mcp.tool(
    title="Goals",
    tags={"goals", "discovery", "intent", "community"},
    annotations=ToolAnnotations(
        title="Goals",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def goals(
    action: str,
    goal_id: str = "",
    branch_def_id: str = "",
    branch_version_id: str = "",
    name: str = "",
    description: str = "",
    tags: str = "",
    visibility: str = "",
    query: str = "",
    metric: str = "",
    min_branches: int = 2,
    author: str = "",
    limit: int = 50,
    scope: str = "",
    force: bool = False,
) -> str:
    """Goals — first-class shared primitives above workflow Branches.

    A Goal captures the intent a workflow serves ("produce a research
    paper", "plan a wedding"). Many Branches bind to one Goal. Users
    discover existing Goals before building a new Branch so the
    "reuse vs invent" decision is tractable.

    Actions:
      propose      Create a new Goal. Needs `name`. Optional
                   description, tags (CSV), visibility (public/private).
      update       Patch a Goal you own. Fields: name, description,
                   tags, visibility. Non-owners cannot update — propose
                   a new Goal instead.
      bind         Attach a Branch to a Goal. Pass goal_id="" to
                   unbind. Needs branch_def_id.
      set_canonical Mark a branch_version_id as the Goal's canonical
                   (best-known) branch. Author-only or host-only.
                   Pass branch_version_id="" to unset.
      list         Browse Goals. Optional author, tags (CSV first
                   value only), limit. Soft-deleted Goals hidden.
      get          Full Goal view + bound Branches. Needs goal_id.
      search       LIKE-based substring search over name, description,
                   tags. Needs query.
      leaderboard  Rank bound Branches by metric. v1 supports
                   `run_count` and `forks`. `outcome` returns a Phase 6
                   stub today; the same call will surface real outcome
                   rankings once Phase 6 ships.
      common_nodes Nodes appearing in >=`min_branches` Branches.
                   With `scope="this_goal"` (default), restricts to
                   one Goal's Branches. With `scope="all"`, aggregates
                   across every Goal and every unbound Branch — use
                   this when helping a user decide "is there already
                   a node that does X somewhere on this server?" even
                   if they haven't committed to a Goal yet.

    Args:
      action: see above.
      goal_id: Goal target for bind/get/update/search/leaderboard,
        and for common_nodes when scope='this_goal'.
      branch_def_id: Branch target for bind.
      branch_version_id: Published branch_version_id for set_canonical
        (pass empty string to unset). Must reference a row in
        `branch_versions` — only published versions may be canonical.
      name/description/tags/visibility: Goal fields for propose/update.
      query: search query.
      metric: leaderboard metric (run_count/forks/outcome).
      min_branches: common_nodes cutoff (default 2).
      scope: common_nodes aggregation. 'this_goal' (default) restricts
        to one Goal; 'all' aggregates cross-Goal.
      author: list filter.
      limit: cap on returned rows.
      force: override `local_edit_conflict` refusal on propose/update/bind
        when the target YAML has uncommitted local edits. Default False —
        the conflict surfaces as a structured response so the caller can
        commit / stash / discard first.
    """
    return _goals_impl(
        action=action,
        goal_id=goal_id,
        branch_def_id=branch_def_id,
        branch_version_id=branch_version_id,
        name=name,
        description=description,
        tags=tags,
        visibility=visibility,
        query=query,
        metric=metric,
        min_branches=min_branches,
        author=author,
        limit=limit,
        scope=scope,
        force=force,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3b — Outcome Gates (back-compat @mcp.tool wrapper, Pattern A2)
# ═══════════════════════════════════════════════════════════════════════════
# Body extracted to ``workflow.api.market.gates``. Same Pattern A2 as
# ``goals()`` above.

@mcp.tool(
    title="Outcome Gates",
    tags={"gates", "outcomes", "impact", "leaderboard", "community"},
    annotations=ToolAnnotations(
        title="Outcome Gates",
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
def gates(
    action: str,
    goal_id: str = "",
    branch_def_id: str = "",
    rung_key: str = "",
    ladder: str = "",
    evidence_url: str = "",
    evidence_note: str = "",
    reason: str = "",
    include_retracted: bool = False,
    limit: int = 50,
    force: bool = False,
    claim_id: str = "",
    bonus_stake: int = 0,
    attachment_scope: str = "node",
    eval_verdict: str = "",
    node_last_claimer: str = "",
    node_id: str = "",
) -> str:
    """Outcome Gates — real-world impact claims per Branch.

    Each Goal declares a ladder of rungs (draft -> peer-reviewed -> published
    -> cited -> breakthrough). Branches self-report which rungs they've
    reached, with an evidence URL.

    All actions require GATES_ENABLED=1 on the server; the tool returns
    {"status": "not_available"} when the flag is off. Bonus actions
    additionally require WORKFLOW_PAID_MARKET=on.

    Actions (all live when GATES_ENABLED=1):
      define_ladder Owner sets the rung list on a Goal. Needs goal_id
                    and `ladder` (JSON list of {rung_key, name,
                    description}).
      get_ladder    Read a Goal's ladder. Needs goal_id.
      claim         Report a rung reached. Needs branch_def_id,
                    rung_key, evidence_url. Idempotent on (branch, rung).
      retract       Soft-delete a claim. Needs branch_def_id, rung_key,
                    reason. Claim author, Goal owner, or host can
                    retract.
      list_claims   Browse claims. Provide exactly one of branch_def_id
                    or goal_id. `include_retracted` optional; claims
                    whose rung no longer exists in the Goal's ladder
                    are tagged `orphaned`.
      leaderboard   Rank Branches bound to a Goal by highest rung
                    reached. Tiebreak: earliest claim wins. Also
                    callable as `goals leaderboard metric=outcome`.

    Bonus actions (live when GATES_ENABLED=1 + WORKFLOW_PAID_MARKET=on):
      stake_bonus   Lock a bonus stake on a claim. Needs claim_id,
                    bonus_stake (int > 0), node_id. attachment_scope
                    controls what the stake attaches to ("node" default).
      unstake_bonus Remove a bonus stake and refund the staker. Needs
                    claim_id. Only the original staker can unstake.
      release_bonus Resolve a bonus payout via evaluator verdict. Needs
                    claim_id, eval_verdict ("pass"|"fail"|"skip"),
                    node_last_claimer (recipient on pass).

    Evidence URL must be http(s) with a host; content is not fetched
    (local-first). Social accountability handles fraud in v1.

    Args:
      action: see Actions above.
      goal_id: Goal target for ladder / leaderboard / list_claims.
      branch_def_id: Branch that's claiming / retracting / listing.
      rung_key: matches a ladder entry's rung_key.
      ladder: JSON list string for define_ladder.
      evidence_url: http(s) URL pointing at the claim's evidence.
      evidence_note: optional human summary.
      reason: retract reason (required for retract, non-empty).
      include_retracted: list_claims filter (default False).
      limit: cap for leaderboard / list_claims.
      force: bypass the dirty-file guard on the target YAML when a
             user has uncommitted local edits. Same ergonomics as
             `goals propose/update/bind` and `branch` mutations.
      claim_id: target claim for stake_bonus / unstake_bonus /
                release_bonus.
      bonus_stake: integer token amount for stake_bonus (must be > 0).
                   Harmless when WORKFLOW_PAID_MARKET is off — the
                   action returns not_available before reading this arg.
      attachment_scope: what the stake attaches to; "node" (default)
                        or "branch". Used by stake_bonus.
      eval_verdict: evaluator decision for release_bonus —
                    "pass" (payout to node_last_claimer), "fail"
                    (refund to staker), or "skip" (no-op).
      node_last_claimer: actor_id of the node fulfiller who receives
                         payout on a "pass" release_bonus verdict.
      node_id: node target for stake_bonus.
    """
    return _gates_impl(
        action=action,
        goal_id=goal_id,
        branch_def_id=branch_def_id,
        rung_key=rung_key,
        ladder=ladder,
        evidence_url=evidence_url,
        evidence_note=evidence_note,
        reason=reason,
        include_retracted=include_retracted,
        limit=limit,
        force=force,
        claim_id=claim_id,
        bonus_stake=bonus_stake,
        attachment_scope=attachment_scope,
        eval_verdict=eval_verdict,
        node_last_claimer=node_last_claimer,
        node_id=node_id,
    )


