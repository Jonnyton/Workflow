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

- [2026-04-13] **Phase 7 in flight** — `workflow/storage/` (backend/layout/serializer) + 10 phase-7 test files uncommitted on main; `claude/inspiring-newton` worktree has ~65K-line restructure. Spec at `docs/specs/phase7_github_as_catalog.md`. Reconciliation pass needed before next dispatch.
- [2026-04-12] **`default-universe` daemon stuck in worldbuild no-op loop since 2026-04-09** — cycling worldbuild → "No changes" → worldbuild, phase "unknown", accept rate 0.0%, no premise set. Bounded reflection should detect this pattern and escalate; it doesn't. See task #6.
- [2026-04-10] **Sporemarch Book 1 premise departure + cross-universe contamination** — 30 scenes drifted off premise, Ashwater entities leaked in, evaluator scored 0.63–0.84 and caught none of it. Evaluator premise-grounding landed 2026-04-11 (reproduces failure); KG contamination and context-assembly root causes still unexplored.

---

## Work

Claim by setting Status to `claimed:yourname`. Files column is the collision boundary.

| Task | Files | Depends | Status | Notes |
|------|-------|---------|--------|-------|
| **Phase 7 reconciliation** — merge worktree restructure with uncommitted main storage layer, or decide which wins | `workflow/storage/`, `workflow/universe_server.py`, `workflow/runs.py`, `workflow/branches.py`, `workflow/graph_compiler.py` | - | pending | Worktree `claude/inspiring-newton` deletes `node_eval.py`, `node_sandbox.py`, `packets.py`, `preferences.py`, much of `universe_server.py` and `runs.py`. Main has additive storage layer. Pick a direction before further Phase 7 work. |
| **#4** docstring drift in universe_server.py | `workflow/universe_server.py` docstring only | - | pending | Says `python -m workflow universe-server` but no such subcommand exists. Only console script invokes. |
| **#5** trim tool docstrings for phone | `workflow/universe_server.py` descriptions | - | pending | `universe` (~66 lines, 13 optional params) and `wiki` (~58 lines, 14 params) have wall-of-text docstrings with duplicated action-table/Args narrative. Kill duplicate tables, bullets over ASCII. |
| **#15** chat-side cross-universe disambiguation | `workflow/universe_server.py` tool descriptions + response shapes | - | pending | Tool responses about a universe must lead with `Universe: <id>`. Descriptions must nudge: don't transfer info across universes. |
| **#41** claude_chat.py input-locked recovery | `scripts/claude_chat.py` | - | pending | Recovery ladder: click body → Escape → scroll bottom → reload chat URL → rescan INPUT_SELECTORS. Only dump if all fail. |
| **#54** Phase 5: Goal as first-class primitive | new `workflow/goals.py`, `workflow/universe_server.py` new `goals` tool | Phase 4 | pending (spec-first) | `goals` table, `branches.goal_id` column, actions propose/list/get/bind/leaderboard/common_nodes. Gated on Phase 4 judgment data before leaderboards earn their keep. STATUS.md header claims this landed — verify against code before starting. |
| **#56** Phase 6+: Outcome gates | new schema, `workflow/universe_server.py` new `gates` tool | #54 | pending (spec-first) | Per PLAN.md "Outcome gates". gates + gate_advances tables, self-report actions first, automation (DOI / court docket / sales / awards) later. |
| **#6** bounded reflection doesn't catch no-op daemon loops | `workflow/orient.py` or scheduler | - | pending | See Concerns — `default-universe` cycled worldbuild → "No changes" for 3 days. |
| **#33** verify and close rich-content capture | `scripts/claude_chat.py` | - | verify | Claude.ai artifact + mermaid capture mostly landed; confirm end-to-end and close. |
