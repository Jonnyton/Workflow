# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; Concerns host-managed; Work rows delete when landed; Next replaced each session. Forever rule = 24/7 uptime with zero hosts online (see AGENTS.md top-of-file).

## Concerns

- [2026-04-23] **P0 revert-loop — daemon PAUSED**. 3 auto-recoveries (#51/#52/#53) but generator outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`. Task #8/#9 retire symptom/cause.
- [2026-04-20] **Option 1 LIVE 01:50 UTC** 976ba1c. `tinyassets.io/mcp` → 200 canonical; `mcp.tinyassets.io/mcp` → 403 gated. Worker `tinyassets-mcp-proxy` deployed w/ CF Access headers. Global API Key retired (use scoped CLOUDFLARE_API_TOKEN). Persistence purge → task #9.
- [2026-04-22] **P0 resolved 01:03 UTC** — `/etc/workflow/env` mode regressed 600 root:workflow on 2026-04-21 07:22; unit runs as user=workflow → EnvironmentFile unreadable → compose crash-loop (67 restarts) → cloudflared down → `tinyassets.io/mcp` 502 for ~18h. Fix: `chmod 640`. Root cause of mode flip unknown — `deploy-prod.yml` or bootstrap path may be overwriting w/ 600; needs audit so this doesn't recur silently overnight again.
- [2026-04-20] `test_node_eval::test_record_and_get_stats_roundtrip` pre-existing flake. Passes in isolation, flaky in full suite. Surface, not block.
- [2026-04-17] 589e1fb REST changes need tests: `/votes/{id}/resolve` forced; `/votes/{id}/ballots` now `{"vote": ...}`.
- [2026-04-17] Privacy mode note landed: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`; 3 host Qs remain.
- [2026-04-18] `add_canon_from_path` sensitivity note landed: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`; 3 host asks remain.
- [2026-04-18] Claude.ai injection mitigation work blocked on host-Q batch: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`.
- [2026-04-18] `fantasy_daemon/author_server.py` alias risk: snapshot export, not sys.modules rebind; fix there if cross-alias drift appears.
- [2026-04-18] Full-platform architecture supersedes phased plan: `docs/design-notes/2026-04-18-full-platform-architecture.md` (migrate to PLAN.md candidate).
- [2026-04-19] Navigator follow-up: `docs/design-notes/2026-04-19-modularity-audit.md` flags `universe_server`, discovery, and `daemon_server` seams.
- [2026-04-24] **Task #9 host Qs** — scope note landed `docs/design-notes/2026-04-24-vault-only-provider-keys.md`. Before dev dispatch: Q1: are GROQ/GEMINI/XAI already in GH Actions secrets (or must host seed them)? Q2: host validates rotation end-to-end after deploy step ships. See §Open Qs in note.
---

## Approved specs (navigator-vetted)

Full specs: `docs/vetted-specs.md` (H2 heading per spec). Dev reads there, never wiki. On land, delete row + H2 section together.

| Spec | Status |
|---|---|
| Per-node llm_policy override | claimed:dev-2 (pending verifier SHIP) |
| In-flight run recovery — part 2 (SqliteSaver-keyed resume, node-escrow aware) | dev-dispatchable |
| Node checkpoints — partial-credit boundaries authored into node_def | claimed:dev (pending verifier SHIP) |
| Gate bonuses — staked payouts attached to gate milestones | dev-dispatchable |
| Concurrency budget + observability for fan-out nodes | claimed:dev (pending verifier SHIP) |
| Loud sandbox-unavailable surface for dev/checker exec nodes | dev-dispatchable |
| Sub-branch invocation primitive | dev-dispatchable |
| Cross-run state query primitive | dev-dispatchable |
| Scheduled + event-triggered branch invocation | dev-dispatchable |
| Project-scope persistent memory primitive | dev-dispatchable |
| file_bug is the feature-request verb — docstring + optional kind field | claimed:dev-2 (pending verifier SHIP) |
| 8 navigator-promoted specs 2026-04-23 — see `docs/vetted-specs.md` §Navigator-promoted 2026-04-23 | dev-dispatchable |
| Continue branch — workspace-memory continuity primitive (PRIYA-R7 retention break) | dev-dispatchable (post-sweep) |
| Evaluator protocol — workflow/evaluation/__init__.py | claimed:dev (Task #17 in_progress) |
| Thundering-herd provider cooldown chain-drain detection (BUG-029) | dev-dispatchable |
| estimate_run_cost — cost + time estimate before dispatch | dev-dispatchable |
| get_status session_boundary field — explicit no-prior-session assertion | dev-dispatchable |
| get_status schema stability guarantee — schema_version + contract test | dev-dispatchable |
| [deferred] Daemon roster + soul.md authoring surface | deferred:needs-scoping |
| [deferred] Per-node soul_policy field on NodeDefinition | deferred:needs-scoping |
| [deferred] Branch-contribution ledger | deferred:needs-scoping |
| [deferred] Claim-time soul-fingerprint (anti-spoof) | deferred:needs-scoping |
| [deferred] Flexible escrow splits — arbitrary setter-declared distributions | deferred:needs-scoping |
| [deferred] Minimum-royalty enforcement on NodeDefinition + BranchDefinition | deferred:needs-scoping |
| [deferred] Attribution chain primitive (remix provenance) | deferred:needs-scoping |
| [deferred] Real-world outcome evaluator hook | deferred:needs-scoping |
| [deferred] Bug-bounty tracking + GitHub attribution | deferred:needs-scoping |
| [deferred] Fair-distribution calculator (navigator-adjudicator tooling) | deferred:needs-scoping |

---

## Work

**Session 2026-04-25 audit (dev-2): uncommitted backlog is MORE complete than STATUS.md implied.** #18/#19/#20/#21 all already complete in tree (pre-commit hook sync + 2 stale patch targets in `tests/test_universe_nodes.py` were the only real deltas). BUG-029 chain-drain Part B landed (`workflow/providers/router.py` + `tests/test_provider_router_bug029.py`, 13 new tests). Most navigator-promoted specs from 2026-04-23 are already implemented + tested: estimate_run_cost, session_boundary, schema_version, dry_inspect_node, storage_inspect, project_memory, recursion_limit_override.

**Reconciled spec status (navigator audit 2026-04-24, file:line evidence):**
- DONE in tree (verifier SHIP only): `query_runs`, `in-flight run recovery part 2` (SqliteSaver-keyed resume).
- PARTIAL: `sub-branch invocation` (schema in branches.py, graph_compiler execution path missing — dev-2 on it, Task #14); `loud sandbox-unavailable` (design-half done; missing get_status.sandbox_status + bwrap detection — Task #16).
- GENUINELY MISSING: `gate bonuses`; `publish_version` + `canonical_branch` + `fork_from` + `gate_event` + `gate-leaderboard` (multi-day, shared storage); `scheduled + event-triggered` (dev on it, Task #9).

**Wrap state:** still 192 files / 6761 insertions uncommitted. Verifier SHIP sweep + themed-bundle commits still pending — top priority for next session before any new spec dispatch. Verifier ran full-suite to 41% clean at wrap (no failures, normal skips). Pre-existing ruff issue in `workflow/desktop/tray.py` (unsorted imports) — fix when touched, not a blocker. Last commit: `3269dcd`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Verifier per-task SHIP sweep | 11 unverified tasks (see above list) | dev-2 stub fix | in_progress:verifier — resume next session |
| dev-2 stub fix | `tests/test_run_recursion_limit.py` `_FakeCompiled` stubs | — | in_progress:dev-2 |
| #18 Clear workflow/api/__init__.py domain wildcard (arch-audit #1) | `workflow/api/__init__.py` + 6 test files | — | in_progress:dev |
| #19-21 arch audit quick-wins (author_server pre-commit gate, prompt single-source, runtime.py rename) | see task descriptions | #18 precedes #20 | dev-dispatchable |
| Arch audit #5/#6 + multi-week #9-#11 (FastMCP submodules, R7 extractions) | see `docs/design-notes/2026-04-24-architecture-audit.md` | host-review before dispatch | host-review |
| #13 Wire enforce_write_cap into write sites | `workflow/**/*.py` write sites | #10 landed | dev-dispatchable (multi-day) |
| Layer-3 design session | `docs/design-notes/2026-04-23-layer-3-design-session-*.md` | host schedules | navigator+lead+host, half-day |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | — | host or lead-with-PAT |
| Mission 10 retest | user-sim | host watches browser | claimed:user |
| #19 Memory-scope Stage 2c flag | — | 30d clean | monitoring |
| #9 Remove provider+DO keys from persistent uptime surfaces (code landed, e2e blocked) | `deploy/*` | host Qs answered | host→e2e |
| STATUS.md Concerns cleanup pass | STATUS.md | — | host |

---

## Next

1. **Stack state @ 2026-04-24 wrap:** droplet `s-1vcpu-2gb` Up. `.pause` signal active. `tinyassets.io/mcp` 200. Session delivered 16 vetted specs in working tree — need verifier sweep + themed commits next session to land on main.
2. **First next-session action:** check dev-2 stub fix → restart verifier sweep → commit in themed bundles (can't do per-task commits cleanly; many tasks share `universe_server.py` + `branches.py`). Themed groups: llm_policy/runs/router; get_status surfaces (session_boundary/schema_version/estimate_run_cost/storage_inspect); file_bug kind + project-memory; BUG-029; conditional-edge pollution; vault-keys; node-checkpoints + concurrency-budget + recursion_limit + cross-run state. Verify each group's tasks all SHIP'd before commit.
3. **Host queue:** answer 2 Qs on task #9 (STATUS Concerns line 18); decide on architecture audit multi-week items #5/#6/#9-#11 (docs/design-notes/2026-04-24-architecture-audit.md); STATUS Concerns curation (navigator flagged /etc/workflow/env + full-platform-migration concerns as structurally retired).
4. **Architecture audit summary:** 6 findings, 4 queued as #18-21 (quick-wins, ≤1 day each). #1 critical PLAN violation (engine importing from domain). #5/#6 medium (R7 split stalled, inverted dep). #9-#11 multi-week FastMCP submodule extractions. Full doc: `docs/design-notes/2026-04-24-architecture-audit.md`.
5. **Memory corrections this session:** `project_daemon_default_behavior.md` rewritten (retired "1/provider free" quota framing; host's daemons = 1 always-on + testing, no quota rule). `feedback_structural_over_chores.md` added (reshape recurring ops chores into one-time fixes). Sweep landed: 3 doc retractions for stale payment-tier-popup phrasing.
6. **Control_station rule 13 shipped** to all 3 universe_server.py copies (re-anchor via tools, never assert from memory). Rule-13 test class #13 completed.
7. **User-sim:** Mission 10 retest when host watches browser. Offline persona work otherwise.
8. Subordinated: rename-end-state, modularity-audit seams. Not blocking 24/7 uptime.
