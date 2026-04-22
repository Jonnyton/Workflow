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

## In-flight run recovery — part 2 (SqliteSaver-keyed resume)

**Strategy decisions (host-answered 2026-04-22, baked into spec):** (a) **Temporal-parity YES** — override v1's "no resume" comment in `runs.py:1417-1419`. Industry has moved; durable execution is table stakes for 2026 agentic systems. (b) **Multi-tenant auth re-check YES, strict** — re-verify caller identity + quota at resume time (session tokens may have rotated, paid-market claim authority must re-validate). (c) **Idempotency step-level via SqliteSaver** — committed steps skip on resume; in-flight step re-executes from scratch. Within-step nodes must be authored to tolerate retry; keyed side effects by `run_id + step_id`. (d) **Cost-neutral** under the node-escrow model (memory `project_node_escrow_and_abandonment`): money locks on the node at claim, resume doesn't double-charge, abandoned work forfeits unearned segment to whoever picks it up. See "Economic semantics" below.

**Scope:** Add `extensions action=resume_run {run_id}`. Flow:

1. **Identity gate.** `_current_actor()` must match run's `actor` field OR admin. Session token must be currently valid for that actor (re-check, not cached). Paid-market runs additionally re-verify the actor still has claim authority over the node escrow attached to this run. Auth failure → `403`-shaped error; no leak of whether run exists.

2. **Status gate.** Run must be in `INTERRUPTED` status. Any other status (`COMPLETED`, `FAILED`, `RUNNING`, `RESUMED` already) → structured error naming current status and the expected transition. Idempotency: resuming a `RESUMED` run returns the existing resumed run_id without spawning a second resume.

3. **Checkpoint load.** Load SqliteSaver checkpoint keyed by `run_id` (thread_id = run_id). If missing (e.g. SqliteSaver storage evicted or pre-resume-feature run), return structured error directing caller to rerun with `run_branch` + same `inputs_json`.

4. **Compile + resume.** Re-compile branch (branch defs may have been patched since original run — use the branch version pinned in runs.branch_version to compile the exact shape; reject resume if that version no longer exists). Call `graph.astream(None, config={"configurable": {"thread_id": run_id}})` — LangGraph resumes from last committed state.

5. **State transitions.** Set status `RESUMED` at resume-call time; flip to `RUNNING` once first node emits; terminal states (`COMPLETED`/`FAILED`/`INTERRUPTED`) land same as fresh runs. Emit `resume_started` event to runs.events carrying `resume_actor`, `resumed_at`, `last_committed_step_id`.

6. **Node-level retry semantics.** In-flight step at interrupt time re-executes from scratch. Document in spec + node-author guide: **any node that performs side effects (wiki writes, canon updates, external HTTP calls, paid-market escrow claims) MUST key side effects by `(run_id, step_id)` so retry is idempotent.** Provide a helper `workflow/idempotency.py` with `@idempotent_by_step` decorator for code-node authors. Prompt-template nodes are naturally idempotent (LLM call produces fresh output; SqliteSaver captures the commit).

**Economic semantics (per `project_node_escrow_and_abandonment`):**
- Resume within the abandonment grace window by the **original claimer** = same ownership, same earning path, no escrow change.
- Resume after grace by a **different daemon** = treated as a new claim on the abandoned segment. Escrow stays on the node; new claimer earns the unearned segment on completion; original claimer forfeits unearned segment (earned segment from checkpoints already paid out, if any).
- Resume does NOT amplify cost — the node-escrow unit is the node, not the attempt. Provider calls for already-committed steps are skipped; only the in-flight step's provider call re-runs, which is already paid for out of the node's escrow.

**Files:** `workflow/runs.py` (resume_run helper, status transitions, idempotency key schema, branch_version pinning validation), `workflow/universe_server.py` (`_action_resume_run` + auth re-check + paid-market claim-authority re-verify), `workflow/idempotency.py` NEW module (decorator + helper for code-node side-effect keying), `workflow/graph_compiler.py` (ensure node callables tolerate SqliteSaver resume — read committed-steps-so-far to skip cleanly), tests.

