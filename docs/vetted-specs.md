# Navigator-vetted specs

Specs for user-submitted ideas — bugs, feature requests, design proposals — that have cleared both navigator passes (safety + strategy). Dev reads from this file. Lead dispatches from this file. When a spec lands in code, both the pointer row in `STATUS.md` and the H2 section here are removed together (commit is the record).

This file is **navigator-owned and git-tracked, never wiki-writable.** No `BUG-NNN` cross-references — titles are descriptive. Each H2 heading is the anchor; slug-ify the heading to get the `#anchor` in pointer rows.

Rule context: `feedback_wiki_bugs_vet_before_implement` + `project_bug_reports_are_design_participation`.

---

## Per-node llm_policy override

**Scope:** Today `NodeDefinition.model_hint` → `role` drives the role-based provider router. User ask: `(provider, model, reasoning_effort)` pinning + fallback chain + difficulty override — supersets role-routing without replacing it. Add `llm_policy: dict | None = None` on NodeDefinition. Shape: `{preferred: {provider, model, reasoning_effort?}, fallback_chain: [{provider, model, trigger: "unavailable"|"rate_limited"|"cost_exceeded"|"empty_response"}], difficulty_override: [{if_difficulty, use: {provider, model}}]}`. Runner resolves preferred → fallback_chain → difficulty_override at dispatch time. Branch-level `default_llm_policy` applies to nodes without their own. Emit actual provider served into activity log + get_node_output. When `llm_policy` unset, fall back to existing role-based routing (backward-compat).

**Files:** `workflow/branches.py` (add field, pass through in serializer), `workflow/graph_compiler.py` (consume + resolve), `workflow/providers/router.py` (accept explicit provider/model override + fallback triggers), tests.

**Invariants:** unset llm_policy = current behavior (no regression); fallback chain must exhaust before raising; provider choice observable via activity log.

**Tests:** pinned preferred used when available; fallback fires on each trigger class; difficulty override routes correctly; branch-default applies when node-level unset; unset = role-routing backward-compat.

**Sibling per-node policy** (`project_daemon_souls_and_summoning` host directive 2026-04-22): a `soul_policy` field will land alongside `llm_policy` as a second per-node authoring decision (deferred; see deferred section below). When `soul_policy` ships, coordinate the build/patch-branch authoring UX so both fields are surfaced together — they're conceptual siblings (both shape how the daemon behaves on that node) and should share the same spec_json authoring shape.

**Vetted:** 2026-04-22 by navigator.

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

**Overlap with branch-contribution ledger + attribution chain** (`project_daemon_souls_and_summoning` + `project_designer_royalties_and_bounties` host directives 2026-04-22): invoke_branch already tracks `child run_id linked to parent run_id` in the runs table — that linkage is the plumbing the deferred branch-contribution ledger AND the deferred attribution-chain primitive both build on. When those specs land, expect the child-parent linkage schema here to extend with `(daemon_id, step_count, earned_fraction, parent_author_ref, lineage_depth)` rows for proportional bonus distribution + lineage royalty routing. No change to this spec; implementation should ensure the linkage is schema-friendly to future ledger + lineage rows (not collapsed into opaque parent_run_id string — preserve parent branch_def_id, parent run_id, parent author_id as separate columns from the start).

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

## Node checkpoints — partial-credit boundaries authored into node_def

**Strategy rationale:** `project_node_escrow_and_abandonment` makes the node the unit of money. All-or-nothing at the node boundary is fine for small nodes but gets brutal on 6-hour nodes where a crash at the 5th hour forfeits everything. Host directive 2026-04-22: user-authored checkpoints are the partial-credit lever. A daemon that runs 2h on a 6h node + hits checkpoint = paid for that segment, forfeits only post-checkpoint. Ships alongside the gate-bonus primitive as a pair — checkpoints handle within-node partial credit, gate bonuses handle cross-node milestone incentives. Both are load-bearing for the paid-market incentive design to be humane to honest daemon hosts.

**Scope:** Extend `NodeDefinition` with `checkpoints: list[dict] = field(default_factory=list)`. Each entry shape: `{checkpoint_id: str (unique within node), earns_fraction: float (0.0-1.0, cumulative sum must not exceed 1.0 across all checkpoints), reached_when: dict}` where `reached_when` is a predicate authored declaratively over state — initial shape `{"state_key": "...", "value": <any>}` or `{"state_key": "...", "exists": true}` meaning "this checkpoint fires when that state field is present / matches". Prompt-template node authors place checkpoints at meaningful prose-output milestones; code-node authors can emit explicit `__checkpoint__("ckpt_id")` calls that map to the declared entries (decorator helper in `workflow/idempotency.py`).

**Runtime:** When the node is running, after each step-commit via SqliteSaver, runner evaluates `reached_when` against committed state. Matching checkpoints fire once; runs.events gets `checkpoint_reached {node_id, checkpoint_id, earns_fraction, at_step}`. Escrow ledger credits `earns_fraction * node_stake` to the running claimer (persistent even on subsequent abandonment). Default (no checkpoints declared) = all-or-nothing = current behavior.

**Abandonment + resume interaction:** post-checkpoint abandonment = claimer keeps earned fraction, next claimer starts from the remaining escrow + earns from future checkpoints + completion. Resume by original claimer within grace = no ledger change, continues earning. `project_node_escrow_and_abandonment` "crash-between-checkpoints" rule: unearned segment forfeits.

**Files:** `workflow/branches.py` (checkpoints field + validation — cumulative_earns_fraction ≤ 1.0, unique checkpoint_ids within node), `workflow/graph_compiler.py` (post-step checkpoint evaluator), `workflow/runs.py` (checkpoint_reached event emission, ledger credit hook), `workflow/idempotency.py` (checkpoint decorator helper for code nodes), tests.

**Invariants:** checkpoints fire at most once per run; cumulative earns_fraction across a node's checkpoints ≤ 1.0 (validation error if exceeded); checkpoint ledger credit is transactional with the step commit that fires it (never credit without commit); abandoned runs preserve already-credited fractions; resume within grace does not re-credit already-fired checkpoints.

**Tests:** node with two 0.5 checkpoints fires both on completion and credits fully; node with 0.3 + 0.3 + 0.4 credits progressively; checkpoint does not fire twice if state matches again after resume; cumulative > 1.0 rejected at build; abandonment between checkpoints = claimer keeps credited, forfeits uncredited; cumulative = 0.0 (no checkpoints) = all-or-nothing current behavior.

**Deferred follow-up questions** (from memory, not this spec): grace-window duration; whether all-or-nothing stays default vs shifts to "at least one mandatory checkpoint per node." Ship opt-in checkpoints first; iterate on defaults once usage data exists.

**Fair-distribution input** (`project_designer_royalties_and_bounties` host directive 2026-04-22): the checkpoint ledger (per-claimer `earned_fraction` per node) is one load-bearing input to navigator's fair-weighting of outcome-bonus payouts. When multiple daemons contribute to a node across abandonment/resume cycles, the checkpoint ledger tells navigator exactly who earned what fraction — making partial-credit distribution computable rather than adjudicated from scratch. Schema should keep `(run_id, node_id, claimer_daemon_id, checkpoint_id, earned_fraction, credited_at)` durable so the fair-distribution calculator (deferred spec below) can query it directly.

**Vetted:** 2026-04-22 by navigator. New spec queued from host directive `project_node_escrow_and_abandonment` — not originally in the wiki bug queue; navigator-generated to support the resume-run part-2 economic semantics.

---

## Gate bonuses — staked payouts attached to gate milestones (node-scoped variant)

**Strategy rationale:** `project_node_escrow_and_abandonment` introduces gate bonuses as "quality-vs-speed lever built into the economy." Base stake pays for the node reaching completion; gate bonus pays extra for passing declared gate milestones. Slow daemon hitting all gates earns more than fast daemon missing them. Pairs with the existing `gates` surface (flag-gated behind `GATES_ENABLED`) — extending that primitive rather than inventing a parallel one. Aligns with `project_evaluation_layers_unifying_frame`: gates are one face of the unified Evaluator primitive, staked bonuses turn them into economic feedback loops.

**Two attachment scopes (per `project_daemon_souls_and_summoning`):** gates can attach to **a single node** (this spec — single-daemon bonus on gate pass, as specced below) OR to **a whole branch** (follow-up spec `branch-scoped gate bonuses with multi-daemon distribution` — deferred, depends on the branch-contribution ledger in the deferred section below). This spec covers the node-scoped variant only.

