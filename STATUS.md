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

- [2026-04-13] **Worktree `claude/inspiring-newton` retire** — still held for host sign-off. Runbook at `docs/planning/worktree_retire_runbook.md`.
- [2026-04-14] **`default-universe` daemon still stuck pre-guardrail** — #6 universe-cycle + worldbuild no-op guardrails now landed (`8ab17cd`, `afb9118`; 47/47 tests). A restart will self-pause at streak=5 with `idle_reason="universe_cycle_noop_streak"`, or make progress if premise is set. Operational action — host-gated.
- [2026-04-14] **Memory scoping is file-path-only; no defense-in-depth at retrieval** — Sporemarch contamination root cause (CWD-relative KG/vector paths) was fixed via explicit-path guards (`workflow/knowledge/knowledge_graph.py:34-38`, `workflow/retrieval/vector_store.py:38-42`, `fantasy_author/__main__.py:293-310`; 20 isolation tests green). But `MemoryScope` at `workflow/memory/scoping.py` is unused on the hot retrieval path — if physical file contamination recurs, retrieval has no query-time defense. Medium design task. Filed from dev's Sporemarch investigation.

---

## Work

Claim by setting Status to `claimed:yourname`. Files column is the collision boundary.

| Task | Files | Depends | Status | Notes |
|------|-------|---------|--------|-------|
| **Worktree retire** — runbook ready | repo-level | host sign-off | pending | `docs/planning/worktree_retire_runbook.md` is user-executable. Commands: `git worktree remove .claude/worktrees/inspiring-newton` + `git worktree prune`. Destructive; held for user. |
| **#56** Phase 6.2: outcome gates (retract + list_claims + leaderboard) | `workflow/universe_server.py` `gates` tool; rewire `_action_goal_leaderboard @ 6229-6264` outcome-metric stub | 6.1 landed (`b6722bd`) | pending | Spec §Rollout 6.2. Three remaining read/write-less actions. Batch: reviewer flagged host-override inconsistency on `define_ladder` (missing `actor == "host"` path per `goals update @ 5943`) + rebind-between-claims edge in idempotent claim UPDATE. Both minor, fold into 6.2 PR. |
| **#56** Phase 6.3: outcome gates (git commit path) | `workflow/storage/backend.py` new `save_gate_claim_and_commit`, YAML emitters under `gates/<goal>/<branch>__<rung>.yaml` | 6.2 landed | pending | H3 `force`/`local_edit_conflict` pattern via `_format_dirty_file_conflict @ workflow/universe_server.py:345-363`. One commit per MCP action; `define_ladder`/`get_ladder` commit subject under `goals.*` (file lands in `goals/`), `claim`/`retract` under `gates.*`. |
| **#56** Phase 6.4: outcome gates (integration) | `goals get` extension with `gate_summary`, `branch` tool `gate_claims` field | 6.3 landed | pending | Per spec §Rollout 6.4. |
| **Memory-scope defense-in-depth** (medium) | `workflow/memory/scoping.py`, `workflow/retrieval/agentic_search.py`, `workflow/retrieval/phase_context.py` | design pass | pending | Tag KG/vector rows with `universe_id` at write-time; filter by it at read-time. Adds second isolation layer under the existing file-path guards. |
| **#18 follow-ups** (small) | `workflow/work_targets.py`, `workflow/universe_server.py` | — | pending | (1) Fail-loud on corrupt `requests.json` in `_read_json` — currently silent fallback to `[]`. (2) Size cap on `submit_request.text` at write site (`workflow/universe_server.py:1305-1355`) — no limit today. (3) Centralize `REQUESTS_FILENAME` import at write site (`:1253, :1335`) — two string literals share a value. Small cluster, batch into one commit. |
| **Phase A** — kill `universe.branches.json` stub + `universe_fork` vs `branch_def` naming | `workflow/universe_server.py` (`_action_list_branches` + related), rename decisions per rollout plan | memo locks | pending | Per rollout plan `docs/exec-plans/daemon_task_economy_rollout.md` Phase A. `_action_list_branches` at `universe_server.py:1873` returns `[{"id":"main"}]` from a dead stub file nothing writes. Kill or rename to match actual semantics. No feature flag — pure rename/delete. |

**Deleted rows (reality audit 2026-04-13):** "Commit + push Phase 7.1" (landed `d8125b1`; Phase 7.2 G1-G4 + 7.3 H2 also landed). "Phase 7.3 H3 branch-cutover commit" (landed `39d92bb`, 2026-04-14). "Orphaned test_phase7.py cleanup" (landed `7bb2b24` — predates today's session; row was stale). "#5 trim tool docstrings" (landed `682c3a1` — stale row; `universe` @ 794-835 and `wiki` @ 6824-6859 already bullet-style, no duplicated tables). "#15 cross-universe disambiguation" (landed `c85efa1`; `_scope_universe_response` @ universe_server.py:378, wraps at 440-467, prompt at 628-639; dev-2 was claimed on already-shipped work, unclaimed). "#6 bounded reflection" (landed via 8ab17cd Task A + afb9118 Task B + orient rename Task C; guardrail lives at `domains/fantasy_author/phases/universe_cycle.py:27` not `workflow/orient.py`; 47/47 tests green; Task D deferred per memo §6). "Reviewer concern #1" (NodeTimeoutError.node_id attribute exists at `graph_compiler.py:58`). "Reviewer trivial cluster" — #2 caveat comment at `graph_compiler.py:65`, #3 typing at `backend.py:188`, #5 opaque-cursor doc at `runs.py:389` all shipped.