**Invariants:** resume requires strict auth re-check against current session token (no cached token reuse); resume rejects non-INTERRUPTED runs with a structured error naming current status; resume of RESUMED returns existing resumed-run_id (idempotent call); branch_version mismatch (branch patched since original run) rejects resume with clear error; side-effect nodes use `idempotent_by_step` keying — a helper-registry-lint fails pre-commit if a code-node with `requires_idempotent_retry=true` doesn't use the decorator; escrow ledger never double-credits a completed step.

**Tests:** successful resume of INTERRUPTED run completes remaining nodes; resume by non-owner rejected 403-shaped; resume of COMPLETED rejected with status-mismatch error; resume-of-RESUMED returns same run_id no second resume; missing checkpoint (evicted SqliteSaver state) returns structured rerun-suggestion error; branch_version mismatch rejected; in-flight step re-executes from scratch (verified via provider_call spy); committed steps do NOT re-execute (spy shows zero additional calls for pre-checkpoint nodes); node with `@idempotent_by_step` side effect does not duplicate that effect on retry; escrow ledger shows no double-credit on resumed completion.

**Vetted:** 2026-04-22 by navigator. Host answered all four strategy questions; spec now dev-dispatchable with economic semantics tied to `project_node_escrow_and_abandonment` memory. Supersedes the strategy-open state from the earlier pass.

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

**Strategy rationale (expanded per lead concern on depth of strategy pass):** The filer named three distinct use cases — scheduled aggregators, event-triggered runs (PR-open, deploy-failure, canon-upload, user-action), and upstream-dependency chaining (branch-run-completed → next-branch-run). All three are the **difference between "a daemon you call" and "a daemon that runs on its own"** — which is the core Forever-Rule ambition (`24/7 uptime with zero hosts online`, `project_always_up_auto_heal`: system always up and self-healing, host is just another contributor). Without this primitive there's no substrate for: (a) nightly stats-rollup branches; (b) PR-triggered review branches; (c) daemon-host-independence because nothing currently triggers work without a user imperative call. This is load-bearing for the always-up vision, not just a convenience.

**Multi-tenant implications (named explicitly per lead flag):** A schedule or subscription is owned by a user (the actor who registered it). Invariants: (1) schedule rows carry `owner_actor`; only the owner + admin can unregister. (2) Event subscriptions fire the subscribed branch with `actor=subscriber:<owner>`, not `actor=event-source` — so the run is billed/attributed to the subscriber, not to whoever triggered the event. (3) Rate-limit per-owner on schedule count + subscription count (default 20 of each) to prevent one user filling the scheduler table. (4) Scheduled runs obey the same paid-market bid economics as manual runs — auto-scheduled expensive work still requires the owner to have budget; if not, schedule pauses with a clear state and notifies owner.

**Scope:** Two new primitives: (1) `extensions action=schedule_branch` `{branch_def_id, cron_or_interval, inputs_template}` registers a schedule; runner invokes `run_branch` per schedule; scheduled runs tag `actor=scheduler:<schedule_id>` with `owner_actor=<registrar>`. (2) `extensions action=subscribe_branch` `{branch_def_id, event_type, inputs_mapping}` registers an event subscription; events include `canon_change`, `branch_run_completed:{branch_def_id}`, `pr_open`, `canon_upload`. Runner emits these events internally + exposes event bus to external producers. Persistence: SQLite tables for schedules + subscriptions; survives daemon restart via restart recovery loop.

**Files:** `workflow/runs.py` (schedule table + event table + recovery), `workflow/universe_server.py` (actions + owner-gated unregister), `workflow/scheduler.py` new module (tick loop), tests.

**Invariants:** schedule fires on wall-clock regardless of in-flight runs (last-run can overlap next tick; configurable `skip_if_running`); event subscription fires exactly once per event (idempotency keyed on event_id); removal of a schedule/subscription is immediate + only by owner/admin (no orphan firings); inputs_template validates at registration time against branch's schema; rate-limit 20 active schedules + 20 subscriptions per owner_actor (configurable); scheduler survives daemon restart via recovery hook.

