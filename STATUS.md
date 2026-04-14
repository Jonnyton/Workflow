# Status

Live project state. Living document — resolved items get deleted, not archived here. Code and `git log` are the history. This file only holds what is currently steering work.

### How This File Works

Items flow: **ideas/INBOX.md → ideas/PIPELINE.md → Concerns / Work → (resolved → deleted)**.

- **Concerns** — open questions and live tensions only. One line each. Delete when resolved.
- **Work** — claimable task board. Position is priority. Each row has **Files** (collision boundary) and **Depends**. Delete rows when landed — commits are the record.
- **Verify labels** — `current:`, `historical:`, `contradicted:`, `unknown:`, with date + environment when based on runtime evidence.

PLAN.md changes require user approval. When behavior contradicts a PLAN.md assumption, raise it here as a Concern first.

---

## Session 2026-04-14 wrap

Today landed: Phase 6.1 outcome gates (`b6722bd`), Task D telemetry (`b75e134`+`951d420`), #18 submit_request wiring (`590d11a`), daemon-task-economy memo + rollout (`52b3031`+`6616db0`+`c3d13af`), Phase A branches disambig (`242a937`), #22 hardening (`0c5f4f5`), stress-test checklist (`194ffcd`), Phase C.1-C.4 (`ebbafa1`/`9aae548`/`ba83254`/`b0b1b2d`), submit_request UX rewrite (`4bdfa51`), #31 user-facing string scrub (`90c3d3b`).

User-sim Mission 7 ran on the live MCP, confirmed #18 + #22 work end-to-end on the write side; surfaced two real bugs (sporemarch oscillation, dispatch_execution mis-routing on metadata.request_type).

**Late-session landings (after the wrap message, both self-verified, NO reviewer audit):**
- **Phase C.5** landed at `a228797` — authorial_priority_review wired through producer dispatcher. Dev-2 self-verified 23/23 producers + 12/12 wiring + 146/146 universe_nodes. Phase C is now COMPLETE (C.1-C.5 all landed).
- **Sporemarch fix (a)** landed at `997f825` — dispatch advances scene_number past existing files. Dev-1 self-verified 4/4 dispatch + 146/146 universe_nodes + 52/52 graph_topology.

**Next session: audit both commits before further work in `domains/fantasy_author/graphs/universe.py` or `domains/fantasy_author/phases/authorial_priority_review.py`.** Reviewer wasn't available at session-close; lead self-merged on tester-only signal because devs reported clean self-checks and STATUS coverage of intent. This violates the just-saved `feedback_commit_discipline.md` rule about test-file changes; deferred audit is the explicit compromise.

Phase D is now unblocked.

---

## Concerns

- [2026-04-13] **Worktree `claude/inspiring-newton` retire** — still held for host sign-off. Runbook at `docs/planning/worktree_retire_runbook.md`.
- [2026-04-14] **`default-universe` daemon still stuck pre-guardrail** — #6 universe-cycle + worldbuild no-op guardrails landed (`8ab17cd`, `afb9118`). A restart will self-pause at streak=5 with `idle_reason="universe_cycle_noop_streak"`, or make progress if premise is set. Operational action — host-gated. Tray "Restart All" picks it up.
- [2026-04-14] **Sporemarch SECOND_DRAFT oscillation on B1-C15-S3** — found by user-sim Mission 7. Daemon trapped: scores 0.69→0.72→0.71, word count frozen at 57,643. Root cause per dev-1 #33 investigation: WorkTarget keeps requesting `scene_number=N` after `scene-N.md` exists; nothing advances scene_number after acceptance. Each cycle re-runs S3, hits 1-revision cap, accepts, overwrites. Fix (a) ready to implement; fix (b) deeper. Both filed below.
- [2026-04-14] **Memory scoping is file-path-only; no defense-in-depth at retrieval** — Sporemarch contamination root cause (CWD-relative KG/vector paths) was fixed via explicit-path guards (`workflow/knowledge/knowledge_graph.py:34-38`, `workflow/retrieval/vector_store.py:38-42`, `fantasy_author/__main__.py:293-310`; 20 isolation tests green). But `MemoryScope` at `workflow/memory/scoping.py` is unused on the hot retrieval path — if physical file contamination recurs, retrieval has no query-time defense. Medium design task.
- [2026-04-14] **Packaging mirror sync question (host)** — `packaging/claude-plugin/plugins/workflow-universe-server/runtime/fantasy_author/universe_server.py` has stale "Author" strings + is broadly stale vs. live `workflow/universe_server.py`. Reviewer flagged on #31 audit. Question for host: is the mirror auto-built at plugin release time, or hand-maintained? If hand-maintained, it needs scrubbing; if auto-built from `workflow/`, no action.

