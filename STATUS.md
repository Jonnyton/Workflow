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

**Audit cleared 2026-04-14 (session 2):** Reviewer passed both commits. `a228797` (C.5): clean, no regressions, test-isolation teardown correct. `997f825` (Sporemarch a): primary fix correct, but guard condition `scene_number <= max_existing_scene` is stricter than "already exists on disk" — edge case flagged below. Audit evidence: 27/27 on `pytest tests/test_scene_dispatch_advance.py tests/test_task_producers.py`.

**Session 3 landings (2026-04-14, full reviewer + tester pass):**
- **dispatch_execution request_type routing fix** at `68400bc` — `_determine_task` honors `metadata.request_type` before keyword-matching. 12/12 new tests.
- **Sporemarch oscillation fix (b)** at `0db181c` — `advance_work_target_on_accept` hooked in chapter.py:run_scene. Closes fix-a gap-scenario edge case at source. 9/9 new tests. Reviewer PASS-WITH-NOTES — multi-scene overshoot + run_scene drafts at scenes_completed+1 flagged for live verification.

Phase D is now unblocked. Sporemarch fix (a+b) + routing fix land ahead of user-sim Mission 8.

---

## Concerns

- [2026-04-13] **Worktree `claude/inspiring-newton` retire** — still held for host sign-off. Runbook at `docs/planning/worktree_retire_runbook.md`.
- [2026-04-14] **`default-universe` daemon still stuck pre-guardrail** — #6 universe-cycle + worldbuild no-op guardrails landed (`8ab17cd`, `afb9118`). A restart will self-pause at streak=5 with `idle_reason="universe_cycle_noop_streak"`, or make progress if premise is set. Operational action — host-gated. Tray "Restart All" picks it up.
- [2026-04-14] **Sporemarch fix (b) multi-scene overshoot + dispatch-guard retention** — fix (b) landed at `0db181c` (commit-layer WorkTarget advance via chapter.py:run_scene hook). Reviewer non-blocking note: run_scene is a looping node, so multi-scene chapters bump target.metadata.scene_number by +N rather than +1, and run_scene drafts at `scenes_completed + 1` (chapter.py:42), NOT at `execution_scope.scene_number` — pinned coordinate drives advance but not what gets drafted. Verify altitude in next user-sim mission. Fix (a)'s dispatch guard at universe.py:173-174 retained as fallback; downgrade to log-only or remove once (b) proves stable in live. Sporemarch oscillation root-cause chain now fully addressed (a+b); re-test on B1-C15-S3 in Mission 8.
- [2026-04-14] **Memory scoping is file-path-only; no defense-in-depth at retrieval** — Sporemarch contamination root cause (CWD-relative KG/vector paths) was fixed via explicit-path guards (`workflow/knowledge/knowledge_graph.py:34-38`, `workflow/retrieval/vector_store.py:38-42`, `fantasy_author/__main__.py:293-310`; 20 isolation tests green). But `MemoryScope` at `workflow/memory/scoping.py` is unused on the hot retrieval path — if physical file contamination recurs, retrieval has no query-time defense. Medium design task.
- [2026-04-14] **Packaging mirror sync question (host)** — `packaging/claude-plugin/plugins/workflow-universe-server/runtime/fantasy_author/universe_server.py` has stale "Author" strings + is broadly stale vs. live `workflow/universe_server.py`. Reviewer flagged on #31 audit. Question for host: is the mirror auto-built at plugin release time, or hand-maintained? If hand-maintained, it needs scrubbing; if auto-built from `workflow/`, no action.
- [2026-04-14] **Phase 6.2 follow-ups** — 6.2.1 landed at `a657a92` (items 2 branch_rebound guard + 3 gates_disabled fallback). Item 4 (already_retracted idempotency) confirmed live at universe_server.py:6886-6893. Only remaining: item 1 private-Branch visibility filter at task #8 blocked on host direction. Reviewer self-corrected mid-audit that handler-level branch_rebound guard did ship at 81affa5 — 6.2.1 adds the storage-layer companion.
- [2026-04-14] **Phase D landed at `c5f29bb`** (reviewer PASS-WITH-NOTES). Fantasy universe-cycle now runs as a compiled BranchDefinition via the domain-trusted opaque node mechanism, behind `WORKFLOW_UNIFIED_EXECUTION=off` flag. Flag-off preserves legacy direct-graph path exactly. Accepted v1 regressions under flag-on (documented): pause/stop at wrapper-boundary granularity (§4.10); SqliteSaver checkpoints only 10 boundary fields, mid-cycle crash loses workflow_instructions etc. (§4.11, survivable via `_build_book_execution_seed` re-reading disk). Dev also tightened `_build_node`: body-less + no-registry nodes now raise `CompilerError` instead of silently returning `_passthrough`. Phase E unblocked. Flag default stays off until user-sim gates its flip.
- [2026-04-14] **Phase E follow-ups (2 remain, non-blocking)** — reviewer flagged at `29a71a7` audit: (1) `queue_cancel` on running tasks returns `running_tasks_require_host_override` rejection with no graph-level interrupt — use daemon pause/stop for in-flight interrupts; real cancel semantics land in Phase H; (2) Missing producer-registry-boundary test per preflight §4.4 invariant 3 — coverage gap, not correctness gap. Follow-up #3 (dispatcher-to-invocation plumbing) is resolved: Phase F delivered `_try_dispatcher_pick` + `_finalize_claimed_task` in `fantasy_author/__main__.py:_run_graph`.
- [2026-04-14] **Commit-failure-after-YAML-write divergence risk** — reviewer flagged at 6.3 audit: if `git_bridge.commit` raises after YAML has been staged, SQLite is committed + YAML on disk + no git commit. Shared failure mode with `save_branch_and_commit` from phase 7. Not a 6.3 regression. Worth documenting as platform-wide invariant; rare enough to defer dedicated fix until someone sees it in practice.
- [2026-04-14] **Phase D follow-ups (4, non-blocking)** — reviewer-flagged at `c5f29bb` audit: (1) User-registered Branches with body-less nodes (if any exist in prod SQLite registry) will fail compile on load — low-probability but release notes should mention; (2) Boundary-field count inconsistency across preflight §4.3 invariant 1 (6 fields) / seed YAML output_keys (7) / `_BOUNDARY_FIELDS` in wrapper (10) — doc-level only, implementation is correct per 6-field restore test; (3) Missing-yaml vs registry-miss hard-fail paths share contract but raise different exception types (FileNotFoundError vs CompilerError) — cosmetic; (4) Activity.log byte-parity under flag-on is not automated — verify manually during user-sim Mission 8 before recommending flag-default flip. Fold 1-3 into a docs-pass before flipping flag default; 4 is a live-test gate.
- [2026-04-14] **MCP always-allow toggle — needs live validation** — `scripts/claude_chat.py` now attempts to check "always allow" checkboxes/toggles before clicking Approve (`_try_check_always_allow` + JS `checkAlwaysAllowToggle` in auto-dismiss). Exact DOM structure of Claude.ai's per-tool dialog is unknown at write-time; selectors use `:near()` text proximity + `aria-label`/`labels[]`. Validate on next user-sim mission: `USER NOTE always-allowed <tool>` should appear once per tool, not on every call.
- [2026-04-14] **Phase F R13: pool double-execution accepted for v1** — Two daemons subscribed to the same pool may both pick up and execute the same task (no claim atomicity). First-push-wins on completion markers. Accepted per preflight §4.12 Q2. Revisit when maintenance pool has real content and 2+ subscribers — observed double-execution will then be the data needed to formalize claim semantics. Phase G bid atomicity is the resolution target.
- [2026-04-14] **Phase F follow-ups (3, non-blocking)** — reviewer flagged at `1d02903` audit: (1) Flag-flip requires daemon restart — `WORKFLOW_GOAL_POOL` read at import-time via `register_if_enabled()`; mid-run flips silently ignored. Matches Phase D `WORKFLOW_UNIFIED_EXECUTION` discipline but wasn't explicitly documented. (2) `repo_root` 30-parent walk can find the wrong `.git` in an ancestor-dotfiles setup (e.g. `.git` at user home). Production should set `WORKFLOW_REPO_ROOT` explicitly. (3) `claim_lost_to_cancel` log tag is slightly misleading when cause is actually another dispatcher claim rather than user-cancel — cosmetic. Document 1+2 in release notes; 3 can be split into two log tags in a later sweep.
- [2026-04-14] **`list_subscriptions` docstring mismatch** — tester caught at Phase F audit: `workflow/subscriptions.py:123` claims "sorted-deduped goal list"; implementation is insertion-order-preserving dedupe (not sorted). Zero data risk; docstring or code should reconcile. Preferred: fix docstring. Alternative (breaking if callers depend on insertion order): `return sorted(out)`.
- [2026-04-14] **Private-Branch visibility gap (host direction needed)** — reviewer 6.2 audit asked for private-Branch visibility filter on `list_gate_claims`/`gates_leaderboard`. Dev investigation: `branch_definitions` table has NO `visibility` column (author_server.py:310-326); only Goals have visibility. Three options: (A) schema migration add `visibility TEXT DEFAULT 'public'` to branch_definitions — destructive; (B) Goal-gated inheritance (Branch inherits privacy from bound Goal) — reinterprets spec; (C) different design entirely. Deferred to 6.2.2 blocking on host. PLAN.md "Private chats, public actions" + "Branches are first-class, long-lived, public-forkable" does not settle the question.
- [2026-04-14] **Phase G follow-ups (4, non-blocking)** — reviewer flagged at `cb7482f`+`2092499` audit (PASS-WITH-NOTES): (1) `NODE_BID_SENTINEL_PREFIX` constant: fixed — `__main__.py` now imports from `producers.node_bid` rather than duplicating the literal; (2) Flag-off bid_coefficient test: added `test_load_dispatcher_config_flag_off_bid_coefficient_stays_zero` at `2092499`; (3) `exec()` security posture docstring — pattern scan is a tripwire (not a sandbox); malicious approved node has full Python runtime access; document in `bids/README.md` for host operators; (4) No producer-side approval/pattern gate — unapproved-node bids waste one dispatcher pick before executor rejects; defense-in-depth opportunity for Phase H.
- [2026-04-14] **Phase G R5: NodeBid double-execution partially resolved** — `claim_node_bid()` advisory mechanism reduces the race window vs. Phase F R13 (no claim at all). Full atomicity (git-rename + push contention) deferred to Phase H. Phase F R13 Concern updated to reference Phase G's partial mitigation.
- [2026-04-14] **Phase G flag-restart requirement** — `WORKFLOW_PAID_MARKET` is import-time. Mid-run flip silently ignored. Document alongside Phase D `WORKFLOW_UNIFIED_EXECUTION` and Phase F `WORKFLOW_GOAL_POOL` in release notes. Same discipline as both predecessors.
- [2026-04-14] **Phase G node lookup uses disk walk, not SQLite registry** — `_node_bid_lookup_factory` in `__main__.py` walks `<repo_root>/branches/*.yaml`. A bid against a SQLite-only Branch (never exported to YAML) fails with `node_not_found` rather than finding the node. Acceptable for v1 (GitHub-as-catalog model). Phase H can add SQLite-aware lookup if this causes confusion.
- [2026-04-14] **Phase G deeper-audit gaps (second audit pass) — flag-flip BLOCKED** — independent second-audit of landed Phase G flagged more severe deviations than the prior STATUS entries. (B1) `claim_node_bid` shipped advisory-YAML-status-update; preflight §4.1 #1 specified git-pull-rebase + os.rename + commit + push + revert-on-push-fail with bid_outputs cleanup. R13 resolution target NOT delivered. Docstring acknowledges shipped-state matches Phase F accepted pattern, but preflight explicitly UPGRADED it. (B2) `workflow/settlements.py` module doesn't exist; settlement writing inlined at `fantasy_author/__main__.py:378-405` via `write_text` with NO existence check — **settlements overwriteable on retry**; preflight §4.1 #5b said immutable. Zero settlement tests. (D1) Three-layer defense at one boundary each, not both (preflight §R1 said both). (D2) `claim_node_bid` returns `bool`, preflight said `NodeBid | None`. (D3) `workflow/bid_ledger.py` undocumented scope addition. **Safety of what shipped is OK for v1 adversarial surface** (core execution still rejects unapproved + dangerous bids). `WORKFLOW_PAID_MARKET` MUST stay default-off until Phase G.1 closes these gaps + independent re-audit clears. Also: dev-2 WIP summary misrepresented the shipped state — described modules + features that don't exist. New team norm in lead prompts: dev summary must list "what's in the commit vs preflight spec" with deltas called out.

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
| **#56 Phase 6.2.2** — private-Branch visibility filter | `workflow/author_server.py`, `workflow/universe_server.py`, possibly new migration | 6.2.1 landed (`a657a92`) + host direction | blocked:host | Three design paths (schema migration add visibility column / Goal-gated inheritance / other) — pick one before claiming. Code shape trivial once direction chosen. |
| **Phase H** — host dashboard + MCP inspect surfaces | per rollout plan §Phase H | Phase G landed (`cb7482f`) | pending | UX-primary delivery vehicle. Where the user actually feels all the prior phases. |
| **Memory-scope defense-in-depth** (medium) | `workflow/memory/scoping.py`, `workflow/retrieval/agentic_search.py`, `workflow/retrieval/phase_context.py` | design pass | pending | Tag KG/vector rows with `universe_id` at write-time; filter at read-time. Defense-in-depth under existing file-path guards. |
| **Author → Daemon mass-rename** (large, deferred) | `fantasy_author/` module + `author_server.py` + `Author` class + identifier-tied "author" strings | host decision 2026-04-14 (memory `project_terminology_daemon.md`); after Phase C-H rollout settles | pending | Drive-by string fixes happening as code is touched (`619725e`, `90c3d3b` were first). Module rename is mass find-replace + import-rewrite + test sweep. Don't claim until C-H lands. |
| **Worktree retire** — runbook ready | repo-level | host sign-off | pending | `docs/planning/worktree_retire_runbook.md` is user-executable. Commands: `git worktree remove .claude/worktrees/inspiring-newton` + `git worktree prune`. Destructive; held for user. |

