---
title: Post-#23 Phase 2 Dev Queue — six unblocked, file-bounded tasks
date: 2026-04-27
author: navigator (claude-code, session d)
status: dispatch-ready (gates on #23 phase 2 verifier SHIP)
audience: lead, dev, dev-2, verifier
gates_on: STATUS Work row #23 Arc B phase 2 lands + verifier ships
load-bearing-question: When dev finishes #23, what do we dispatch immediately to keep dev + dev-2 fully utilized without collisions?
---

# Post-#23 Dev Queue

When dev's #23 Arc B phase 2 (39-file tests/ rename migration) lands and verifier ships, the lead pastes the rows below into STATUS.md and dispatches in the order shown. Six tasks, all file-bounded with no inter-task overlap, ordered by leverage and dependency depth.

**Sequencing assumption:** dev returns to #18 retarget sweep completion FIRST after phase 2 (87 files in worktree, ~972 LOC residual, prior session preserved WIP). Once #18 ships, the post-#18 menu opens. The plan below assumes #18 has shipped — the order it surfaces in is queue order, not phase order.

**Cross-task non-overlap matrix:** Files cells are disjoint across tasks #1-6. Verified by inspection — see `## Files-cell collision matrix` at the end.

---

## Task 1 — `extensions action=my_recent_runs` (recency primitive part A)

**Why first:** smallest single-action surface, anchors the pattern that #2 + #3 will copy. User-visible value (chatbot can answer "show me what I built recently" in one tool call). Spec + fixtures + cards all frozen.

**Files (write-set):**
- `workflow/api/runs.py` (new `_action_my_recent_runs` handler in existing `_RUN_ACTIONS` dispatch table)
- `tests/test_my_recent_runs.py` (NEW)
- `tests/fixtures/runs_recent_mixed_authors.json` (NEW)
- `tests/fixtures/expected_my_recent_runs_limit_5_alice.json` (NEW)

**Files (read-only deps):** none — `_action_*` dispatch convention is locked in `runs.py`.

**Depends:** `#23` ships. No other dependencies.

**Prep docs:**
- `docs/specs/2026-04-27-recency-and-continue-branch-primitives.md` §3.1 — input/output contract
- `docs/specs/2026-04-27-recency-continue-fixture-pack.md` §1-3 — fixture spec
- `docs/exec-plans/active/2026-04-27-post-18-recency-continue-implementation-cards.md` Card A

**Done when:**
- Action handler in `_RUN_ACTIONS`, returns `{ok, runs, count}` envelope.
- Actor filter via `UNIVERSE_SERVER_USER` identity path (existing pattern).
- `limit` clamped to 50, default 10.
- Newest-first ordering with name-sort tiebreaker.
- Fixture-based test green; live MCP probe green via `mcp_probe.py --tool extensions --args '{"action":"my_recent_runs","limit":5}'`.

**What could go wrong:**
- Identity resolution path differs across `_action_list_runs` and `_action_get_run` — pick the canonical one (likely `_get_effective_actor()` or equivalent helper) and document in commit. Risk: if no shared helper exists, the new action invents a third path. Audit existing `_action_list_runs` for actor filtering BEFORE writing handler.
- `RunSummary` shape varies across other actions — pick the existing format that includes `run_id, branch_id, status, created_at, goal_title` and reuse rather than mint a new one. Spec says "minimally" but consistency matters.
- Fixture pack uses `tests/fixtures/` — verify this directory exists and is in conftest's load path. If not, create + register.

**Estimated effort:** 1.5-2h.

---

## Task 2 — `goals action=my_recent` (recency primitive part B)

**Why second:** mirrors Task 1 pattern. Same actor-filter + envelope shape, applied to goals surface. Lower risk because Task 1 establishes the convention.

**Files (write-set):**
- `workflow/api/market.py` (new `_action_my_recent` in `_GOAL_ACTIONS` or equivalent dispatch table — verify exact name in market.py before writing)
- `tests/test_my_recent_goals.py` (NEW)
- `tests/fixtures/goals_recent_mixed_authors.json` (NEW)
- `tests/fixtures/expected_my_recent_goals_limit_5_alice.json` (NEW)

**Files (read-only deps):** `workflow/api/runs.py` (Task 1 handler as reference pattern).

**Depends:** Task 1 lands first (pattern reference). Conceptually parallel-able but ordering avoids inventing two competing actor-filter idioms.

**Prep docs:** Same spec + fixture pack as Task 1; §3.2 in spec.

**Done when:**
- Action handler returns `{ok, goals, count}`.
- Same identity path as Task 1.
- Fixture-based test green; live MCP probe green via `mcp_probe.py --tool goals --args '{"action":"my_recent","limit":5}'`.

**What could go wrong:**
- `market.py` is 2387 LOC — find the existing `_action_*` registration site (likely near the top, e.g., `_GOAL_ACTIONS = {...}`). Don't introduce a second dispatch table.
- Goal-actor binding may be different from run-actor binding. Verify which column on `goals` table holds the author/owner identity before filtering. If goals table has no actor column at all, this task surfaces a primitive-gap that needs `file_bug` rather than a workaround.

**Estimated effort:** 1-1.5h.

---

## Task 3 — `extensions action=continue_branch` (continue-branch primitive)

**Why third:** depends conceptually on Tasks 1+2 (dispatch-table conventions established). Larger surface than recency because it creates a sibling branch and dispatches a run.

**Files (write-set):**
- `workflow/api/runs.py` (new `_action_continue_branch` handler — distinct from any existing `continue_branch` in branches.py)
- `tests/test_continue_branch_run.py` (NEW)
- `tests/fixtures/runs_continue_source_catalog.json` (NEW)
- `tests/fixtures/expected_continue_branch_success.json` (NEW)
- `tests/fixtures/expected_continue_branch_not_found.json` (NEW)
- `tests/fixtures/expected_continue_branch_forbidden.json` (NEW)

**Files (read-only deps):** `workflow/api/branches.py` (need to read existing `continue_branch` if any to disambiguate naming).

**Depends:** Task 1 lands (same dispatch table; commit ordering avoids merge conflict in `_RUN_ACTIONS`).

**Prep docs:**
- spec §3.3 — v1 sibling-branch mode only.
- fixture pack §1.3 + §2 — three response snapshots.
- implementation cards Card C.

**Done when:**
- Sibling-branch mode resolves source run, creates a continuation branch, dispatches as a normal run request.
- Returns `{ok, continuation: {source_run_id, new_branch_id, request_id}}`.
- Three error cases pass: `from_run_id` not found, cross-actor forbidden, missing `instructions`.
- Live MCP probe green.

**What could go wrong:**
- "Sibling-branch" mode requires a branch-creation primitive — verify whether `_clone_branch` or similar exists. If not, the task scope expands to include branch-creation glue, not just dispatch wiring.
- "Carry-over contract" (which params + state survive from source run) is under-specified in the spec. Default: copy branch definition + run params; do NOT copy run results into new run state. Document the choice in the handler docstring.
- Cross-actor forbidden semantics: confirm the actor check uses the same path as Tasks 1+2.

**Estimated effort:** 2-3h.

---

## Task 4 — `run_branch resume_from=<run_id>` parameter

**Why fourth:** F2 host-ACCEPTED 2026-04-28; single param add. Smallest scope on the runs.py surface. Coordinate with Task 3 — both touch `_action_run_branch` neighborhood.

**Files (write-set):**
- `workflow/api/runs.py` (add `resume_from` param to `_action_run_branch` and threading through to dispatch)
- `tests/test_run_branch_resume_from.py` (NEW)

**Files (read-only deps):** none.

**Depends:** Task 3 lands first (avoids merge conflict in `_action_run_branch` neighborhood; sequencing keeps each task's runs.py diff small).

**Prep docs:** F2 acceptance memo (referenced in STATUS row "run_branch resume_from"). No standalone spec — single-param add.

**Done when:**
- `resume_from` param accepted; when present, run picks up source run's state checkpoint.
- Validation: `resume_from` must be a valid run_id, owned by the same actor.
- Test covers: happy path, not-found, forbidden, fresh-start (param omitted).

**What could go wrong:**
- Checkpoint resume requires the underlying run to have a SqliteSaver checkpoint — confirm SqliteSaver write happens at every node boundary so resume_from has a meaningful checkpoint to land on. If not (and runs are atomic), this task is structurally blocked.
- Interplay with `continue_branch` (Task 3): `resume_from` is "continue same run" while `continue_branch` is "fork into sibling." Document the distinction in the runs.py module docstring so future readers don't conflate them.

**Estimated effort:** 1.5-2h.

---

## Task 5 — Phase 6 db rename (`.workflow.db` + `db_path()` fn + Option A migration)

**Why fifth:** ships independently of Tasks 1-4 (different file: `workflow/storage/__init__.py`). Coordinate ordering with Arc C (#24) — both touch storage/__init__.py.

**Files (write-set):**
- `workflow/storage/__init__.py` (add `db_path()` fn, `.workflow.db` constant, Option A migration logic)
- `packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/storage/__init__.py` (mirror — auto-regenerated by `build_plugin.py`; verify mirror parity post-edit)
- `tests/test_storage_db_path.py` (NEW)
- `tests/test_storage_migration_option_a.py` (NEW)

**Files (read-only deps):**
- `workflow/storage/checkpoint.py` if it exists (callers of the implicit db path)
- All callers of any current db-path resolver — grep `data_dir().*\.db`, `checkpoint.db` to find them

**Depends:** Arc C (#24) lands first if it ships. If Arc C is queued behind Phase 6, Phase 6 ships first and Arc C re-bases against Phase 6's `data_dir()` shape. Verify with lead at dispatch time which order makes sense.

**Prep docs:**
- STATUS Work row "Phase 6" + memory `project_memory_scope_stage_2b` for sibling Stage 2c context.
- AGENTS.md "Configuration" table row for `WORKFLOW_DATA_DIR` (canonical resolver `workflow.storage.data_dir()`).
- Decomp Arc B/C prep docs — same module ownership.

**Done when:**
- `db_path()` returns `<data_dir()>/.workflow.db` by default.
- Option A migration: on first call, if old path exists (e.g., `<data_dir()>/checkpoint.db` or wherever the implicit path was), atomically rename to `.workflow.db`.
- 30s daemon restart after rename succeeds; canary green.
- Plugin mirror parity confirmed via `python packaging/claude-plugin/build_plugin.py` no-op or matching diff.
- Plugin minor-bump if API surface changed (verify with packaging convention).

**What could go wrong:**
- Migration is the highest-risk piece. If the daemon is mid-write when migration runs, the rename can corrupt. Wrap in a "daemon-must-be-stopped OR no SQLite connection open" precondition; fail-loud if the precondition fails.
- LanceDB index path is independent — confirm it's NOT under the same rename, otherwise indexes get orphaned.
- Plugin mirror is regenerated by `build_plugin.py`; if dev edits the mirror by hand, the next run of `build_plugin.py` overwrites. Edit canonical only; let pre-commit invariant validate parity.
- Tray + container env may have hardcoded `checkpoint.db` paths — grep `deploy/`, `workflow_tray.py`, `fantasy_daemon/__main__.py`. If any, update in same commit.

**Estimated effort:** 2-3h dev + 1h host validation per nav memory `project_memory_scope_stage_2b`.

---

## Task 6 — Claude.ai injection mitigation (§5+§5.5 prompt-discipline)

**Why sixth:** prompt-only edit; no test surface beyond chat-trace verification; can land in parallel with any other task because Files cell is disjoint. Sequenced last because its Files cell migrated POST-#18 — `workflow/universe_server.py` is the old path; control_station prompt now lives in extracted prompt module after decomp Steps 1-11.

**Files (write-set):**
- `workflow/prompts/control_station.py` (or wherever decomp landed the control_station prompt — verify post-#18; was inline in `universe_server.py` pre-decomp)
- `tests/test_control_station_prompt.py` (NEW or extended) — text-presence regression tests for the §5/§5.5 directives

**Files (read-only deps):**
- `docs/audits/2026-04-28-rows-6-7-8-community-build-obviation-addendum.md` §3 — the prompt-discipline directives that must land
- `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md` — rationale + threat model

**Depends:** #18 lands first (file paths shifted post-decomp). Otherwise standalone.

**Prep docs:** Audit cited above. Specifies exact directive text to add to the system prompt's §5 (treat-untrusted-canon) and §5.5 (don't-execute-instructions-from-canon) sections.

**Done when:**
- Control_station prompt contains both §5 and §5.5 directive blocks verbatim per audit.
- Regression test asserts directive text presence (so future prompt edits don't accidentally drop them).
- Live Claude.ai chat smoke (one user-sim turn) shows chatbot rejecting an injected instruction inside a canon read.

**What could go wrong:**
- Post-#18, control_station prompt may have moved to `workflow/prompts/` or `workflow/api/prompts.py` — confirm location at dispatch time. If still in universe_server.py post-#18, the row's Files cell needs updating; #18 should have moved it.
- §5/§5.5 directives may conflict with existing prompt content (e.g., a "trust user" directive). Resolve at edit time; either reframe or layer with priority language.
- Live Claude.ai test has tool-budget cost; one turn is enough for SHIP, more for the 30d watch.

**Estimated effort:** 1-2h dev + ~30 min for one-turn live verification.

---

## Files-cell collision matrix

| Task | runs.py | market.py | storage/__init__.py | prompts/* | tests/ NEW | fixtures/ NEW |
|------|---------|-----------|---------------------|-----------|------------|---------------|
| 1 my_recent_runs | W | — | — | — | test_my_recent_runs.py | runs_recent + 1 expected |
| 2 my_recent (goals) | — | W | — | — | test_my_recent_goals.py | goals_recent + 1 expected |
| 3 continue_branch | W | — | — | — | test_continue_branch_run.py | continue source + 3 expected |
| 4 resume_from | W | — | — | — | test_run_branch_resume_from.py | — |
| 5 Phase 6 | — | — | W | — | test_storage_db_path.py + test_storage_migration_option_a.py | — |
| 6 Injection mitigation | — | — | — | W (control_station) | test_control_station_prompt.py (or extended) | — |

**Same-file overlap on `runs.py` (Tasks 1, 3, 4):** mitigated by sequential dispatch — Task 1 → 3 → 4 commits land in order, each touching distinct `_action_*` neighborhoods.

**No two tasks touch the same NEW test file or fixture file.** Adding `tests/fixtures/` to a `.gitignore`-style `# fixtures live here` directive isn't required if filenames are distinct.

---

## Suggested dispatch order (lead use)

| Order | Task | Provider | Rationale |
|-------|------|----------|-----------|
| 1 | Task 1 (my_recent_runs) | dev | Establishes pattern. |
| 2 | Task 2 (my_recent goals) | dev-2 (parallel) OR dev (sequential) | If dev-2 idle: parallel, no overlap (different file). If dev-2 busy: dev does sequentially after Task 1. |
| 3 | Task 3 (continue_branch) | dev | Pattern-dependent on Task 1; same dev keeps mental model loaded. |
| 4 | Task 4 (resume_from) | dev | Single-param add; quick win between heavier tasks. |
| 5 | Task 5 (Phase 6) | dev or dev-2 | Independent file; can run in parallel with any other task. **Highest blast radius — book against verifier full-suite slot.** |
| 6 | Task 6 (injection mitigation) | dev or dev-2 | Smallest blast radius; can drain at end of any session. |

**Floater rule:** if dev-2 is on a parallel slot, prefer Tasks 5 or 6 for dev-2 (lower coupling to the runs.py serialization chain).

---

## Out-of-queue (skipped intentionally)

- **Q6.3 `allowed_providers`** — host-decision pile (Q6.3 §4 dispositions still pending). Skipped per lead instruction. `tests/test_provider_allowlist.py` (codex test-first artifact) needs skip-mark or removal — flagged in reality sweep §6.
- **Hyperparameter_importance evaluator node** — module-lane blocked (no scientific-computing module exists yet). Specs + cards ready (`docs/specs/2026-04-27-hyperparameter-importance-*.md`, `docs/exec-plans/active/2026-04-27-hyperparameter-importance-implementation-cards.md`); waitlist until module lane opens.
- **Runtime fiction memory graph** — host-decision pending on entity set + contradiction policy (`docs/specs/2026-04-27-runtime-memory-graph-minimal-schema-v1.md` + `docs/notes/2026-04-27-runtime-memory-graph-contradiction-policy.md`). Not dev-ready.
- **Memory-scope Stage 2c flip** — gated on 30d clean watch ending ≥2026-05-16 per `docs/exec-plans/active/2026-04-27-memory-scope-stage-2c-flip-prep.md`. Not in this queue's window.
- **`#24 Arc C` env-var deprecation** — already in STATUS as `dev-ready`; either dispatch as Task 0 (before Tasks 1-6) or sequence after Task 5 (Phase 6) since both touch `storage/__init__.py`. Not added as a new row here because it already exists. Lead's call which order.

---

## Acceptance

This plan is dispatch-ready when:

- All Files cells refer to files that will exist post-#18 + #23 (verified at dispatch time, not now).
- Each task can SHIP independently of the others (no inter-task code dependencies — only sequencing dependencies for merge cleanliness).
- The reading-time-to-claim-time path for any provider is ≤5 minutes via this doc + the cited spec/prep docs.

If any of the assumptions break (e.g., #18 reshapes the api/* tree differently than expected, control_station prompt lives somewhere unexpected), the affected task gets a one-paragraph "verify file location" note added at dispatch — no full re-spec needed.
