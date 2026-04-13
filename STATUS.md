# Status

Live project state. Living document — resolved items get deleted, not archived here. Code and `git log` are the history. This file only holds what is currently steering work.

### How This File Works

Items flow: **ideas/INBOX.md → ideas/PIPELINE.md → Concerns / Work → (resolved → deleted)**.

- **Concerns** — open questions and live tensions only. One line each. Delete when resolved.
- **Work** — claimable task board. Position is priority. Each row has **Files** (collision boundary) and **Depends**. Delete rows when landed — commits are the record.
- **Verify labels** — `current:`, `historical:`, `contradicted:`, `unknown:`, with date + environment when based on runtime evidence.

PLAN.md changes require user approval. When behavior contradicts a PLAN.md assumption, raise it here as a Concern first.

---

## Concerns

- [2026-04-13] **Phase 7 direction settled** — planner recommends keep-all-from-main, retire worktree `claude/inspiring-newton` (it's pre-c85efa1 and reverts Community Branches Phases 2-5). `git worktree remove` held for host sign-off. Phase 7.1 storage layer is ready to commit; reviewer audit identified 5 follow-ups, no hard blockers. Phase 7.2 (git_bridge.py) is next roadmap step.
- [2026-04-12] **`default-universe` daemon stuck in worldbuild no-op loop since 2026-04-09** — cycling worldbuild → "No changes" → worldbuild, phase "unknown", accept rate 0.0%, no premise set. Planner scoping detection design at `docs/planning/no_op_reflection_investigation.md`.
- [2026-04-10] **Sporemarch Book 1 premise departure + cross-universe contamination** — 30 scenes drifted off premise, Ashwater entities leaked in, evaluator scored 0.63–0.84 and caught none of it. Evaluator premise-grounding landed 2026-04-11 (reproduces failure); KG contamination and context-assembly root causes still unexplored.

---

## Work

Claim by setting Status to `claimed:yourname`. Files column is the collision boundary.

| Task | Files | Depends | Status | Notes |
|------|-------|---------|--------|-------|
| **Commit + push Phase 7.1** — land uncommitted main diff as a single Phase 7.1 commit | `workflow/storage/`, `workflow/universe_server.py`, `workflow/runs.py`, `workflow/branches.py`, `workflow/graph_compiler.py`, 10 new test files, 7 research docs | reviewer follow-ups (optional pre-merge) | pending | Keep-all-from-main per planner. Reviewer audit green (5 follow-up concerns captured below). Host sign-off on Phase 7.1 gate since spec introduces on-disk YAML layout (additive; SqliteOnly stays default per spec §Dual-write). |
| **#15** cross-universe disambiguation | `workflow/universe_server.py` | - | claimed:dev-2 | Plan at `output/dev-2_phase15_plan.md`. Universe-scoped responses must lead with `Universe: <id>`. Tool descriptions nudge against cross-universe info transfer. |
| **Reviewer concern #1** — NodeTimeoutError node_id as attribute | `workflow/graph_compiler.py`, `workflow/runs.py` | - | claimed:dev | Fragile regex parses node_id from error string. Store as attribute instead. |
| **Reviewer concerns #2–#5 (follow-ups)** | `workflow/graph_compiler.py`, `workflow/runs.py`, `workflow/storage/backend.py` | - | pending | (2) `_TIMEOUT_EXECUTOR` queued calls can exceed nominal timeout — document or redesign. (3) `stage_hook: Any` → `Callable[[Path], None] \| None`. (4) Verify `set_goal`/`unset_goal` impl exists (docstring mentions it; reviewer didn't spot impl in diff). (5) step_index no longer equals node ordinal — clients assuming ordering handle max. |
| **#5** trim tool docstrings for phone | `workflow/universe_server.py` descriptions | #15 | pending | `universe` (~66 lines, 13 params) and `wiki` (~58 lines, 14 params) have wall-of-text docstrings with duplicated action-table/Args narrative. Kill duplicate tables, bullets over ASCII. |
| **#6** bounded reflection doesn't catch no-op daemon loops | `workflow/orient.py` or scheduler | planner investigation | pending | Planner scoping at `docs/planning/no_op_reflection_investigation.md`. |
| **Orphaned test_phase7.py cleanup** | `tests/test_phase7.py` | - | pending | 3 tests call `DaemonController._bootstrap_universe_runtime_files` / `._bootstrap_retrieval_indices` — methods that don't exist in prod or git history. Delete or re-scope. Not urgent. |
| **Worktree retire** — `git worktree remove .claude/worktrees/inspiring-newton` + delete branch | repo-level | host sign-off | pending | Destructive git op; hold for user. After Phase 7.1 commits. |
| **#54** Phase 5: Goal as first-class primitive | new `workflow/goals.py`, `workflow/universe_server.py` new `goals` tool | Phase 4 | pending (spec-first) | `goals` table, `branches.goal_id`, actions propose/list/get/bind/leaderboard/common_nodes. |
| **#56** Phase 6+: Outcome gates | new schema, `workflow/universe_server.py` new `gates` tool | #54 | pending (spec-first) | Per PLAN.md "Outcome gates". Self-report first, automation later. |