**Tests:** cron schedule fires at expected times (fake clock); interval schedule respects skip_if_running; event subscription fires on emitted event; subscription unregister by non-owner rejected; rate-limit rejects 21st active schedule per owner; daemon restart recovers schedule table + resumes ticking; scheduled run carries owner_actor correctly for billing attribution.

**Vetted:** 2026-04-22 by navigator (re-expanded strategy + multi-tenant invariants per lead concern on depth of original pass).

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

---

## Node checkpoints — partial-credit boundaries authored into node_def

**Strategy rationale:** `project_node_escrow_and_abandonment` makes the node the unit of money. All-or-nothing at the node boundary is fine for small nodes but gets brutal on 6-hour nodes where a crash at the 5th hour forfeits everything. Host directive 2026-04-22: user-authored checkpoints are the partial-credit lever. A daemon that runs 2h on a 6h node + hits checkpoint = paid for that segment, forfeits only post-checkpoint. Ships alongside the gate-bonus primitive as a pair — checkpoints handle within-node partial credit, gate bonuses handle cross-node milestone incentives. Both are load-bearing for the paid-market incentive design to be humane to honest daemon hosts.

**Scope:** Extend `NodeDefinition` with `checkpoints: list[dict] = field(default_factory=list)`. Each entry shape: `{checkpoint_id: str (unique within node), earns_fraction: float (0.0-1.0, cumulative sum must not exceed 1.0 across all checkpoints), reached_when: dict}` where `reached_when` is a predicate authored declaratively over state — initial shape `{"state_key": "...", "value": <any>}` or `{"state_key": "...", "exists": true}` meaning "this checkpoint fires when that state field is present / matches". Prompt-template node authors place checkpoints at meaningful prose-output milestones; code-node authors can emit explicit `__checkpoint__("ckpt_id")` calls that map to the declared entries (decorator helper in `workflow/idempotency.py`).

**Runtime:** When the node is running, after each step-commit via SqliteSaver, runner evaluates `reached_when` against committed state. Matching checkpoints fire once; runs.events gets `checkpoint_reached {node_id, checkpoint_id, earns_fraction, at_step}`. Escrow ledger credits `earns_fraction * node_stake` to the running claimer (persistent even on subsequent abandonment). Default (no checkpoints declared) = all-or-nothing = current behavior.

**Abandonment + resume interaction:** post-checkpoint abandonment = claimer keeps earned fraction, next claimer starts from the remaining escrow + earns from future checkpoints + completion. Resume by original claimer within grace = no ledger change, continues earning. `project_node_escrow_and_abandonment` "crash-between-checkpoints" rule: unearned segment forfeits.

**Files:** `workflow/branches.py` (checkpoints field + validation — cumulative_earns_fraction ≤ 1.0, unique checkpoint_ids within node), `workflow/graph_compiler.py` (post-step checkpoint evaluator), `workflow/runs.py` (checkpoint_reached event emission, ledger credit hook), `workflow/idempotency.py` (checkpoint decorator helper for code nodes), tests.

**Invariants:** checkpoints fire at most once per run; cumulative earns_fraction across a node's checkpoints ≤ 1.0 (validation error if exceeded); checkpoint ledger credit is transactional with the step commit that fires it (never credit without commit); abandoned runs preserve already-credited fractions; resume within grace does not re-credit already-fired checkpoints.

**Tests:** node with two 0.5 checkpoints fires both on completion and credits fully; node with 0.3 + 0.3 + 0.4 credits progressively; checkpoint does not fire twice if state matches again after resume; cumulative > 1.0 rejected at build; abandonment between checkpoints = claimer keeps credited, forfeits uncredited; cumulative = 0.0 (no checkpoints) = all-or-nothing current behavior.

**Deferred follow-up questions** (from memory, not this spec): grace-window duration; whether all-or-nothing stays default vs shifts to "at least one mandatory checkpoint per node." Ship opt-in checkpoints first; iterate on defaults once usage data exists.