**Scope:** Extend gate claims with an optional bonus stake. `gates action=claim {goal_id, branch_def_id, node_id, milestone, bonus_stake?}`. When `bonus_stake > 0` and the Paid-Market flag is on, stake is locked from the claimer's budget alongside the node's base stake. On gate pass (claim marked satisfied by the gate's configured verifier — human-attested, automated-metric-passed, or chatbot-judged per goal config), bonus releases to the daemon that held the node's last claim at pass-time. On gate fail (verifier rejects) or gate-stale (pass timeout exceeded), bonus refunds to the claimer who staked it — stake is at-risk for the claimer if the gate never resolves, defaulting to refund after a configurable `gate_stake_timeout_days` (default 30).

**Schema addition:** `gate_claims.bonus_stake` column (int, smallest currency unit — matches existing stake precision) + `gate_claims.bonus_refund_after` timestamp + `gate_claims.attachment_scope: Literal['node','branch']` (this spec only ships `node`; branch variant lands in the follow-up). Existing gate claim rows without bonuses unchanged (default attachment_scope='node', bonus_stake=0). The **node** the bonus is attached to must be in the same branch_def as the gate's scope — prevents cross-branch bonus attachments that would complicate escrow tracking.

**Multi-tenant invariants:** only the original bonus-staker can unstake (before gate resolves); bonus release goes to whoever holds the node's last claim at gate-pass-time (not necessarily the original claimer — this is intentional; encourages daemons to pick up abandoned high-gate-value nodes); refund on timeout goes to staker, not to any daemon. Paid-market flag must be on; gate bonuses silently unavailable (zero-cost default) when `WORKFLOW_PAID_MARKET=off`.

**Files:** `workflow/gates/` (schema migration for bonus_stake + attachment_scope columns, claim/unstake/release helpers), `workflow/universe_server.py` (`gates` action extensions: bonus_stake arg on claim, unstake action), `workflow/payments/` or wherever escrow ledger lives (add bonus-release path distinct from base-stake), tests.

**Invariants:** bonus_stake only locked when `GATES_ENABLED=on` AND `WORKFLOW_PAID_MARKET=on`; `attachment_scope='node'` bonus release goes to node's last-claimer at gate-pass-time (may differ from bonus-attacher — abandonment-reward dynamic); `attachment_scope='branch'` rejected at claim time in this spec (returns "branch-scope gate bonuses not yet implemented; see deferred spec"); unstake allowed only by original staker and only while gate is unresolved; refund-on-timeout fires deterministically at `bonus_refund_after`; gate failure or retraction refunds bonus to staker; bonus_stake precision matches base-stake (same currency unit, no rounding ambiguity).

**Tests:** claim + bonus_stake locks budget correctly; gate pass releases bonus to node's last-claimer; gate fail refunds bonus to staker; unstake by non-staker rejected; unstake after gate resolves rejected; cross-branch bonus attachment rejected at claim; attachment_scope='branch' rejected with clear not-yet-implemented error; PAID_MARKET=off silently ignores bonus_stake (zero-cost default); gate timeout refunds correctly.

**Deferred follow-ups (separate specs, not this one):**
- **Branch-scoped gate bonuses with multi-daemon distribution** — attachment_scope='branch'; payout splits across all daemons that contributed to the branch, proportional to step-count or earned-fraction per `project_daemon_souls_and_summoning`. Uses the deferred branch-contribution ledger + attribution-chain plumbing for distribution (both in deferred section below) + `project_designer_royalties_and_bounties` fair-weighting for cross-layer splits (claimer vs node-author vs branch-author vs remix-lineage).
- Chatbot-judged gate verification (separate spec — `project_evaluation_layers_unifying_frame` Evaluator primitive lands that).
- Bonus-splitting across multiple daemons that shared a single node via checkpoints (open design Q — probably pro-rata by earned fractions; fair-distribution calculator deferred spec routes this).

**Vetted:** 2026-04-22 by navigator. New spec queued from host directive `project_node_escrow_and_abandonment`; attachment_scope field added per `project_daemon_souls_and_summoning` to preserve forward-compat with branch-scoped variant.

---

# Navigator-promoted 2026-04-23

Eight specs promoted in one pass from plan-page mentions to formally-vetted, dev-dispatchable specs. Source: navigator's 2026-04-23 full-corpus synthesis (`docs/audits/2026-04-23-navigator-full-corpus-synthesis.md`). These were already implicitly ratified in `strategic-synthesis-2026-04-24`, `tier-1-investigation-routing-resolver`, `chatbot-builder-behaviors`, and user-sim mission drafts — promoted here so dev can claim them individually. Dispatch-order notes per spec; internal dependencies surfaced in each.

---

## dry_inspect_node — preview a build/patch before it commits

**Strategy rationale:** Chatbot-builder-behaviors page already demands "show work before running" as a trust primitive. User-sim mission drafts (Priya L1 §2, Devin M27 §2) both fail-bar on "dry-inspect before mutation." Today the chatbot has to reconstruct what would change by reading state and re-inferring — a fragile pattern. First-class `dry_inspect_node` makes the preview architectural rather than emergent behavior, and lets the chatbot narrate what will change with structured evidence.

**Scope:** Add MCP action `extensions action=dry_inspect_node` accepting `{branch_def_id, node_id?}` OR `{branch_spec_json, node_id?}` (latter lets chatbot preview a would-be-built node before calling `build_branch`). Returns `{node_def: {...}, resolved_prompt_template: str, declared_input_keys: [...], declared_output_keys: [...], state_schema_refs: [...], placeholder_validation: {missing: [], extra: [], escaped: []}, policy_resolution: {llm_role, fallback_chain, effective_policy}, warnings: [...]}`. No state writes, no side effects. Companion verb `dry_inspect_patch` accepts `{branch_def_id, changes_json}` and returns the same shape post-hypothetical-patch so the chatbot can show "before/after" diffs to the user before committing the real patch.

**Files:** `workflow/universe_server.py` (two new action handlers), `workflow/graph_compiler.py` (extract existing-prompt-resolution + placeholder-validation into a side-effect-free helper callable outside run context), `workflow/branches.py` (factor out node-policy-resolution into a dry-callable), tests.

**Invariants:** zero state writes, zero wiki writes, zero provider calls (pure structural preview); works on branches that have never been run; works on spec_json that hasn't been built yet; placeholder_validation surfaces the same messages build-time `_missing_state_keys` would emit; policy_resolution output matches what the runtime router would pick at dispatch time (run the same resolver helper, don't re-implement).