---

## Next Session Recommended Sequence

1. **User-sim Mission 8** — re-test Sporemarch queue drainage (fix a+b: `997f825`, `0db181c`) + dispatch_execution routing fix (`68400bc`). Validate multi-scene overshoot concern (fix b, live). Gate Phase D default flip (`WORKFLOW_UNIFIED_EXECUTION=1`). Phase D follow-up items 1-3 docs-pass should land before this flip.
2. **User-sim Mission 9** — end-to-end pool post-and-pick + NodeBid with all flags on (D+E+F+G). Two temp universes sharing a repo_root; (a) subscribe uni-B to test Goal, post from uni-A, assert uni-B daemon picks up; (b) submit NodeBid, daemon with WORKFLOW_PAID_MARKET=on picks up, bid_ledger entry written. Gates `WORKFLOW_GOAL_POOL` + `WORKFLOW_PAID_MARKET` default flips.
3. **Phase H** — host dashboard + MCP inspect surfaces. Unblocked: Phase G landed (`cb7482f`). First phase where all prior infrastructure becomes user-visible and steerable.

---

## Reference

- Memo + rollout: `docs/planning/daemon_task_economy.md`, `docs/exec-plans/daemon_task_economy_rollout.md` (`52b3031` + `6616db0` + `c3d13af`)
- Stress-test scenarios: `docs/planning/stress_test_scenarios.md` (`194ffcd`) — 28 scenarios across 10 subsystems, 14 P0 floor
- Phase C spec: `docs/specs/taskproducer_phase_c.md` (passed reviewer audit)
- Phase G preflight: `docs/specs/phase_g_preflight.md` (planner draft 2026-04-14)
- Outcome gates spec: `docs/specs/outcome_gates_phase6.md` (passed reviewer audit, 6.1 landed)
- User-sim Mission 7 transcript: `output/user_sim_session.md` tail
- Memory updates this session: `project_paid_requests_model.md`, `project_terminology_daemon.md`, `feedback_testing_philosophy.md` (UX is the benchmark), `feedback_commit_discipline.md` (tester-only green is not enough), `feedback_restart_daemon.md` (restart authorized via tray)