**Vetted:** 2026-04-22 by navigator. New spec queued from host directive `project_node_escrow_and_abandonment` — not originally in the wiki bug queue; navigator-generated to support the resume-run part-2 economic semantics.

---

## Gate bonuses — staked payouts attached to gate milestones

**Strategy rationale:** `project_node_escrow_and_abandonment` introduces gate bonuses as "quality-vs-speed lever built into the economy." Base stake pays for the node reaching completion; gate bonus pays extra for passing declared gate milestones. Slow daemon hitting all gates earns more than fast daemon missing them. Pairs with the existing `gates` surface (flag-gated behind `GATES_ENABLED`) — extending that primitive rather than inventing a parallel one. Aligns with `project_evaluation_layers_unifying_frame`: gates are one face of the unified Evaluator primitive, staked bonuses turn them into economic feedback loops.

**Scope:** Extend gate claims with an optional bonus stake. `gates action=claim {goal_id, branch_def_id, node_id, milestone, bonus_stake?}`. When `bonus_stake > 0` and the Paid-Market flag is on, stake is locked from the claimer's budget alongside the node's base stake. On gate pass (claim marked satisfied by the gate's configured verifier — human-attested, automated-metric-passed, or chatbot-judged per goal config), bonus releases to the daemon that held the node's last claim at pass-time. On gate fail (verifier rejects) or gate-stale (pass timeout exceeded), bonus refunds to the claimer who staked it — stake is at-risk for the claimer if the gate never resolves, defaulting to refund after a configurable `gate_stake_timeout_days` (default 30).

**Schema addition:** `gate_claims.bonus_stake` column (int, smallest currency unit — matches existing stake precision) + `gate_claims.bonus_refund_after` timestamp. Existing gate claim rows without bonuses unchanged (default 0). The **node** the bonus is attached to must be in the same branch_def as the gate's scope — prevents cross-branch bonus attachments that would complicate escrow tracking.

**Multi-tenant invariants:** only the original bonus-staker can unstake (before gate resolves); bonus release goes to whoever holds the node's last claim at gate-pass-time (not necessarily the original claimer — this is intentional; encourages daemons to pick up abandoned high-gate-value nodes); refund on timeout goes to staker, not to any daemon. Paid-market flag must be on; gate bonuses silently unavailable (zero-cost default) when `WORKFLOW_PAID_MARKET=off`.

**Files:** `workflow/gates/` (schema migration for bonus_stake column, claim/unstake/release helpers), `workflow/universe_server.py` (`gates` action extensions: bonus_stake arg on claim, unstake action), `workflow/payments/` or wherever escrow ledger lives (add bonus-release path distinct from base-stake), tests.

**Invariants:** bonus_stake only locked when `GATES_ENABLED=on` AND `WORKFLOW_PAID_MARKET=on`; bonus release goes to node's last-claimer at gate-pass-time (may differ from bonus-attacher — abandonment-reward dynamic); unstake allowed only by original staker and only while gate is unresolved; refund-on-timeout fires deterministically at `bonus_refund_after`; gate failure or retraction refunds bonus to staker; bonus_stake precision matches base-stake (same currency unit, no rounding ambiguity).

**Tests:** claim + bonus_stake locks budget correctly; gate pass releases bonus to last-claimer; gate fail refunds bonus to staker; unstake by non-staker rejected; unstake after gate resolves rejected; cross-branch bonus attachment rejected at claim; PAID_MARKET=off silently ignores bonus_stake (zero-cost default); gate timeout refunds correctly.

**Deferred follow-up:** chatbot-judged gate verification (separate spec — `project_evaluation_layers_unifying_frame` Evaluator primitive lands that); bonus-splitting across multiple daemons that shared a node via checkpoints (open design Q — probably pro-rata by earned fractions).

**Vetted:** 2026-04-22 by navigator. New spec queued from host directive `project_node_escrow_and_abandonment` — not originally in the wiki bug queue; navigator-generated to support the paid-market quality-vs-speed lever.