**Tests:** dry_inspect of existing node returns full envelope; dry_inspect of non-existent node_id returns structured 404; dry_inspect_patch on add_node op returns the would-be node without mutating; dry_inspect surfaces missing placeholder in validation block; no provider calls observed via spy during dry_inspect; tests cover the spec_json pre-build path (branch that doesn't exist yet).

**Vetted:** 2026-04-23 by navigator. Promoted from plan-page mentions in `chatbot-builder-behaviors` + user-sim mission draft chain-break risks (Priya L1 §2, Devin M27 §2). Substantially the "self-auditing-tools pattern" (design-note `docs/design-notes/2026-04-19-self-auditing-tools.md`) extended to mutation-verb previews.

---

## recursion_limit_override — expose LangGraph recursion cap on run_branch

**Strategy rationale:** `tier-1-investigation-routing-resolver` Step 6 names this as an independent ship-even-if-routing-investigation-finds-nothing. Evidence from runs `9a7329466c774732` + `16c543c154c94a54`: LangGraph's default `recursion_limit=25` is too tight for modern iterative agent graphs — even single-pass conditional-edge graphs hit it. The routing investigation may reduce per-iteration step consumption; but the cap being un-exposed makes any retry_budget > 2 unusable regardless of fix quality.

**Scope:** Add optional `recursion_limit_override: int | None = None` param on `extensions action=run_branch`. When set, passes through to LangGraph's `config={"configurable": {"thread_id": ...}, "recursion_limit": N}`. When unset, uses new default = 100 (raised from 25). Valid range: 10-1000 (guardrail against absurd values). Emit the applied limit in `runs.events` as `recursion_limit_applied: N` so the chatbot can see what was actually used. `get_run` response includes `recursion_limit` so post-hoc analysis can see it. `GraphRecursionError` at runtime produces a structured error carrying the limit + recommendation to raise it.

**Files:** `workflow/universe_server.py` (run_branch action param), `workflow/graph_compiler.py` or wherever `graph.astream` is called (thread config assembly), `workflow/runs.py` (event emission + get_run surfacing), tests.

**Invariants:** unset = default 100 (raised from 25 = intentional baseline bump); value outside 10-1000 rejected at dispatch with clear error; recursion_limit_applied event fires once per run; GraphRecursionError surfaces structured error naming the limit; no change to existing retry_budget semantics.

**Tests:** unset uses 100; override=50 uses 50; override=5 rejected (below min); override=2000 rejected (above max); GraphRecursionError structured with limit value; recursion_limit visible on get_run; event emitted in runs.events.

**Vetted:** 2026-04-23 by navigator. Promoted from `tier-1-investigation-routing-resolver` Step 6 — independent of routing investigation findings. Ships standalone; compose with Tier 1 fix when that lands.

---

## storage_inspect — per-subsystem disk observability surface

**Strategy rationale:** 2026-04-23T20:30Z P0 (disk full, 18h dark before that class) + BUG-023 re-authored. Forever rule (24/7 uptime, zero hosts online) requires that the daemon know its own storage state and surface it to operators before the wall is hit. Today `get_status` exposes no disk info — operator cannot tell from an MCP probe whether the volume is at 50% or 98%. Phase-1 of the BUG-023 fix scope.

**Scope:** Extend `get_status` with a `storage_utilization` block:

```
storage_utilization: {
  volume_percent: float,  # 0.0-1.0, root volume usage
  volume_bytes_total: int,
  volume_bytes_free: int,
  per_subsystem: {
    run_transcripts: {bytes: int, path: str, rotation_policy?: str},
    knowledge_db: {bytes: int, path: str},
    story_db: {bytes: int, path: str},
    lance_indexes: {bytes: int, path: str},
    checkpoint_db: {bytes: int, path: str},
    wiki: {bytes: int, path: str},
    activity_log: {bytes: int, path: str},
    universe_outputs: {bytes: int, path: str}
  },
  growth_estimate: {
    bytes_per_day_recent: int,  # from last 24h
    days_until_full_at_recent_rate: float | null  # null if growth=0
  },
  pressure_level: Literal['ok','warn','critical']  # warn >=80%, critical >=95%
}
```

Composable: uptime-canary can probe `get_status.storage_utilization.pressure_level` and page on warn/critical. Pushover priority=0 at warn, priority=2 at critical (pairs with existing paging ladder).

**Files:** `workflow/universe_server.py` (`get_status` extension), `workflow/storage/__init__.py` (helpers to walk subsystem paths + aggregate bytes + compute growth rate from activity-log timestamps), tests.

**Invariants:** inspect is read-only (no writes); aggregation walk tolerates missing subsystem paths (returns 0 bytes, not error); growth-rate computation falls back to null when no historical data exists; pressure_level thresholds are hard-coded at this spec level, tunable in later iterations; per_subsystem byte counts are approximate at single-digit MB precision (acceptable for observability).

**Tests:** get_status includes storage_utilization block; missing subsystem path returns 0 bytes not error; pressure_level=warn at 80-94%; pressure_level=critical at >=95%; pressure_level=ok below 80%; growth_estimate=null with no historical data; synthetic-fs test manipulating fake volume_percent exercises all three pressure levels.

**Vetted:** 2026-04-23 by navigator. Phase-1 of BUG-023 (re-authored body). Unblocks Phase-2 rotation, Phase-3 auto-prune, Phase-4 hard-cap (all per BUG-023 proposed-fix scope); can ship independently and compose.

---

## publish_version — content-addressed immutable branch snapshots

**Strategy rationale:** Strategic-synthesis Pillar 1 names `publish_version` as Phase-1 substrate. The forkable-Goals story depends on it: forks without content-addressing are moving targets; a fork published today must be citable verbatim by a gate event two years from now. Today `patch_branch` mutates in-place; there is no primitive for "mint an immutable snapshot of this branch at this moment."

**Scope:** Add MCP action `extensions action=publish_version {branch_def_id, notes?}`. Returns `{branch_version_id: str, content_hash: str, published_at: str, publisher: str, parent_version_id: str?}`. `branch_version_id` is a content-addressed ID (e.g. `<branch_def_id>@<hash_prefix>` or a UUID keyed to content hash — pick one form consistently). Snapshots the full branch (node_defs, edges, conditional_edges, state_schema, entry_point) as a write-once record. `patch_branch` on the underlying branch continues to work on the working version, not the published one. `run_branch` accepts EITHER `branch_def_id` (runs working version) OR `branch_version_id` (runs snapshot version) — caller decides. `describe_branch` + `get_branch` surface both the working version and a `published_versions: [...]` list.

**Companion:** `fork_from: branch_version_id` field on `BranchDefinition` — when set, lineage-tracks which published-version this branch forked from. Paired with `canonical_branch` marker on Goals (separate spec). The three together (publish_version + fork_from + canonical_branch) constitute the forkable-Goals primitive stack.

**Files:** `workflow/branches.py` (new Published-Version storage, hash computation, lineage field), `workflow/storage/` or wherever branches persist (immutable-record table), `workflow/universe_server.py` (publish_version action + branch_version_id handling on run_branch/describe_branch/get_branch), tests.

**Invariants:** published versions are immutable (no update verb; any change is a new publish); content_hash deterministic over canonical serialization of branch; parent_version_id optional and validated to exist when set; run_branch with branch_version_id runs the snapshot verbatim (patches to working version don't affect it); describe_branch distinguishes working-vs-published state clearly.

**Tests:** publish_version mints new branch_version_id; re-publishing same content returns same hash (determinism); post-publish patch_branch on working version does not mutate published snapshot; run_branch on branch_version_id runs the snapshot; fork_from references validate; describe_branch lists published_versions; get_branch on branch_version_id returns the snapshot shape.

**Vetted:** 2026-04-23 by navigator. Promoted from strategic-synthesis Pillar 1 (Phase-1 substrate). Blocks meaningful gate-event attribution and fork lineage — Pillar 1 + Pillar 2 both depend on it. Ships BEFORE gate-event spec (attribution has nothing to attribute to without published versions). Ships AFTER Tier 1 routing investigation (published versions of a broken-routing branch are useless).

---

## canonical_branch — marker on Goals naming the first-experience fork target

**Strategy rationale:** Strategic-synthesis Pillar 1: "Each Goal needs a **canonical starter branch** — the first-experience fork target for new users. Today multiple branches can bind to one Goal with no canonical designation. Missing primitive." Without it, a new user arriving at a Goal has no way to pick a starting point — they're shown all branches bound to the Goal and must guess which represents the best current approach. The Goal library cannot have a meaningful "here's how to start" experience.

**Scope:** Add `canonical_branch_version_id: str | None = None` field on `Goal`. Set via new action `goals action=set_canonical {goal_id, branch_version_id}` (host + goal-author can set; branch must be bound to the Goal + must be a published version, not a working version). `goals action=get` response surfaces canonical; `goals action=list` includes canonical summary per goal. Unset = "no canonical yet" — natural for new Goals; chatbot-side UX treats as "no starter branch recommended yet."

**Invariants surrounding authority:** only Goal-authors + host may set canonical (identity re-check at set time, paid-market compatible); canonical must point to a `branch_version_id` (content-addressed — see `publish_version` spec), not a working `branch_def_id` (enforces "canonical is stable; updates to canonical are deliberate version-bumps, not silent patches"); a Goal may have at most one canonical at a time; changing canonical records the previous canonical in `canonical_branch_history: [{version_id, set_at, set_by, unset_at}]` so lineage survives updates.

**Files:** `workflow/goals.py` or goals storage module (field + history + authority check + set action), `workflow/universe_server.py` (new action handler), tests.

**Invariants:** only published versions valid as canonical (rejects working branch_def_id with structured error); set_canonical re-verifies caller authority; unauthorized set rejected 403-shaped; history preserved across unset/reset; `goals action=get` always returns canonical key (null-valued when unset).

**Tests:** set_canonical by Goal author succeeds; set by non-author rejected; set with branch_version_id that isn't bound to goal rejected; set with working branch_def_id rejected (not a version); history preserved across re-set; unset returns to null; goals action=list surfaces canonical summaries correctly.

**Vetted:** 2026-04-23 by navigator. Promoted from strategic-synthesis Pillar 1 (Goals-as-first-class-coordination-unit). Depends on `publish_version` (canonical must reference a version). Does NOT depend on gate events (canonical can exist before gates fire). Ships after `publish_version` as the next Pillar-1 primitive.

---

## fork_from — content-addressed lineage tracking on branches

**Strategy rationale:** Strategic-synthesis Pillar 1: "**Fork lineage** — who forked from what, tracked automatically so compounding is visible, not silent reinvention." Without it, the library cannot show "branch X was forked by 12 users and improved in 4 directions" — the compounding story that makes the forkable-Goals proposition work. Ships as a thin addition to `BranchDefinition` once `publish_version` is in; the combined feature is the actual Pillar-1 primitive.

**Scope:** Add `fork_from: str | None = None` field on `BranchDefinition`. Value is a `branch_version_id` (content-addressed per `publish_version` spec) — the published version this branch was forked from. Set at branch creation via new optional arg on `build_branch` (`fork_from_version: str | None`) or via `patch_branch` op `set_fork_from`. Immutable-after-set by default (preserves lineage integrity); admin-only override for correction. `describe_branch` + `get_branch` surface `fork_from` + `fork_descendants: [{branch_def_id, author, published_versions_count}]` (descendants computed as branches whose `fork_from` points at any published version of this branch). `goals action=get` includes per-bound-branch fork-count so the leaderboard can surface forking activity.

**Fork descendants visibility:** a new MCP action `extensions action=fork_tree {branch_def_id}` returns the lineage graph — ancestors via `fork_from` chain + descendants via reverse-index. Respects universe isolation (only lineage within the caller's visible universes). Shows fork counts, contributor counts, published-version counts. This is the discovery surface for the forkable-Goals story.

**Files:** `workflow/branches.py` (field, validation), `workflow/universe_server.py` (build_branch arg, patch_branch op, describe_branch + get_branch enrichment, fork_tree action), `workflow/storage/` (reverse-index on fork_from for efficient descendant queries), tests.

**Invariants:** fork_from must point to a valid `branch_version_id` (rejects branch_def_id or non-existent version); fork_from is immutable after set by default (admin override via dedicated flag); fork_tree respects universe isolation (no leakage); descendant counts are eventually-consistent with published versions (indexed); cycles in fork chain rejected at set time.

**Tests:** build_branch with fork_from sets lineage; patch_branch set_fork_from on existing branch adds lineage; set_fork_from pointing at branch_def_id rejected; set_fork_from pointing at non-existent version rejected; fork_tree returns ancestors + descendants; fork_tree respects universe isolation; descendants count matches actual forking activity; cycle-in-chain rejected.

**Vetted:** 2026-04-23 by navigator. Promoted from strategic-synthesis Pillar 1. Depends on `publish_version`. Independent of `canonical_branch` (they're sibling Pillar-1 primitives, not sequential). Ships in the Phase-1 substrate triad (publish_version + canonical_branch + fork_from) — that's the forkable-Goals primitive stack.

---

## gate_event — real-world outcome attestation primitive

**Strategy rationale:** Strategic-synthesis Pillar 2 names real-world gate events as the engine's measurement substrate: "real-world gates are not inline LLM evals. They are world events that declare the work successful." The primitive makes the engine's core claim auditable — a prosecutor filed, a book sold, a paper was peer-reviewed, and this branch's output was cited in that event. Without it, quality is LLM-judged (cluster drift) and attribution is hand-waved (claim-not-cause). With it, the engine becomes the first AI-workflow platform where quality feedback comes from the real world.

**Scope:** New first-class record class (Layer-3 substrate — see Layer-3 design session agenda). Schema:

```
gate_event {
  id: str (server-owned, immutable),
  goal_id: str (which Goal this event attests),
  event_type: str (defined per goal's gate_spec — see deferred schema below),
  event_date: date,
  evidence_urls: [str],
  cites: [{branch_version_id: str, run_id: str?, contribution_summary: str}],
  attested_by: user_id,
  attested_at: timestamp,
  verification_status: Literal['attested','verified','disputed','retracted'],
  verified_by: user_id?,
  verified_at: timestamp?,
  notes: str
}
```

MCP actions: `gate_events action=attest {goal_id, event_type, cites, evidence_urls, ...}`; `gate_events action=verify {event_id}` (requires different user than attester, verified_status transitions); `gate_events action=dispute {event_id, reason}`; `gate_events action=list {goal_id?, branch_version_id?}`. Attribution language is load-bearing — UI + API must say "this branch's output was cited in this gate event," never "this branch caused the outcome." Causality is for historians.

**Integration with Pillar 1:** `cites.branch_version_id` is content-addressed per `publish_version`. This is why `publish_version` ships first — long-horizon attribution survival depends on content-addressing. A run from today cited by a gate event two years from now still resolves to the exact branch state that was published.

**Integration with Pillar 2:** `Goal.gate_spec` (separate spec) declares allowed event_types + required evidence fields per Goal. Civic accountability Goal: event_types = [filed_charges, conviction, sentence, policy_change]. Fantasy writing Goal: event_types = [copies_sold, publisher_signed, award_nominated, award_won, translated, adapted]. Paper Goal: event_types = [peer_review_accepted, citation, trial_launched, industry_adoption, replication]. attest validates event_type + evidence shape against the Goal's gate_spec.

**Files:** new module `workflow/gate_events/` (schema, storage, record class), `workflow/universe_server.py` (four new actions), `workflow/goals.py` (gate_spec field — ships in companion spec), tests.

**Invariants:** gate_events are append-only; event_id is server-owned + immutable; verification requires different user than attester (prevents self-verify); disputed events surface in list queries with verification_status; retracted events remain visible with retraction record (audit trail); cites.branch_version_id must resolve to a published version (content-addressed validation); attestation attribution uses "cited by" / "contributed to" language, never causal.

**Tests:** attest creates record; verify by same user rejected; verify by different user succeeds; dispute transitions status; list by goal filters correctly; list by branch_version shows attribution; retracted event still listable with retraction marker; invalid cites.branch_version_id rejected at attest; event_type not in Goal's gate_spec rejected.

**Vetted:** 2026-04-23 by navigator. Promoted from strategic-synthesis Pillar 2. DEPENDS on Layer-3 substrate decision (design session output — storage backend decides how this record class persists; MVP may prototype on wiki-plumbed Layer-3 before Layer-3 substrate lands, but that's explicit-prototype not production-ship). DEPENDS on `publish_version` (cites must resolve to content-addressed versions). Does NOT depend on Gate-bonus payout surface (gate events are evidence records; bonuses are an orthogonal economic layer that consumes them).

---

## gate-based leaderboard — rank branches by attributed gate-event attribution

**Strategy rationale:** Strategic-synthesis Pillar 2: "gate-based leaderboard ranks branches by attributed gate events, not run count or LLM scores. This replaces/augments primitive #6 from `next-level-primitives-roadmap`." LLM-judge and upvote-style rankings are both game-able by agents at scale; real-world-gate-event attribution is not. This is the ranking primitive that makes the library's canonical branches rise organically.

**Scope:** Per-Goal leaderboard computed from gate_event.cites. New MCP action `goals action=leaderboard {goal_id, window?: 'all'|'30d'|'90d'|'1y', limit?: int}` returning ranked branches:

```
{
  goal_id: str,
  window: str,
  ranked: [{
    branch_version_id: str,
    branch_def_id: str,
    author: user_id,
    gate_event_count: int,
    gate_event_types: {event_type: count, ...},  # breakdown
    verified_event_count: int,  # verified-status only
    most_recent_event_date: date,
    score: float  # weighted per gate_spec
  }],
  total_events_in_window: int
}
```

Scoring starts dumb (count of verified gate events weighted per `Goal.gate_spec.event_weights`, if set; uniform weight otherwise) and evolves. Navigator-adjudicator tooling (deferred) can later re-weight. Leaderboards query gate-events by window, aggregate by `cites.branch_version_id`, sort by score desc.

**User-facing framing:** the leaderboard surfaces "here are the branches on this Goal whose output has been cited in the most real-world gate events." Not a popularity contest; not an LLM-grade. Users forking from top-ranked branches get a meaningful "this is working for people" signal.

**Files:** `workflow/goals.py` (leaderboard action + scoring helper), `workflow/gate_events/` (query-by-goal-and-window, aggregation), `workflow/universe_server.py` (action wiring), tests.

**Invariants:** leaderboard is deterministic given a gate_event set + window (reproducible); disputed/retracted events excluded from score; verified events weighted more than attested-only (factor configurable in gate_spec, default 2x); rank ties broken by most_recent_event_date desc then branch_version_id asc (stable); windows computed against `event_date` not `attested_at` (real-world date, not bureaucratic date).

**Tests:** leaderboard with 0 gate events returns empty ranked list; single gate event ranks single branch; two branches with same event count ordered by recent-date; disputed events excluded; verified events weighted 2x by default; custom gate_spec weights applied correctly; window filters correctly; limit caps output.

**Vetted:** 2026-04-23 by navigator. Promoted from strategic-synthesis Pillar 2. DEPENDS on `gate_event` spec (this is the consumer). DEPENDS on `publish_version` (ranks by branch_version_id). Ships naturally alongside `gate_event` spec — they form the Pillar-2 ranking surface together.

---

## Thundering-herd provider cooldown — chain-drain detection + backoff floor (BUG-029)

**One-line:** When all API providers enter cooldown simultaneously, the router silently funnels all traffic to `ollama-local` for up to 120s — the provider that triggered the revert-loop in the 2026-04-23 P0. Add a chain-drain detector that emits a structured warning and imposes a minimum inter-scene wait when every non-local provider is in cooldown, preventing the daemon from hammering the already-failing local provider at full scene-loop speed.

**Strategy rationale (3-layer lens):** System→Chatbot→User chain breaks at the generator layer. When all API providers are in cooldown, `ollama-local` receives all writer calls. In the 2026-04-23 incident, ollama-local was the empty-prose trigger — so the "safe fallback" was the broken component. The router has no awareness of this state. Lane 4 revert-loop canary (Task #9, shipped) detects the symptom (N consecutive REVERTs) but not the cause (all-providers-in-cooldown). This spec adds upstream cause-detection so the canary fires earlier and the daemon self-limits before disk pressure cascades.

**Diagnosis (from router.py + quota.py inspection):**
- `COOLDOWN_UNAVAILABLE = COOLDOWN_TIMEOUT = 120s` for all API providers.
- A burst failure at session start (container restart, all APIs rate-limited simultaneously, or network partition) puts all 4 API providers into 120s cooldown at roughly the same time.
- `ProviderRouter.call()` iterates the chain, skips all cooled-down providers, falls through to `ollama-local` — but does NOT log or signal that `ollama-local` is now carrying 100% of traffic.
- `get_status` does not expose per-provider cooldown state. Chatbot and operator have no visibility.
- No `AllProvidersExhaustedError` is raised (ollama-local is always in the chain and always available from quota's perspective), so the daemon has no signal to back off.

**Scope — two decoupled parts:**

*Part A — chain-drain detection + observability (small, ship first):*
Add `QuotaTracker.all_api_providers_in_cooldown(chain: list[str], local_providers: set[str]) -> bool` that returns True when every provider in `chain` except those in `local_providers` is in cooldown. `ProviderRouter.call()` checks this after chain traversal fails all non-local entries and emits a structured `logger.warning("CHAIN_DRAINED: all API providers in cooldown; routing exclusively to local for up to Xs")` event. Expose `per_provider_cooldown_remaining: dict[str, int]` on `get_status` so chatbot can narrate "claude-code: 87s, codex: 112s, gemini-free: 0s" to a user asking why nothing is happening.

*Part B — backoff floor when chain-drained (companion behavior):*
When `all_api_providers_in_cooldown` returns True AND `ollama-local` returned empty prose on the last N attempts (N=2 default, configurable), the router raises `AllProvidersExhaustedError` instead of returning the empty response. This gives the scene loop a clean error to back off from rather than silently committing an empty-prose REVERT that refills disk. The Lane 4 canary then catches the consecutive REVERTs before they cascade.

**Files:** `workflow/providers/quota.py` (add `all_api_providers_in_cooldown`), `workflow/providers/router.py` (call detection + emit warning + raise on local-empty-chain-drained), `workflow/universe_server.py` (expose `per_provider_cooldown_remaining` in `get_status`), `tests/test_quota.py` or `tests/test_provider_router.py` (new tests).

**Local providers set (hardcoded for now):** `{"ollama-local"}`. When more local providers exist, this becomes a provider attribute (`is_local: bool`).

**Invariants:** Part A is purely observational — no behavior change to routing for non-chain-drain cases. Part B only raises when BOTH conditions hold (all-api-in-cooldown AND local-returned-empty-last-N). Normal fallback-to-ollama behavior (API providers cooled down but ollama producing valid prose) is unaffected.

**Tests:** All-API-in-cooldown detection returns True when all non-local providers cooled; returns False when at least one API provider is available; `get_status` includes `per_provider_cooldown_remaining` dict; chain-drained + local-empty raises `AllProvidersExhaustedError`; chain-drained + local-producing returns response (Part B does not fire); normal single-provider-cooled path unchanged.

**Depends on:** None (self-contained quota + router change). Complementary to Lane 4 revert-loop canary (Task #9, shipped) — that canary detects the symptom; this spec adds upstream cause-signal.

**Vetted:** 2026-04-24 by navigator. Root-cause traced from 2026-04-23 P0 revert-loop audit + router.py + quota.py code inspection. Corroborates PLAN.md §Providers "error loudly when the remaining provider can't produce acceptable work."

---

## Three chatbot-leverage primitives — cost estimate, session boundary, get_status stability

Three primitives surfaced by the 2026-04-23 pre-dispatch sweep (`docs/audits/user-chat-intelligence/2026-04-23-pre-dispatch-sweep.md`) as the highest-leverage missing chatbot tools across four pending persona missions (Priya L1, Priya M2, Devin M27, Maya S2). All three are interface-1 chain-break mitigations — they make the chatbot's job easier by giving it structured tool facts instead of forcing it to heuristic-estimate or rely on prompt-level behavioral rules.

### estimate_run_cost — cost + time estimate before dispatch

**One-line:** `extensions action=estimate_run_cost branch_id=X` returns `{estimated_paid_market_credits: float, free_queue_eta_hours: float, node_count: int, basis: str, confidence: "low"|"medium"|"high"}` so the chatbot can give the user honest upfront cost/time framing before any dispatch.

**Why this matters:** Priya (scientific-computing persona) success bar includes "~$6 on paid-market" or "8 hours free-queue, honest ETA." Without a tool primitive the chatbot must heuristic-estimate from node count — a source of Priya-R12 (mid-sweep failure, partial compute loss) and general pitch-vs-product drift on any paid workflow. Cross-persona: any Tier-2 user dispatching a non-trivial branch faces the same gap. Per `project_paid_requests_model` the requester sets node+price; the estimate verb closes the loop so the chatbot can narrate the bid math before committing.

**Scope:** New `estimate_run_cost` action in the `extensions` MCP tool. Reads `BranchDefinition.nodes` (count + declared `llm_role` per node), cross-references current `FALLBACK_CHAINS` provider roster + approximate token estimates per node type, returns structured estimate. Confidence is "low" when no prior run data exists for this branch, "medium" when 1+ prior runs exist, "high" when 5+ runs exist (use median). Free-queue ETA derives from current queue depth (if dispatcher is available). No provider calls. No writes.

**Files:** `workflow/universe_server.py` (new extensions action handler), `workflow/branches.py` (read node declarations for cost basis), `workflow/dispatcher.py` (read queue depth for free-queue ETA, optional), tests.

**Invariants:** read-only; zero writes; works on branches that have never run (returns low-confidence estimate from node declarations alone); `basis` field narrates the formula so chatbot can quote it verbatim.

**Tests:** estimate on never-run branch returns low-confidence estimate with node_count; estimate on 5-run branch returns medium/high confidence; queue_depth unavailable path returns null free_queue_eta_hours with caveat; response is stable across multiple calls with no state changes.

---

### get_status session_boundary field — explicit "no prior session" assertion

**One-line:** Add a `session_boundary` field to `get_status` response that explicitly states whether the daemon has any record of the calling session or prior context, giving the chatbot a tool fact to ground "I don't have context from a prior session" instead of relying purely on prompt rule 11 (cross-session ask-don't-assert behavioral directive).

**Why this matters:** The 2026-04-23 sweep identifies "cross-session / shared-account fabrication" as a risk in 3/4 pending mission drafts. Rule 11 in the `control_station` prompt is a behavioral guardrail, but it's prompt-level — a model that wants to be helpful can drift under user pressure ("but you said yesterday…"). A tool fact that explicitly returns `"session_boundary": {"prior_session_context_available": false, "note": "No prior session record in this universe's activity log for the current account"}` gives the chatbot a ground-truth anchor to cite, not just a rule to follow. This is the `get_status` caveats pattern (`project_chain_break_taxonomy` — "tool response contains the caveats directly, chatbot can't dodge the truth") applied to session identity.

**Scope:** Add `session_boundary` block to the existing `get_status` response shape. Reads activity log for any entries associated with the current `UNIVERSE_SERVER_USER` identity in the last N days (configurable, default 30). If none: `prior_session_context_available: false`. If some: `prior_session_context_available: true, last_session_ts: "..."`. Adds `account_user: <UNIVERSE_SERVER_USER value>` so chatbot can narrate "account shows as <user>, prior sessions are [not] present."

**Files:** `workflow/universe_server.py` (extend `get_status` response block), tests. Minimal scope — `get_status` already reads the activity log; this adds one structured block to the output.

**Invariants:** read-only; zero writes; always present in get_status response (not gated on universe_id resolution); uses same activity.log reader that `get_status` already uses.

**Tests:** universe with no activity returns `prior_session_context_available: false`; universe with activity returns `true` + `last_session_ts`; `account_user` field present and matches env var; response schema stable (no existing fields changed).

---

### get_status schema stability guarantee

**One-line:** All existing `get_status` response fields must be considered a versioned contract. Any field removal or rename requires a deprecation notice in `get_status` output for one release before removal. New fields may be added freely.

**Why this matters:** The 2026-04-23 sweep explicitly flags: "Any regression there breaks three of four live-validation arcs simultaneously." Three pending personas (Priya L1, Devin M27, Priya M2) depend on `get_status` evidence fields being stable. The `served_llm_type`, `llm_endpoint_bound`, `policy_hash`, and `caveats` fields are load-bearing for trust claims. The new `per_provider_cooldown_remaining` (BUG-029) and `session_boundary` (above) additions must not silently displace existing fields.

**Scope:** Document the `get_status` response shape in the docstring as a versioned contract. Add a `schema_version` field (integer, starts at 1, increments on any breaking change). Add a test that reads `get_status` output and asserts the presence of every field named in the docstring. If any spec change to `get_status` lands, the test fails and forces the spec author to update the contract explicitly.

**Files:** `workflow/universe_server.py` (`get_status` docstring + `schema_version` addition), `tests/test_get_status_primitive.py` (schema assertion test). Read-only behavioral change.

**Tests:** `test_get_status_schema_contract` — calls `get_status`, asserts presence of all documented fields; any field removal causes test failure and forces explicit contract version bump.

**Vetted:** 2026-04-24 by navigator. Surfaced from 2026-04-23 pre-dispatch sweep cross-draft analysis. All three are interface-1 chain-break mitigations with no dependency blockers and small file footprints. `estimate_run_cost` and `session_boundary` are new additions; schema stability is a guard for both.

---

## continue_branch — workspace-memory continuity primitive

**One-line:** `extensions action=continue_branch {branch_id}` returns the branch's current working state (recent run summaries, last session activity, open notes, node progress) in one structured response — giving the chatbot a "pick-up-where-we-left-off" primitive instead of forcing it to reconstruct context from disconnected tool calls or, worse, hallucinate it.

**Problem statement (PRIYA-R7 + Maya LIVE-F1 chain-break diagnosis):** When a user returns to a branch in a second chat session, the chatbot has no memory of prior session activity. The chatbot must either (a) ask the user what was done before (friction — user expected continuity), (b) heuristic-reconstruct from disconnected `get_status` + `get_progress` + `describe_branch` calls (high-latency, error-prone), or (c) assert prior context that it doesn't have (hallucination — PRIYA-R7 root cause). `continue_branch` closes this interface-1 chain-break by giving the chatbot one verb that returns everything it needs to narrate "here's where we are" accurately.

**User experience framing (System→Chatbot→User):** User opens a second chat and says "let's keep going on my fantasy novel workflow." Chatbot calls `continue_branch branch_id=X`. Tool returns: last-run summary, open notes, most recent session timestamp, partial-progress state, any open concerns flagged by the daemon. Chatbot narrates "Your branch has 3 completed chapters and is currently in the Orient phase of chapter 4 — you left off yesterday at 14:23 UTC. The daemon flagged one note: [quote]. Want to resume?" That's the experience. Without this primitive the chatbot either asks (friction) or invents (hallucination).

**Scope:** New action `continue_branch` in the `extensions` MCP tool. Composes from already-existing read paths:
- `get_progress` output (completed / in-progress / pending node summary)
- Last `N` run records for this branch (from `query_runs`, default N=5, most recent first)
- Open notes from `notes.json` scoped to this branch (`note_type in ["user", "editor", "structural"]`, last 10)
- Current daemon phase if a run is active (`get_status` phase field)
- `session_boundary` block (from the session-boundary spec above) to explicitly anchor whether prior-session context is available
- Branch metadata: `branch_def_id`, `branch_name`, `description`, `last_modified_at`

Returns a single structured dict `ContinueBranchResponse` with all of the above, plus a `chatbot_summary: str` field — a one-paragraph plain-English "here's where you are" pre-composed for the chatbot to quote verbatim or adapt. The chatbot_summary is the composing layer that connects the structured data into a narrative the chatbot can use immediately without additional reasoning.

**`chatbot_summary` composition rules (pre-computed by the tool, not by the chatbot):**
- Lead with branch name + last-active timestamp
- State progress: "X of Y nodes completed; currently in [phase]"
- Cite open notes count and (if ≤2) quote them inline
- Close with "Want to [continue / run_branch / inspect a specific node]?" — but only if a clear next action is deterministic; otherwise omit the prompt to avoid false confidence

**Anti-hallucination invariant:** If `session_boundary.prior_session_context_available = false`, the tool includes `"prior_session_available": false` explicitly in the response AND reflects this in `chatbot_summary` ("No prior session history is recorded — this may be your first time running this branch, or context was not captured."). This gives the chatbot a tool fact to cite when it cannot provide continuity — eliminates the hallucination mode.

**Alias:** `patch_branch action=continue` resolves to the same handler for users who discover it via `patch_branch` rather than `extensions`. The canonical verb is `continue_branch` in `extensions`; the alias is for discoverability only.

**Files:** `workflow/universe_server.py` (new `_action_continue_branch()` handler wired into `_EXT_ACTIONS`; composes from `_action_get_progress()`, `query_runs()`, notes reader, `get_status()` phase field, `session_boundary` block), `workflow/branches.py` (read `last_modified_at` if not already surfaced), `tests/test_continue_branch.py` (new test file). No schema changes. No writes.

**Invariants:** read-only; zero writes; works on a branch that has never been run (returns "no run history" + low-confidence chatbot_summary); `session_boundary` block always present; `chatbot_summary` always present (even if "no data available — branch is new"); `prior_session_available: false` path tested explicitly; does not call any external providers; latency target: ≤200ms (pure SQLite reads + notes.json parse).

**Tests:**
- Branch with 3 completed runs returns correct progress + last-run summaries
- Branch with 0 runs returns "no run history" response with non-null chatbot_summary
- Open notes (≤2) quoted inline in chatbot_summary; (>2) count-only reference
- `prior_session_available: false` when session_boundary has no prior record — chatbot_summary includes anti-hallucination language
- `prior_session_available: true` when activity log has prior records — chatbot_summary includes last-session timestamp
- Active run (daemon mid-flight): `current_phase` field present and matches `get_status` phase
- Response is read-only: calling continue_branch twice returns identical output when no state changes occurred
- Alias `patch_branch action=continue` routes to same handler

**Depends on:** `get_status session_boundary field` spec (above) — uses the `session_boundary` block. `get_progress` (already implemented). `query_runs` (DONE per 2026-04-25 audit).

**Vetted:** 2026-04-25 by navigator. Signal: PRIYA-R7 (retention break in second-chat return), Maya LIVE-F1 (chatbot asked instead of assumed on brand return). Both failures root-cause to the same missing primitive: one verb that gives the chatbot accurate workspace-memory continuity without forcing reconstruction or tolerating hallucination. The `chatbot_summary` field is the key differentiator — it pre-composes the narrative the chatbot would have to reason toward, eliminating one hallucination-risk reasoning step.

---

## Evaluator protocol — workflow/evaluation/__init__.py

**One-line:** Define a shared `Evaluator` Protocol in `workflow/evaluation/__init__.py` so that every evaluation surface in the system (editorial judges, structural checks, gate verifiers, real-world outcome hooks, autoresearch metrics) implements a common structural interface — enabling the gate-bonus economy, autoresearch metric composition, and future moderation rubrics to share a single dispatch and result shape.

**Problem statement (unifying frame):** `workflow/evaluation/` currently has three siloed modules with incompatible shapes: `editorial.py` (`EditorialNotes` — no score, no `to_dict()`), `structural.py` (deterministic checks, optional spaCy/ASP deps), `process.py` (`ProcessEvaluation` with `aggregate_score` and `to_dict()` — closest to canonical). Gate bonuses depend on gate verifiers. Autoresearch depends on a runnable metric. Moderation rubrics are entirely future. All three are the same primitive at different points in the design — an `Evaluator` that takes context and returns a structured result. Without a shared interface, every new evaluation surface re-invents the shape and the dispatch layer cannot compose them. `project_evaluation_layers_unifying_frame` explicitly calls this out: "unify into first-class `Evaluator` type."

**Design (structural subtyping via `typing.Protocol`):** Use `typing.Protocol` with `runtime_checkable` — not ABC inheritance. Existing evaluator types do NOT need to inherit; they satisfy the protocol structurally if they implement `evaluate()` and `kind`. This keeps the change non-breaking and lets other in-flight work proceed in parallel without touching evaluation surfaces.

```python
# workflow/evaluation/__init__.py

from __future__ import annotations
from typing import Any, Literal, Protocol, runtime_checkable
from dataclasses import dataclass

EvalVerdict = Literal["pass", "fail", "warn", "skip"]

@dataclass
class EvalResult:
    score: float          # 0.0-1.0; deterministic checkers use 0.0 or 1.0
    verdict: EvalVerdict
    rationale: str        # human-readable; chatbot can quote verbatim
    evaluator_kind: str   # "editorial" | "structural" | "gate" | "metric" | "moderation" | custom
    details: dict[str, Any]  # evaluator-specific breakdown; always serializable

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "evaluator_kind": self.evaluator_kind,
            "details": self.details,
        }

@runtime_checkable
class Evaluator(Protocol):
    """Structural protocol -- implement evaluate() + kind to satisfy."""
    kind: str  # matches EvalResult.evaluator_kind

    def evaluate(self, context: dict[str, Any]) -> EvalResult:
        ...
```

**`context` dict contract:** Callers pass a context dict with keys appropriate to the evaluator kind. Each evaluator declares its required keys in its docstring. No global schema — each evaluator validates its own inputs and raises `ValueError` with a clear message if required keys are missing. This avoids a monolithic context schema that must anticipate all future evaluator types.

**`EvalResult.details` contract:** Evaluator-specific. `editorial` may include `{"concerns": [...]}`. `structural` may include `{"failed_checks": [...]}`. `gate` includes `{"gate_id": ..., "rung_key": ...}`. `metric` includes `{"metric_name": ..., "raw_value": ...}`. The `evaluator_kind` field is the discriminant. Callers that need to interpret `details` must know `evaluator_kind` first.

**Migration path for existing evaluators (non-breaking):** `editorial.py`, `structural.py`, `process.py` do NOT need to change to satisfy the Protocol. They satisfy structurally if they expose `kind: str` and `evaluate(context) -> EvalResult`. `process.py` is closest and may need minor field additions (`kind` attribute, return type coercion). `editorial.py` needs a `score` field or thin adapter. These adaptations are follow-up tasks dispatched separately — this spec ships the Protocol definition only.

**Gate bonus integration point:** The gate claim verifier (future `gate_event` spec) uses `Evaluator.evaluate()` to determine gate pass/fail. `EvalResult.verdict == "pass"` triggers bonus release; `"fail"` triggers refund to staker. This is the `project_evaluation_layers_unifying_frame` economic feedback loop made concrete. The `gate bonuses` spec (L198 above) depends on this Protocol being defined first.

**Autoresearch integration point:** Per `project_node_autoresearch_optimization`, per-node autoresearch runs a metric evaluator across 1000 candidate outputs overnight. The metric is an `Evaluator` — `evaluate({"node_output": ..., "node_def": ...})` returns `EvalResult` with `score` as the optimization target. The Protocol makes this composable: a research run can chain multiple `Evaluator` instances and aggregate scores.

**Files:** `workflow/evaluation/__init__.py` (Protocol + EvalResult + EvalVerdict — currently empty; this is the only file this spec touches), `tests/test_evaluator_protocol.py` (new test file).

**Invariants:** `Evaluator` is structural (Protocol), not nominal (ABC) — no existing class needs to inherit; `EvalResult.to_dict()` is always JSON-serializable (evaluators are responsible for `details` values being serializable); `runtime_checkable` allows `isinstance(obj, Evaluator)` checks at dispatch time without explicit registration; `EvalVerdict` is a `Literal` type — mypy catches invalid verdicts at type-check time; `score` range 0.0–1.0 by convention — evaluators with out-of-range values must normalize before returning.

**Tests:**
- `EvalResult` construction and `to_dict()` round-trip
- Structural Protocol satisfaction: a class with `kind: str` and `evaluate() -> EvalResult` passes `isinstance(obj, Evaluator)` without inheriting
- A class without `evaluate()` fails `isinstance` check
- A class without `kind` fails `isinstance` check
- `EvalVerdict` accepts `"pass"`, `"fail"`, `"warn"`, `"skip"`
- `to_dict()` output is JSON-serializable for a representative details payload
- Context dict with missing required key raises `ValueError` from a sample evaluator (integration pattern test)

**Depends on:** Nothing. `workflow/evaluation/__init__.py` is currently empty — clean dispatch, no blockers.

**Vetted:** 2026-04-25 by navigator. Unblocks: `gate bonuses` spec (needs gate verifier interface), autoresearch metric composition, future moderation rubrics. Existing evaluators (`editorial.py`, `structural.py`, `process.py`) do not need to change — Protocol is additive. Smallest possible footprint for maximum unblocking leverage: one file, one Protocol, one dataclass.

---

## teammate_message — inter-node messaging primitive for agent-teams-on-Workflow

**One-line:** Add a `teammate_message` MCP action that lets one branch node post a typed message to another node's inbox, enabling the agent-teams-on-Workflow pattern: chatbot as lead, branch nodes as teammates, inter-node coordination via message rather than shared state mutation.

**Problem statement (agent-teams-on-Workflow thesis):** Sub-branch invocation (Task #14, done) gives the chatbot the ability to spawn a child branch as a "teammate." But once spawned, there is no coordination channel — a node cannot signal another node, request approval, or broadcast state without writing to the shared branch state (which requires reducer coordination and pollutes the canonical output). In the Claude Code teams model, teammates communicate via `SendMessage`; in Workflow, the equivalent is a typed event posted to `run_events` with a well-known status. Without this primitive, agent-teams-on-Workflow degrades to fire-and-forget fan-out with no inter-node dialogue.

**Design (uses existing `run_events` table — no schema change):** The `run_events` table already has `run_id`, `event_type`, `payload_json`, `created_at`, `status` columns (confirmed at `workflow/daemon_server.py:~200`). The `teammate_message` primitive uses this table with `status="teammate_msg"` as the message-passing channel. No new table, no new schema migration. The sender writes a row; the recipient polls (or is notified via the existing event-sink mechanism).

**Scope — three MCP actions under a new `messaging` tool (or added to `extensions`):**

```
messaging action=send {
  from_run_id: str,       # sender's run_id
  to_node_id: str,        # recipient node_def_id (inbox address)
  message_type: str,      # "request" | "response" | "broadcast" | "plan_approval_request" | "shutdown_request"
  body: dict,             # arbitrary payload; JSON-serializable
  reply_to_message_id?: str  # for threading responses to a prior message
}
-> {message_id: str, delivered_at: str}

messaging action=receive {
  node_id: str,           # which node's inbox to read
  since?: str,            # ISO timestamp; defaults to beginning of run
  message_types?: [str],  # filter by type; default all
  limit?: int             # default 50
}
-> {messages: [{message_id, from_run_id, message_type, body, sent_at, reply_to_message_id}]}

messaging action=ack {
  message_id: str,        # mark message as processed
  node_id: str            # must match original to_node_id (auth check)
}
-> {acked_at: str}
```

**Storage:** Each `send` inserts a `run_events` row with `event_type="teammate_msg"`, `status="teammate_msg"`, `payload_json` containing `{from_run_id, to_node_id, message_type, body, reply_to_message_id, message_id}`. `receive` queries `run_events WHERE event_type="teammate_msg" AND payload_json->to_node_id = ?`. `ack` updates `status` to `"teammate_msg_acked"`. No new tables. Index on `(event_type, created_at)` already exists from prior run_events usage — the `payload_json->to_node_id` query path will be a JSON extract on SQLite; acceptable at current scale, index on `to_node_id` can be extracted column if benchmarks show need.

**Plan-approval flow (mirrors Claude Code teams protocol):** A node posts `message_type="plan_approval_request"` with `body={plan_summary, request_id}`. The lead node (or chatbot, via MCP) calls `messaging action=receive` to read it, then posts `message_type="plan_approval_response"` with `body={request_id, approve: bool, feedback?: str}`. The requesting node polls `receive` for a response to its `request_id`. This is the two-message handshake from the Claude Code teams plan-approval protocol, implemented purely via `run_events` rows — no new concurrency primitives needed.

**Shutdown flow:** `message_type="shutdown_request"` + `"shutdown_response"` mirror the Claude Code shutdown protocol. A lead node posts shutdown; child nodes respond with `approve: bool`. Lead polls for all responses before terminating child branches.

**Broadcast:** `to_node_id="*"` routes to all active nodes in the same branch run. `receive` with no `node_id` filter returns all messages posted to `"*"`. Useful for state-change announcements ("phase changed to orient") that all nodes should know about without targeted delivery.

**Universe isolation:** Messages are scoped to `run_id` (from_run_id determines the universe). Cross-universe messaging is structurally impossible — `run_events` rows are per-universe database. No additional isolation logic needed.

**Files:** `workflow/universe_server.py` (new `messaging` action dispatch block — or add to `_EXT_ACTIONS`), `workflow/daemon_server.py` (3 helper functions: `post_teammate_message()`, `read_teammate_messages()`, `ack_teammate_message()` — thin wrappers over `run_events` inserts/queries), `tests/test_teammate_message.py` (new test file).

**Invariants:** messages are immutable after send (no update verb); `ack` is idempotent (double-ack is a no-op); `receive` is non-destructive (does not consume messages — callers must `ack` explicitly); `from_run_id` is validated to be a real run in the universe (rejects phantom senders); `to_node_id="*"` broadcast is per-run (no cross-run broadcast); `body` must be JSON-serializable (error at send time, not at receive time); `message_id` is server-generated UUID (not caller-supplied, prevents collision/spoofing).

**Tests:**
- `send` inserts run_events row with correct event_type + status
- `receive` returns messages for correct `to_node_id`; does not return messages for other nodes
- `receive` with `since` filter excludes older messages
- `ack` marks message as acked; double-ack is no-op
- Plan-approval flow: request → response → requesting node reads response by `request_id`
- Broadcast (`to_node_id="*"`): received by any node calling receive with no node_id filter
- `from_run_id` pointing to non-existent run rejected
- Non-JSON-serializable `body` rejected at send time
- `message_id` is server-generated (caller-supplied id ignored)

**Depends on:** Sub-branch invocation (Task #14, done) — `teammate_message` is the coordination layer on top of sub-branch spawning. `run_events` table (already exists). No other blockers.

**Vetted:** 2026-04-25 by navigator. Closes the second gap in the agent-teams-on-Workflow analysis (`docs/notes/2026-04-20-agent-teams-on-workflow-research.md` — gap: "no inter-teammate messaging"). Sub-branch invocation (#14) is gap 1 (spawn); `teammate_message` is gap 2 (coordinate). Together they make chatbot-as-lead + branch-nodes-as-teammates a complete pattern. STATUS.md row pending verifier sweep clearing `daemon_server.py` + `universe_server.py`.

---

# Deferred specs — needs scoping before dev-dispatchable

The four rows below trace from the `project_daemon_souls_and_summoning` architectural landing (host directive 2026-04-22). Each is strategy-cleared under the SHIP-IT default (primitive expansions that fit `project_user_builds_we_enable`) but needs a scoping session before dev picks it up — they touch tray UX, identity model changes, cryptographic primitives, or new data-model tiers that navigator alone should not scope unilaterally. Flagging here for visibility so they're not dropped; promote to full dev-dispatchable spec when lead + host schedule scoping.

---

## [deferred] Daemon roster + soul.md authoring surface

**One-line:** Tray UX + backend for host-authored named daemons, each with a persistent soul.md identity file. Creating a soul = creating an inactive daemon. Summoning activates a specific named daemon.

**Foundational.** The three specs below all depend on this one being scoped first — daemon-as-persistent-named-object is the substrate. Touches `workflow_tray.py` (new daemon list + editor UX), `workflow/daemon/` likely new submodule (daemon registry, soul persistence, activation lifecycle), `workflow/storage/` (soul path resolution under `$WORKFLOW_DATA_DIR/daemons/<name>/soul.md`), MCP surface (new actions: `daemons action=list | create | edit_soul | summon | banish`).

**Open scoping questions:** tray interaction pattern for soul editor (external editor vs embedded); live-daemon soul-edit semantics (hot-reload vs require-banish-resummon); soul versioning schema; default-soul shape for users who never author one; migration path from today's generic `UNIVERSE_SERVER_HOST_USER` identity to named-daemons; relationship to `cloud-droplet` executor identity (is cloud-worker a single default-souled daemon, or multiple?).

**Needs scoping with:** host (UX + identity model), dev team (tray + storage), navigator (strategy + security of soul-spoof attacks).

---

## [deferred] Per-node soul_policy field on NodeDefinition

**One-line:** Add `soul_policy: Literal['allow_host_soul', 'append_node_header', 'insist_node_soul', 'hybrid']` + optional `node_soul: str` to NodeDefinition. Sibling to the (also-queued) `llm_policy` field — both are per-node authoring decisions that shape how the daemon behaves on that node.

**Depends on:** Daemon roster + soul.md authoring surface (the "host soul" referent must exist first).

**Open scoping questions:** hybrid-merge semantics (who wins on conflict); validation of node-provided souls (are they user-writable untrusted content that navigator must vet?); precedence at run time (how `_build_prompt_template_node` composes host soul + node header + node soul); does claim-time filter match on policy (daemon with incompatible policy can't claim).

**Shares authoring surface with:** per-node llm_policy (dev-dispatchable) — when that lands, coordinate UX so both fields are surfaced together in the build/patch-branch spec flow.

---

## [deferred] Branch-contribution ledger

**One-line:** Track `(daemon_id, node_id, step_count, earned_fraction)` across a multi-node branch run so branch-level bonuses can distribute proportionally across daemons that contributed (not just the finisher).

**Depends on:** Daemon roster + soul.md (daemon_id as first-class persistent identity).

**Overlaps with:** (1) existing `Sub-branch invocation primitive` spec (queued) — sub-branch invocation already needs to track which daemons executed which child-run steps; ledger plumbing is probably shared. (2) `Node checkpoints` spec (queued) — per-node earned-fraction already exists for node-level partial credit; branch ledger aggregates those upward. (3) `project_node_escrow_and_abandonment` — branch ledger is the escrow-tier above node-level. When both are implemented, there's one ledger with (daemon, node_id, earned_fraction) rows and a branch-level aggregator view.

**Open scoping questions:** step-count definition (langgraph step ≠ node if fan-out nodes have multiple inner steps); proportional distribution weighting (equal-per-step vs earned-fraction-weighted vs hybrid); privacy (branch ledger is claims-visibility vs contributor-visibility); partial-credit handling when a daemon contributes + abandons before checkpoint (probably zero per escrow rule, but interacts with aggregation).

---

## [deferred] Claim-time soul-fingerprint (anti-spoof)

**One-line:** Cryptographic primitive that lets a claiming daemon prove their soul is what they say it is, without the dispatcher having to trust claimer-asserted metadata.

**Depends on:** Daemon roster + soul.md (souls are stable addressable entities).

**Open scoping questions:** fingerprint scheme (sha256 of soul.md content vs keyed HMAC with a platform-side secret vs on-chain signature once crypto ledger lands); enforcement level (advisory display in claim UX vs hard match against a registry); key management for hosts (every host needs to sign their souls — keypair management burden); interaction with soul-editing (does a soul edit invalidate outstanding claims with the old fingerprint?); whether fingerprint is required OR opt-in per node (probably opt-in: `node_def.requires_verified_soul: bool`).

**Important but not urgent:** spoofing matters once daemon identity drives gate-bonus payouts. Today with no paid-market live, the threat model is thin. Spec when Paid-Market flag comes on AND gate-bonus primitive lands.

---

## [deferred] Flexible escrow splits — arbitrary distributions declared by the escrow-setter

**One-line:** Extends the paid-market post-a-request surface with setter-declared split primitives. The escrow-setter (per-request staker) can express **any distribution they want**: claimer-on-completion, cut-to-designer(s), gate-bonus pool, checkpoint partial-credit, real-world-outcome bonus, patronage, attribution-chain lineage cut, voluntary bounty-pool donation, platform-take. Platform provides templates for common patterns; setter can always customize.

**Critical role distinction** (`project_designer_royalties_and_bounties` §"Two distinct roles — designer vs escrow-setter"): the escrow-setter is NOT the designer. Staking money to run a node doesn't make you that node's creator; the designer identity is permanent and immutable on the artifact. Each request is a new escrow with its own distribution rules — the same node run by two different requesters can have two totally different distributions. Attribution chain stays the same; escrow varies per-request.

**Strategy rationale:** makes the escrow model express-the-setter's-intent rather than platform-mandate-one-pattern. OSS-commons strategy (0% to designers, 100% to claimer), patronage (high cut to a named designer), real-world-outcome stakes, quality-weighted splits — all are valid setter choices. Platform's job is to provide split primitives + a small template library; setters compose their own distribution.

**Depends on:** `project_node_escrow_and_abandonment` (base escrow model), `project_monetization_crypto_1pct` (platform-take floor), Attribution chain primitive (below — for lineage weights when setter chooses to cut the lineage), Minimum-royalty enforcement (below — platform-side floor that rejects non-compliant setter splits at escrow-setup).

**Open scoping questions:** template library shape (named templates like "standard" / "OSS-commons" / "patronage" / "real-world-outcome" / "quality-weighted"); template customization UX (fully editable vs template-lock-with-parameters); precision + rounding for percentage splits; behavior when setter's split violates a referenced node's minimum-royalty (rejected at escrow-setup — that's the minimum-royalty-enforcement spec's job); behavior when setter names a nonexistent recipient (reject with structured error); immutability of declared split once escrow is locked (probably immutable — changing mid-flight violates claimer expectations).

**Needs scoping with:** host (template library + what primitives setters can express), navigator (default-template shapes that reflect fair-distribution biases so setters have a good starting point), dev (escrow ledger columns + rounding invariants + split-validation at setup).

---

## [deferred] Minimum-royalty enforcement on NodeDefinition + BranchDefinition

**One-line:** Platform-provided knobs designers attach to their own work so escrow-setters can't post runs that free-ride past a declared floor. Adds `minimum_royalty: dict` field to NodeDefinition + BranchDefinition: `{default_percent: float, per_tier: {paid_market?: float, free_queue?: float, host_internal?: float}}`. Escrow-setup validates the setter's split against all referenced nodes'/branches' floors; rejects with structured error naming the violating node + floor if cut is insufficient.

**Strategy rationale** (`project_designer_royalties_and_bounties` §"What designers control about their own work"): most designers who want broad adoption pick 0% default and earn via voluntary escrow cuts + attribution-chain decay. Designers who want to monetize directly set a floor. Per-tier lets public work enforce a paid-tier royalty without blocking free-tier adoption — a designer can publish for free-queue use while requiring paid-market posts to pay them X%.

**Sibling designer knobs in the same memory** (either co-specced or called out as adjacent):
- **Private / access-gated node:** only specific users can post escrow for it. Escape hatch for proprietary work. Likely a separate `visibility` / `access_control` field (may overlap with existing branch-visibility from Phase 6.2.2).
- **Unpublished node:** exists only for the designer's own workspace. Simplest — a `published: bool` field; unpublished nodes cannot be escrow-posted by anyone but the designer.

**Depends on:** Flexible escrow splits (above — enforcement fires at escrow-setup validation); Attribution chain primitive (below — floor applies to designer named in the artifact's author field, so author identity must be durable).

**Open scoping questions:** floor-stacking when a branch references multiple nodes (sum of minimums vs independent per-node floors — probably independent, so setter must satisfy each); tier-naming (paid_market / free_queue / host_internal per memory — is there a catch-all `other` tier, or unnamed tier rejects); mid-life floor changes (designer raises floor after publishing — does that affect existing escrow setups with locked splits? Probably grandfathers existing escrows + applies to new setups only); interaction with remix — does a remix inherit the parent's floor, lower it, or reset it (memory is silent — probably remix is free to re-declare, but attribution-chain lineage cut still flows regardless, so setting 0% on remix doesn't escape lineage royalties); default shape for designers who never set a floor (default 0% = free commons matches memory §"Most designers who want broad adoption will pick 0% default").

**Needs scoping with:** host (tier naming + grandfather rules + remix-inheritance policy), navigator (interaction with fair-distribution + remix-lineage), dev (field schema + validation at escrow-setup + error-shape for floor violations).

---

## [deferred] Attribution chain primitive (remix provenance)

**One-line:** Lineage metadata on branches + nodes preserved through fork/remix/patch_branch. Carries parent-id + author + source-hash through N generations; queryable for royalty distribution.

**Strategy rationale** (`project_designer_royalties_and_bounties` §"Attribution chain"): multi-generation royalty flow (Carol earns → Carol 60%, Bob 25%, Alice 10% per suggested decay) requires durable lineage. Today fork/remix silently loses parent context. Chatbot auto-attributes on remix; deliberate declaration required to strip the chain. Makes "remix = collaboration" economically real per `project_convergent_design_commons`.

**Depends on:** `project_daemon_souls_and_summoning` (author_id is first-class — today's `author: "anonymous"` default on NodeDefinition isn't enough), Flexible escrow splits (above — needs author-id to route royalties).

**Open scoping questions:** decay function (hardcoded platform parameter vs per-split-template configurable — if hardcoded, what curve: geometric / linear / manual per-generation); lineage depth cap (unbounded vs max-10-generations to avoid ledger bloat); strip-chain semantics (chatbot-asserted "this is new inspired-by" vs human-ratified; audit trail for stripped claims); fork-diff threshold (does a 1-line edit count as "remix" earning lineage, or structural-novelty threshold navigator enforces); node-level vs branch-level lineage (probably both, independently tracked); handling when parent branch/node is deleted or privacy-flipped.

**Overlaps with:** the queued **Sub-branch invocation** spec — child-parent run linkage is execution-time provenance; this is design-time provenance. Should share lineage-schema where plausible.

**Needs scoping with:** host (decay parameters + strip-chain policy), navigator (fair-weighting bias), dev (lineage storage + query performance).

---

## [deferred] Real-world outcome evaluator hook (one escrow-template among many)

**One-line:** Extends the Evaluator primitive with "external outcome" variants that verify real-world signals (paper-published / MVP-shipped / contract-awarded / competition-won / revenue-threshold-hit). Used as **one common escrow-template** for setters who want to stake on external outcomes — not a canonical platform pattern.

**Framing correction** (`project_designer_royalties_and_bounties` §"Escrow design is open-ended"): real-world-outcome stakes are what a setter chooses to stake on, not what the platform mandates. A setter who cares only about a finished draft stakes on completion; a setter who cares about peer-reviewed publication stakes on that external signal. This spec ships the primitive that makes the latter expressible — the Evaluator variants + release mechanics. The distribution of the released bonus is whatever the setter declared in their escrow split (see Flexible escrow splits — could be "only finisher" or "split across all contributors weighted by navigator's fair-distribution calc"). The spec doesn't impose a distribution shape.

**Strategy rationale** (`project_real_world_effect_engine`): real-world outcomes are the product soul. Making external-signal-staking expressible is the direct economic incentive for setters who want to reward workflows that actually deliver. Setters who don't want to stake on externalities simply don't use this template. Platform supplies the template + ~5 common outcome-type evaluators; setters can author custom ones for niche cases.

**Depends on:** `project_evaluation_layers_unifying_frame` Evaluator primitive spec (the base Evaluator type this extends — itself not yet scoped), Attribution chain (above — needed when setter's distribution references lineage), Flexible escrow splits (above — the outcome-bonus slot is declared by setter, not platform).

**Open scoping questions:** which outcome signals are MVP-supported (peer-review status via DOI lookup? GitHub release published? self-attested + other-party-verified? on-chain contract awarded?); abuse vectors (how do we prevent self-attested "I published!" from draining escrow — probably requiring verifiable external signal OR multi-party-attested chatbot-judged claim); staker-defined vs platform-defined outcome types (probably both — platform ships ~5 common ones; stakers can author custom evaluators for niche cases); timeout + refund semantics (if outcome never arrives, does escrow refund to setter after N months?); tax / legal implications of platform-initiated outcome-bonus payouts (deferred per memory §"Deferred / open questions").

**Needs scoping with:** host (MVP outcome-type roster + staker-authored Evaluator policy), navigator (fair-distribution tree-weighting if setter chooses distributional shape), dev (external-signal plumbing — DOI APIs, GitHub-release webhooks, etc.).

---

## [deferred] Bug-bounty tracking + GitHub attribution

**One-line:** `file_bug` captures filer identity + optional `github_handle`. On ship (merged + deployed) + stability-period (7-30d) pass, reporter earns bounty from the 50%-of-1%-platform-take pool. Commit template auto-inserts `Co-Authored-By: <handle>` or `Reported-by: @handle` on bug-id-referenced commits. PR descriptions + release notes credit handles.

**Strategy rationale** (`project_designer_royalties_and_bounties` §"Bug + feature bounties" + §"GitHub attribution"): doubles user credit surface — bounty payout (money) + public GitHub attribution (reputation, portfolio, discoverability). Flywheel: platform volume → bounty pool → user-driven improvements → more volume. Reshaped bugs (like the maintainer-notes → describe_branch.related_wiki_pages reshape earlier this session) still credit the original reporter, possibly split with navigator if reshape was substantial.

**Depends on:** `project_monetization_crypto_1pct` live + platform-take accounting; `project_bug_reports_are_design_participation` framing (already landed); Fair-distribution calculator (below — for reshape splits).

**Open scoping questions:** stability-period duration (7d vs 30d vs platform-tuned-per-class); pool depletion semantics (defer payout until replenished, or pro-rate, or LIFO priority); low-quality-report rate-limiting + reputation to prevent bounty-farming (e.g. 5-report-per-week limit per filer, reputation decays on consistent rejections, navigator can ban abusive filers); bounty-amount schedule (trivial $5 / meaningful $100 / foundational $1000+ is illustrative per memory — needs platform-set table); handle collection UX (prompt-once-per-session in chatbot vs per-file_bug-call); handle validation (is `github_handle` verified against GitHub API, or accepted as-asserted with audit trail); payout rails (same crypto primitives as node-escrow or different?); tax / legal (deferred).

**Needs scoping with:** host (stability-period, amount schedule, handle validation policy, legal), navigator (reshape-split bias for the bounty-vs-navigator-cut decision), dev (file_bug schema extension + commit-template + post-merge stability monitor + pool accounting).

---

## [deferred] Fair-distribution calculator (navigator-adjudicator tooling)

**One-line:** Tool-assist for navigator's formal fair-distribution role. Given a payout event, compute a default split **within the rules the escrow-setter declared for that event**. Navigator reviews + overrides; dispute path escalates to host.

**Two distinct payout classes the calculator handles differently** (`project_designer_royalties_and_bounties` clarification):
- **Per-run payouts (setter-declared):** operate on whatever rules the escrow-setter declared for THIS run. Same node run by two different requesters can have totally different distributions. Calculator's job is to apply the setter's declared rules (e.g. "split across all contributors") using observed contribution data (step-counts, earned-fractions, attribution lineage). If setter said "only finisher," calculator just routes to the finisher — no fair-weighting needed.
- **Platform-set payouts (bug-bounty + navigator-reshape splits):** fully navigator-adjudicated from platform defaults. The 50%-of-1%-platform-take bounty pool routes by my fair-distribution heuristics — reporter vs navigator-reshape-cut vs (when applicable) dev-stipend. No escrow-setter involved; platform is the payer.

**Strategy rationale** (`project_designer_royalties_and_bounties` §"Navigator's fair-distribution role"): navigator is the only role that sees all contribution layers (dev/verifier/lead don't see full economics tree); natural place to adjudicate. Tooling makes the default computation transparent + reproducible; navigator's override is auditable; dispute path keeps the system human-appealable. Fairness bias baked into defaults: over-credit originators, under-credit shallow-relay remixes, reward structural novelty.

**Depends on:** Attribution chain primitive, Branch-contribution ledger (in daemon-souls deferred section), Flexible escrow splits, Real-world outcome evaluator hook, Bug-bounty tracking.

**Open scoping questions:** default-split formula (how much to each contribution layer at baseline — needs platform parameter table grounded in principles like "originator gets ≥25% regardless of remix depth"); override UX (CLI tool for navigator? MCP action? dispute-filing surface); transparency (is the computed split + navigator override public per-payout, or only visible to staker + payees); appeal SLA (how long do originators have to dispute; what does navigator produce in response — revised split + rationale, or refusal + rationale); repeat-payout pattern — for a frequently-used branch, does navigator adjudicate once per branch or once per event (probably once per branch with auto-apply, revisit on material contribution change); interaction with DAO weighted-votes governance (future) — does DAO override navigator's adjudication, or is it final.

**Needs scoping with:** host (fairness-bias parameters + dispute SLA + DAO-interaction), navigator (me — the tool needs to match my actual workflow and the fairness heuristics I'd apply manually), dev (the tooling itself — probably an MCP action + a persistent table for navigator-vetted splits).

**Importance:** this is the tool that makes navigator's new formal role executable at volume. Without it, each payout requires manual navigator computation, which doesn't scale past ~10/day. Priority should track paid-market + bounty-pool go-live.