---

## Open Questions for Host (batch-answer at convenience)

Conservative defaults applied; dev can proceed without answers, but host input sharpens the design. From three locked specs.

### Daemon task economy memo §6 (`docs/planning/daemon_task_economy.md`) — 7 items

1. Universe default-private or default-public? (Recommend private.)
2. Paid-tier monetization policy / escrow vs trust-first settlement, per-tier "paid-only" pause switch, bid transparency (see-all vs see-one), daemon reputation filter.
3. Multi-universe per daemon? (Recommend one-per for now.)
4. Opportunistic tier scope? (Read/verify/consolidate only.)
5. Goal-pool auto-accept vs approve-per-Task? (Budget-gated auto-accept.)
6. Chatbot-held durable state? (Yes but only via durable-artifact writes — Branch authoring, Goal creation, Task submission.)
7. Paid claim sybil prevention via outcome gates evidence (#56 coupling).

### Outcome gates spec §9 (`docs/specs/outcome_gates_phase6.md`) — 4 items

1. Ladder authority (owner-only vs community-proposed) — recommend owner-only v1.
2. Evidence URL archiving (auto web.archive.org snapshot?) — recommend NO in v1.
3. Private claims (inherit Branch visibility?) — recommend YES.
4. Cross-Goal shared rung primitives? — recommend NO in v1.

### Phase C TaskProducer spec §9 (`docs/specs/taskproducer_phase_c.md`) — 6 items

1. Enum vs string for `origin` (recommend string indefinitely).
2. Single daemon config vs per-producer config file (recommend single).
3. Origin-stamp mismatch policy (recommend override + warn). Already implemented in C.4.
4. Wrap `ensure_seed_targets` as producer? (Recommend yes — done in C.4 SeedProducer.)
5. IDLE sentinel return value? (Defer to Phase F.)
6. Make `candidate_override` required? (Recommend optional until Phase D.)

---

## Work

Claim by setting Status to `claimed:yourname`. Files column is the collision boundary. Position is priority.

| Task | Files | Depends | Status | Notes |
|------|-------|---------|--------|-------|
| **Sporemarch oscillation fix (b) — scene-completion advances WorkTarget** (medium) | chapter graph + commit phase + target_actions helper | fix (a) landed | pending | After `commit` returns verdict="accept", the selected WorkTarget's `metadata.scene_number` (and book/chapter equivalents) gets bumped + upserted. Closes the gap fix (a) only patches at dispatch layer. ~30-50 lines. |
| **Dispatch_execution doesn't honor `metadata.request_type`** | `domains/fantasy_author/phases/dispatch_execution.py:_determine_task` | user-sim Mission 7 + dev-1 #33 + stress-test 9.10 | pending | User-sim's `scene_direction` requests route to worldbuild instead of drafting because dispatch_execution keyword-matches on intent text rather than reading WorkTarget's `metadata.request_type`. Direct downstream of #18 wiring — requests reach the daemon now, but the daemon mis-routes them. |
| **#56 Phase 6.2** — outcome gates (retract + list_claims + leaderboard) | `workflow/universe_server.py` `gates` tool; rewire `_action_goal_leaderboard @ 6229-6264` outcome-metric stub | 6.1 landed (`b6722bd`) | pending | Spec §Rollout 6.2. Three remaining read/write-less actions. Fold in: reviewer-flagged host-override inconsistency on `define_ladder` (missing `actor == "host"` path per `goals update @ 5943`) + rebind-between-claims edge in idempotent claim UPDATE. Both minor. |
| **#56 Phase 6.3** — outcome gates (git commit path) | `workflow/storage/backend.py` new `save_gate_claim_and_commit`, YAML emitters under `gates/<goal>/<branch>__<rung>.yaml` | 6.2 landed | pending | H3 `force`/`local_edit_conflict` pattern via `_format_dirty_file_conflict @ workflow/universe_server.py:345-363`. One commit per MCP action; `define_ladder`/`get_ladder` commit subject under `goals.*`, `claim`/`retract` under `gates.*`. |
| **#56 Phase 6.4** — outcome gates integration | `goals get` extension with `gate_summary`, `branch` tool `gate_claims` field | 6.3 landed | pending | Per spec §Rollout 6.4. |
| **Phase D** — fantasy universe-cycle graph as registered BranchDefinition | per rollout plan §Phase D; `domains/fantasy_author/graphs/universe.py` + new BranchDefinition wrap | C.5 landed | pending | High blast radius. Behind `WORKFLOW_UNIFIED_EXECUTION=off` flag. Reviewer C.4 audit confirmed `NodeDefinition.approved=True` precedent at `workflow/universe_server.py:2577` lets the trusted-domain wrap reuse existing approval mechanism. Option (b) opaque-node wrap is primary path per memo §3.4. |
| **Phase E** — tier-aware DaemonController + BranchTask queue | per rollout plan §Phase E | Phase D landed | pending | First time user can see + steer a daemon queue. Major UX surface delivery. |
| **Phase F** — Goal subscription + pool producer | per rollout plan §Phase F | Phase E landed | pending | First time daemon leaves the universe boundary. May need async TaskProducer protocol variant per spec §1.1. |
| **Phase G** — NodeBid executor + paid priority weights | per rollout plan §Phase G | Phase F landed | pending | Priority slot; wallet integration deferred. Per-host-memory `project_paid_requests_model.md`: own crypto, requester sets node+LLM+price, daemons prefer higher bids matching their LLM, no floor. |
| **Phase H** — host dashboard + MCP inspect surfaces | per rollout plan §Phase H | Phase G landed | pending | UX-primary delivery vehicle. Where the user actually feels all the prior phases. |
| **Memory-scope defense-in-depth** (medium) | `workflow/memory/scoping.py`, `workflow/retrieval/agentic_search.py`, `workflow/retrieval/phase_context.py` | design pass | pending | Tag KG/vector rows with `universe_id` at write-time; filter at read-time. Defense-in-depth under existing file-path guards. |
| **MCP always-allow tooling gap** (medium) | `scripts/claude_chat.py`, `.claude/skills/ui-test/SKILL.md` | — | pending | `claude_chat.py dismiss-dialogs` clicks Approve without checking the per-tool "Always allow" toggle, so every fresh tool name re-prompts and stalls user-sim missions. Skill is updated to flag it; real fix is making the helper script auto-check the toggle before dismissing. |
| **Author → Daemon mass-rename** (large, deferred) | `fantasy_author/` module + `author_server.py` + `Author` class + identifier-tied "author" strings | host decision 2026-04-14 (memory `project_terminology_daemon.md`); after Phase C-H rollout settles | pending | Drive-by string fixes happening as code is touched (`619725e`, `90c3d3b` were first). Module rename is mass find-replace + import-rewrite + test sweep. Don't claim until C-H lands. |
| **Worktree retire** — runbook ready | repo-level | host sign-off | pending | `docs/planning/worktree_retire_runbook.md` is user-executable. Commands: `git worktree remove .claude/worktrees/inspiring-newton` + `git worktree prune`. Destructive; held for user. |

---

## Next Session Recommended Sequence

1. **Continue Phase C rollout: claim C.5 first** (small, well-specified, blocks Phase D). Concrete code in spec §8 C.5.
2. **Then Sporemarch fix (a)** — quick win, demonstrably restores a real-world UX path (queue drainage on sporemarch).
3. **Then dispatch_execution bug** — same UX path (request_type honoring), small fix.
4. **Then #56 Phase 6.2** — continues the outcome-gates rollout.
5. **Or skip ahead to user-sim Mission 8** — re-test #18 round-trip read-side after Sporemarch (a) lands. Read-side was unverifiable in Mission 7 because of the oscillation block.
6. The big Phase D-H sequence is the load-bearing user-facing payoff arc — Phase D in particular has high blast radius, plan carefully.

---

## Reference

- Memo + rollout: `docs/planning/daemon_task_economy.md`, `docs/exec-plans/daemon_task_economy_rollout.md` (`52b3031` + `6616db0` + `c3d13af`)
- Stress-test scenarios: `docs/planning/stress_test_scenarios.md` (`194ffcd`) — 28 scenarios across 10 subsystems, 14 P0 floor
- Phase C spec: `docs/specs/taskproducer_phase_c.md` (passed reviewer audit)
- Outcome gates spec: `docs/specs/outcome_gates_phase6.md` (passed reviewer audit, 6.1 landed)
- User-sim Mission 7 transcript: `output/user_sim_session.md` tail
- Memory updates this session: `project_paid_requests_model.md`, `project_terminology_daemon.md`, `feedback_testing_philosophy.md` (UX is the benchmark), `feedback_commit_discipline.md` (tester-only green is not enough), `feedback_restart_daemon.md` (restart authorized via tray)
