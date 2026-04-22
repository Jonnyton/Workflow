# Navigator-vetted specs

Specs for user-submitted ideas — bugs, feature requests, design proposals — that have cleared both navigator passes (safety + strategy). Dev reads from this file. Lead dispatches from this file. When a spec lands in code, both the pointer row in `STATUS.md` and the H2 section here are removed together (commit is the record).

This file is **navigator-owned and git-tracked, never wiki-writable.** No `BUG-NNN` cross-references — titles are descriptive. Each H2 heading is the anchor; slug-ify the heading to get the `#anchor` in pointer rows.

Rule context: `feedback_wiki_bugs_vet_before_implement` + `project_bug_reports_are_design_participation`.

---

## Structured JSON output for multi-output + typed prompt nodes

**Scope:** `_build_prompt_template_node` (graph_compiler.py) appends a JSON response-schema contract to the rendered prompt when the node has ≥2 output_keys OR any typed state_schema entry (≠ str) on its output_keys. Response parsed as JSON; each declared output_key assigned from the parsed object; values coerced per state_schema types. Missing declared key, type-coercion failure, or malformed JSON all raise `CompilerError` / `EmptyResponseError`. **Provider layer untouched** — layerable, future direct-API providers can add a native response_format fast path on top without re-architecting this layer. Fixes two sibling symptoms of the same root cause: (1) multi-output silent-drop where `output_key = node.output_keys[0]` writes the entire response to only the first declared key; (2) typed-output no-op where `state_schema` type declarations are declarative-but-unenforced so `retry_count: int` stays at its prior value while the LLM emits the new value as prose.

**Files:** `workflow/graph_compiler.py`, tests.

**Invariants:** hard-rule #8 (crash, never silent-drop) applies identically across all 6 providers including Ollama CLI-wrapped fallback; single-output-key + str-type path unchanged (backward-compat); JSON-contract path fires only when multi-output OR typed.

**Tests:** both-keys-present + typed-correct success; one-key-missing crash; wrong-type crash; malformed-JSON crash; str-only single-key backward-compat path unchanged; Ollama-provider path crashes-not-drops.

**Vetted:** 2026-04-22 by navigator.

**Rationale for compiler-only scope:** 3/6 providers are CLI-wrapped (claude, codex, ollama) where response_format isn't natively wirable — prompt-engineered JSON satisfies hard-rule #8 today; native response_format fast path is a separate 4-8h feature ask.

---

## Strict input_keys isolation for prompt_template nodes

**Status note:** in-progress — dev has already implemented matching approach in working tree per `workflow/branches.py` + `workflow/graph_compiler.py` uncommitted diff. Lead — delete this section + the STATUS.md pointer row when the commit lands.

**Scope:** Extend code-node state-filter to prompt_template nodes. Add `strict_input_isolation: bool = False` on NodeDefinition. `_build_prompt_template_node` renders against input_keys-scoped state when strict; `collect_build_warnings` surfaces out-of-input-keys placeholders at build time regardless of flag.

**Files:** `workflow/branches.py`, `workflow/graph_compiler.py`, tests.

**Invariants:** flag default false (backward-compat); strict=true rejects at build AND run; warning is non-fatal and render-noop when strict=false.

**Tests:** strict+valid ok; strict+out-of-keys raises; strict=false same refs warn+render; build-time static check catches before run.

**Vetted:** 2026-04-22 by navigator.

---

## Expose conditional_edges on build_branch + patch_branch

**Use case the filer called out explicitly:** iteration loops + pass-fail gates as first-class in-graph control flow. Today these require an outer runner invoking run_branch repeatedly and threading state externally; this spec moves loop-and-gate logic inside the graph where it belongs.

**Scope:** `ConditionalEdge` dataclass + `BranchDefinition.conditional_edges` + `graph_compiler` rendering already exist. MCP surface never exposes the field: `_staged_branch_from_spec` (universe_server.py:5293) doesn't read `spec["conditional_edges"]`; `_apply_patch_op` (line 5435) has no `add_conditional_edge` / `remove_conditional_edge` ops. Add: (a) `_apply_conditional_edge_spec(branch, raw)` mirroring `_apply_edge_spec`, parses `{from, conditions: {outcome: target}}` via `ConditionalEdge.from_dict`; (b) `_staged_branch_from_spec` iterates `spec.get("conditional_edges") or []` after regular edges; (c) patch_branch ops `add_conditional_edge` (takes `{from, conditions}`) and `remove_conditional_edge` (takes `from` plus optional `outcome` — removes the entire conditional edge if outcome unspecified, else just that outcome→target mapping).

**Files:** `workflow/universe_server.py`, tests.

**Invariants:** conditional_edges returned in `describe_branch` / `get_branch` already work unchanged; build from spec_json and patch ops round-trip to the same on-disk shape; validation rejects conditional edges referencing nonexistent nodes or empty conditions dict. **Cycles are allowed** (they're the point — iteration loops require them); validation only rejects unreachable targets and malformed condition maps. LangGraph runtime already caps iteration via its recursion limit, so the graph layer doesn't need a separate loop guard.

**Tests:** build_branch with conditional_edges spec populates field; patch_branch add_conditional_edge appends; remove_conditional_edge with outcome removes mapping; remove_conditional_edge without outcome removes entire edge; validation rejects conditional edge referencing nonexistent target; validation ACCEPTS a self-loop via conditional edge (e.g. `gate → {loop: producer, done: END}` where producer ultimately routes back to gate — explicit loop test case).

**Vetted:** 2026-04-22 by navigator (re-tightened with loop use case + cycle-allowed invariant after lead correction on two-halves audit).

---

## list_branches node_count double-counts graph.nodes + node_defs

**Scope:** `workflow/universe_server.py:4576` computes `node_count = len(graph.get("nodes", [])) + len(r.get("node_defs", []))`. Change to `len(r.get("node_defs", []))` — matches the source-of-truth `describe_branch` uses at line ~4924. Truthful count is node_defs length; graph.nodes is a compiled-topology view that overlaps.

**Files:** `workflow/universe_server.py` + existing list_branches test.

**Invariants:** list_branches.node_count == describe_branch node count for the same branch.

**Tests:** regression test asserting count parity across list+describe for a branch with N node_defs.

**Vetted:** 2026-04-22 by navigator.

---

## describe_branch / get_branch surface related wiki pages

**Scope:** Add `related_wiki_pages: [{path, title, summary, matched_via}]` section to `_ext_branch_describe` and `_ext_branch_get` responses. Compute by calling `_wiki_search` for the branch_def_id + each node_id; dedupe by path; rank by match-count (both-match beats single-match); cap top 20 with `truncated_count`; summary = first prose paragraph clipped to 140 chars else frontmatter `description` else empty; `matched_via` lists which query terms hit.

**Files:** `workflow/universe_server.py` (add helper near `_ext_branch_describe`), tests.

**Invariants:** no NodeDefinition/BranchDefinition schema change; no `graph_compiler` touch; no new at-rest storage; always-on (no flag).

**Tests:** matches returned in describe+get; no matches returns empty list not missing key; summary 140-char cap; top-20 cap with truncated_count set; matched_via reflects actual term hits.

**Vetted:** 2026-04-22 by navigator. Reshape of the maintainer-notes user-submitted spec per host direction option B (wiki is the substrate; don't duplicate). Full design rationale: `pages/plans/feature-describe-branch-related-wiki-pages.md` (navigator-authored).

---

## Per-node llm_policy override

**Scope:** Today `NodeDefinition.model_hint` → `role` drives the role-based provider router. User ask: `(provider, model, reasoning_effort)` pinning + fallback chain + difficulty override — supersets role-routing without replacing it. Add `llm_policy: dict | None = None` on NodeDefinition. Shape: `{preferred: {provider, model, reasoning_effort?}, fallback_chain: [{provider, model, trigger: "unavailable"|"rate_limited"|"cost_exceeded"|"empty_response"}], difficulty_override: [{if_difficulty, use: {provider, model}}]}`. Runner resolves preferred → fallback_chain → difficulty_override at dispatch time. Branch-level `default_llm_policy` applies to nodes without their own. Emit actual provider served into activity log + get_node_output. When `llm_policy` unset, fall back to existing role-based routing (backward-compat).

**Files:** `workflow/branches.py` (add field, pass through in serializer), `workflow/graph_compiler.py` (consume + resolve), `workflow/providers/router.py` (accept explicit provider/model override + fallback triggers), tests.

**Invariants:** unset llm_policy = current behavior (no regression); fallback chain must exhaust before raising; provider choice observable via activity log.

**Tests:** pinned preferred used when available; fallback fires on each trigger class; difficulty override routes correctly; branch-default applies when node-level unset; unset = role-routing backward-compat.

**Vetted:** 2026-04-22 by navigator.

---

## In-flight run recovery surface — part 1 (document v1 contract)

**Bug-half vs feature-half — both named explicitly:** The filer asked BOTH (a) "document what happens on restart" (bug-half — v1 contract is fail-loudly-INTERRUPTED, already implemented via `recover_in_flight_runs` runs.py:1411 but undocumented at the MCP surface) AND (b) "expose a resume_run(run_id) action" (feature-half — SqliteSaver-keyed resume, explicitly deferred in runs.py:1417-1419 as "v1 product requirement = clean terminal state"). Under the new "don't skip the feature half" rule, I'm splitting this into two specs: part 1 (this one) ships the v1 contract documentation; part 2 (follow-up below) is the resume feature worth real deliberation.

**Scope (part 1):** Add: (a) docstring on `run_branch` describing the durability guarantee ("runs are interrupted-terminal on daemon restart; caller reruns with same inputs_json"); (b) `get_run` response includes `resumable: false, reason: "v1 terminal-on-restart"` for INTERRUPTED rows so the chatbot knows to retry rather than poll forever; (c) explicit rerun-with-same-inputs example in the branch_design_guide. Chatbot provides the user-facing UX of "your run was interrupted, rerunning it now."

**Files:** `workflow/universe_server.py` (run_branch docstring + get_run response), `workflow/runs.py` (comment refinement), tests.

**Invariants:** INTERRUPTED runs return resumable=false; get_run on INTERRUPTED includes the "Server restarted while in flight" error clearly; no silent stuck-forever state.

**Tests:** runs that existed pre-restart and were interrupted show status=INTERRUPTED + resumable=false + error present in get_run.

**Vetted:** 2026-04-22 by navigator (re-scoped: part-1 of two after lead correction on two-halves audit).

---

## In-flight run recovery — part 2 (SqliteSaver-keyed resume) — STRATEGY REVIEW NEEDED

**Status: strategy-open.** This is the feature-half of the durable-execution bug the filer named. Navigator's Pass 2 needs a host call before dev starts. The existing code (`runs.py:1417-1419`) comments the resume as a "follow-up" with "v1 product requirement = clean terminal state" — a deliberate deferral. Filer argues this was defensible before Temporal-style durable execution became 2026 industry standard, and now it's not.

**Candidate scope if approved:** Add `extensions action=resume_run {run_id}`. On INTERRUPTED runs, load the SqliteSaver checkpoint keyed by `run_id`, compile the branch, resume the LangGraph state from last-completed-node via `graph.astream(None, config={"configurable": {"thread_id": run_id}})`. Write resume event to runs.events. New run status `RESUMED` between INTERRUPTED and RUNNING.

**Strategy questions open to host:**
1. **Is the 2026 Temporal-parity argument load-bearing enough to override the deliberate v1 product call?** Filer cites OpenAI Codex using Temporal in production. Counter: our workflows are user-ratified-rerun-tolerant; rerunning with same inputs_json is often the correct UX (fresh LLM call, chance to see if the problem is transient vs deterministic).
2. **Multi-tenant implications:** resume assumes the original caller's identity is re-validated at resume time (not just "the checkpoint exists"). Needs auth re-check so a different user can't resume another user's interrupted run.
3. **Failure-mode asymmetry:** resume-succeeds is cheap; resume-fails-halfway is expensive (partial state written with no way to distinguish from fresh-run state). Need idempotency guarantees or per-node "already completed" markers.
4. **Cost implications:** resume skips provider calls for completed nodes. At paid-market prices this matters — ~10× cheaper than rerun on a 10-node branch that died at step 9. Aligns with `project_monetization_crypto_1pct` ledger honesty.

**Recommendation:** Host direction needed before dev scopes this. My lean is "ship it — Temporal-parity is real and cost-savings at scale make this load-bearing" but the v1-was-deliberate comment in runs.py means this is a product call above navigator's pay grade.

**Vetted:** 2026-04-22 by navigator — **strategy pass OPEN pending host direction, NOT dev-dispatchable yet.** Bug filer was right to ask both; I originally absorbed this into a v1-lock that wasn't mine to make.

---

## Concurrency budget + observability for fan-out nodes

**Scope:** (1) Add `concurrency_budget: int | None = None` on `BranchDefinition` (branch-level cap; None = unbounded = current behavior). When set, the runner caps concurrent executing nodes at N using a semaphore acquired before each node's provider_call. (2) `get_run` response includes a `concurrency` field: `{active_now: int, peak: int, budget: int | null}` — lets the chatbot see contention. (3) Optional `run_branch` arg `concurrency_budget_override` to override branch-level at dispatch time.

**Files:** `workflow/graph_compiler.py` (semaphore around provider_call), `workflow/branches.py` (field), `workflow/runs.py` (event emission for active-node count), `workflow/universe_server.py` (override arg + response), tests.

**Invariants:** unset = unbounded = current behavior (backward-compat); semaphore releases on node completion, failure, timeout, and cancellation; observability non-zero overhead acceptable but should be cheap (atomic counter).

**Tests:** budget=1 serializes fan-out; budget=3 allows 3 concurrent; active_now emitted in events; peak monotonic; unset = no cap; override beats branch default.

**Vetted:** 2026-04-22 by navigator.

---

## Loud sandbox-unavailable surface for dev/checker exec nodes + design-only-branch role

**Bug-half vs feature-half:** Filer named both (a) "silent ran=true on sandbox failure is the worst outcome" (bug-half) and (b) "design-only agent teams that produce specs without implementing" as a legitimate product shape for when the sandbox genuinely isn't available (feature-half). The bug-half is the fail-loudly surface; the feature-half is making "design-only" a first-class branch role, not just a user workaround.

**Scope — bug-half (fail-loudly sandbox detection):** Agent-team dev/checker nodes invoke external CLIs (Claude Code, Codex) that on Linux use bubblewrap. When the kernel lacks unprivileged user namespaces, bwrap fails and the CLI emits a specific error string ("bwrap: No permissions to create a new namespace") — but the current code treats this as normal CLI output, writes it into state, and marks the node `ran`. Detect the bwrap-failure signature in CLI outputs (exit code + stderr pattern); when detected, raise `CompilerError` (hard-rule #8 fail-loudly) with guidance (see `sandbox_status` below for the structured form). Also: `get_status` surfaces a new field `sandbox_status: {bwrap_available: bool, reason?: str}` probed once at daemon startup (try `bwrap --version` + a no-op subprocess).

**Scope — feature-half (design-only branch role):** NodeDefinition gains a `requires_sandbox: bool = False` field (default false preserves compat). Nodes that shell out to exec-requiring CLIs (dev, checker, tester variants) set `requires_sandbox=true`. When `get_status.sandbox_status.bwrap_available=false`, `validate_branch` emits a warning listing every `requires_sandbox=true` node in the branch and suggests "this branch requires sandbox; either enable bwrap on the host or design a branch variant without sandbox-requiring nodes." A branch with no `requires_sandbox=true` nodes is implicitly a "design-only" branch — no new role enum needed, the field + validation are the feature. `list_branches` filter `requires_sandbox: "any" | "none"` so users can filter for design-only-safe branches.

**Files:** `workflow/graph_compiler.py` (post-call bwrap detection), `workflow/providers/` (detection helper shared with other callers), `workflow/branches.py` (requires_sandbox field), `workflow/universe_server.py` (_action_get_status sandbox_status field, _ext_branch_validate sandbox-compat warning, _ext_branch_list filter), tests.

**Invariants:** detection regex matches the exact bwrap failure string and does not false-positive on normal output; get_status probe runs once cached; bwrap-failure ⇒ raise (never silent ran=true); `requires_sandbox=false` node NEVER raises on sandbox unavailability (design-only nodes don't care); `validate_branch` warning is non-fatal (branch still runs, user decides).

**Tests:** mock CLI output with bwrap-failure signature raises; normal CLI output with no bwrap mention passes through; get_status reports sandbox_status correctly on a probe-success and probe-fail host; validate_branch on a bwrap-unavailable host warns for branches with requires_sandbox=true nodes and stays clean for design-only branches; list_branches filter splits the corpus correctly.

**Vetted:** 2026-04-22 by navigator (re-scoped to include design-only branch role per lead correction on two-halves audit — filer named it as a legitimate product pattern; I had originally left it as error-message text only). Note: root-cause fix (bwrap actually working) is host-level configuration, not code — this spec closes both the observability gap AND the "design-only is a valid product shape" gap.

---

## Sub-branch invocation primitive (with async-companion)

**Scope:** Two companion node kinds so the async half is first-class, not deferred. (1) `invoke_branch`: accepts `{branch_def_id, inputs_mapping: {state_key: input_key}, output_mapping: {state_key: output_key}, wait_mode: "blocking"|"async"}`. Blocking = spawn child run via `execute_branch_async`, wait for END, write declared output_mapping fields into parent state. Async = spawn child, write `run_id` into a declared parent state field, return immediately. (2) `await_branch_run`: accepts `{run_id_field, output_mapping, timeout_seconds?}`. Reads the run_id from the named parent state field, polls runs table until that child reaches END (or timeout), writes output_mapping. Blocking + async + await together cover fork/join (spawn several async children, wait for all via await nodes in parallel) as well as the simple blocking invoke.

**Files:** `workflow/branches.py` (new node kinds / specs for both `invoke_branch` and `await_branch_run`), `workflow/graph_compiler.py` (build both node callables), `workflow/runs.py` (ensure nested runs don't recurse into the same SqliteSaver thread; expose child-status poll helper for await), tests.

**Invariants:** inputs_mapping + output_mapping validated at build time (keys must exist on parent state_schema + child); recursion depth capped (default 5) to avoid infinite nesting; child run links to parent run_id in runs table; `await_branch_run` default timeout 300s (matches existing NodeDefinition.timeout_seconds default); await on a nonexistent run_id raises at run time with clear error (not silent hang).

**Tests:** blocking invoke populates output mapping; async invoke returns run_id; await reads run_id and populates output; await with timeout raises; fork/join pattern (two async invokes → two awaits in parallel) works end-to-end; recursion cap raises; invalid mapping rejected at build.

**Vetted:** 2026-04-22 by navigator (re-tightened: pulled in the `await_branch_run` companion per lead correction on two-halves audit — filer named it in the expected-behavior, I had originally deferred it).

---

## Cross-run state query primitive

**Scope:** Add `extensions action=query_runs` accepting `{branch_def_id, filters: {status?, actor?, since?, until?}, select: [state_field_names], aggregate?: {group_by: state_field, count|mean|sum|rate}, limit}`. Returns denormalized rows OR aggregation result. Powers karpathy-style autoresearch + pass-rate analytics that today require O(N) `get_run` loops. Backed by a materialized view OR on-demand sqlite query against runs.db with a JSON extract over the state blob.

**Files:** `workflow/runs.py` (query helper), `workflow/universe_server.py` (MCP action), tests.

**Invariants:** select fields must be in the branch's state_schema (build-time check); visibility respects Branch privacy; limit default 100 / cap 1000 to avoid dump-the-db; aggregation correct across partial runs (exclude INTERRUPTED unless opted in).

**Tests:** filter+select returns expected rows; group_by+count aggregates correctly; visibility filter hides private-to-other-user branches; limit capping.

**Vetted:** 2026-04-22 by navigator.

---

## Scheduled + event-triggered branch invocation

**Scope:** Two new primitives: (1) `extensions action=schedule_branch` `{branch_def_id, cron_or_interval, inputs_template}` registers a schedule; runner invokes `run_branch` per schedule; scheduled runs tag `actor=scheduler:<schedule_id>`. (2) `extensions action=subscribe_branch` `{branch_def_id, event_type, inputs_mapping}` registers an event subscription; events include `canon_change`, `branch_run_completed:{branch_def_id}`, `pr_open`, `canon_upload`. Runner emits these events internally + exposes event bus to external producers. Persistence: SQLite table per schedule/subscription; survives daemon restart. Uptime alignment: scheduled aggregators are core to always-on (forever-rule).

**Files:** `workflow/runs.py` (schedule table + event table), `workflow/universe_server.py` (actions), `workflow_tray.py` or `workflow/scheduler.py` new module (tick loop), tests.

**Invariants:** schedule fires on wall-clock regardless of in-flight runs (last-run can overlap next tick; configurable skip_if_running); event subscription fires exactly once per event; removal of a schedule is immediate (no orphan firings); inputs_template validates at registration time against branch's schema.

**Tests:** cron schedule fires at expected times (fake clock); interval schedule respects skip_if_running; event subscription fires on emitted event; subscription unregister stops firings.

**Vetted:** 2026-04-22 by navigator.

---

## Project-scope persistent memory primitive (minimal — "what is a project" deferred)

**Scope (MINIMAL — what-is-a-project deferred):** Add `project` as a sixth scope tier to the existing tiered memory model (node/branch/goal/user/universe). **`project_id` is an opaque caller-supplied string** — we deliberately do NOT define "what is a project" at the data-model level in this spec. A caller passes e.g. a repo name, goal slug, or arbitrary identifier; we store key/value rows keyed on it. The deeper question (auto-project-detection from git clone? project lifecycle events? project-settings substrate? relationship to existing goal_id?) is a **follow-up design spec**, not this one. Ship the minimal persistent-kv surface now; iterate on project-identity once we see how it's used.

New MCP primitives: `extensions action=project_memory_get {project_id, key}` / `project_memory_set {project_id, key, value}` / `project_memory_list {project_id, key_prefix?}`. Storage: sqlite table `project_memory (project_id, key, value, updated_at, updated_by, version)`. Visible to any branch run whose inputs include matching project_id; writes require `actor == updated_by` OR admin. Nodes read via `{project_memory.key}` substitution shape OR explicit input_keys wiring — defer which interface to dev; both workable.

**Orthogonality to chatbot-native user prefs** (memory `project_user_prefs_chatbot_native`): that memory covers **per-user preferences** held in the chatbot's own memory primitive. This spec covers **cross-branch aggregate facts about a project** (e.g. "this repo uses pytest not unittest" — not a user pref, a discovered project fact that a later run benefits from). Different kind of memory, different scope, no conflict.

**Files:** `workflow/memory/` new submodule, `workflow/universe_server.py` (actions), tests.

**Invariants:** project_memory writes append-only history (audit trail for moderation); no cross-project reads without explicit project_id; size cap per-project (1MB total default) to prevent DoS; respects privacy tier of the branch that writes (memory `project_privacy_per_piece_chatbot_judged`); `version` field supports optimistic concurrency (write requires matching `expected_version` or 200-on-conflict).

**Tests:** set+get roundtrips; list with prefix; cross-project isolation; size cap rejects oversize writes; concurrent write with mismatched version returns conflict; version increments monotonically per project_id+key.

**Vetted:** 2026-04-22 by navigator (re-tightened: explicitly flag "what is a project" as deferred follow-up rather than silently decide via the opaque-string shape; name chatbot-native-prefs orthogonality per lead correction on two-halves audit).

**Deferred follow-up (separate future spec, not this one):** project-identity primitive — auto-detect project from repo context, project lifecycle events, relationship to goal_id, project-settings substrate. Re-open once we see real usage patterns.

---

## file_bug is the feature-request verb — docstring + optional kind field

**Scope:** Per navigator memory `project_bug_reports_are_design_participation`, `file_bug` IS the feature-request surface. Rename / expand: (a) update `wiki action=file_bug` docstring to name "bug, feature request, design proposal, primitive ask" as the same channel; (b) add an optional `kind` field to frontmatter with values `bug | feature | design`; default `bug` preserves compat; (c) add a `tags` convention in docstring guiding chatbots to classify. No new verb. No schema migration — old BUG-* pages remain.

**Files:** `workflow/universe_server.py` (file_bug docstring + optional kind field), wiki template, tests.

**Invariants:** existing BUG-* pages remain valid without frontmatter migration; kind=feature filings land in the same pipeline (navigator vets both); docstring makes the design-participation rule discoverable from the tool surface itself.

**Tests:** file_bug with no kind = bug; file_bug kind=feature annotates frontmatter correctly; missing kind reads as bug.

**Vetted:** 2026-04-22 by navigator. Reshape of user-submitted "no file_feature_request verb" ask — reframe not implement, per host framing memory.

---

## Prompt_template literal-brace escape + build-time missing-key validation

**Scope:** Three additive changes to `workflow/graph_compiler.py` + `workflow/branches.py`. (A) Add backslash-escape pass: identifier wrapped in backslash-brace pair renders literally as `{ident}` without substitution; runs after Jinja→Python normalizer, before single-brace substitution; `_missing_state_keys` skips escaped refs. (B) Extend `BranchDefinition.validate()` with per-node placeholder scan — each `{ident}` must exist in `input_keys` ∪ `state_schema` names; validation error with node+key otherwise. Runtime `CompilerError` stays as second layer. (C) Fix docstring at `graph_compiler.py:11-13` (falsely claims `str.format_map`).

**Files:** `workflow/graph_compiler.py`, `workflow/branches.py`, tests.

**Invariants:** Jinja `{{ident}}` = substitute unchanged (ecosystem compat); non-identifier braces still pass through verbatim; Parts A+B+C ship together.

**Tests:** backslash-escape renders literal; single-brace substitutes; double-brace normalized+substitutes; build-time catches undeclared ref; build-time does NOT flag escaped refs; JSON `{"key": "val"}` passes through.

**Vetted:** 2026-04-22 by navigator. Reshape of user-submitted "double-braces should be literal" ask — filer's proposed fix would silently break every existing Claude.ai-authored template. Full design rationale: `pages/plans/feature-prompt-template-literal-braces-and-build-time-validation.md` (navigator-authored).
