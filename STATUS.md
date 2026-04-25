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
| Continue branch — workspace-memory continuity primitive | claimed:dev (Task #37 in_progress) |
| Gate bonuses MCP wiring — claim/unstake/release with bonus_stake | claimed:dev (Task #38) |
| Payments escrow MCP wiring — extensions action=escrow_* | claimed:dev (Task #41) |
| patch_branch docstring batch-ops example + control_station hint | claimed:dev-2 (Task #39) |
| Maya LIVE-F3 vocabulary leak — control_station prompt discipline | claimed:dev-2 (Task #40) |
| teammate_message — inter-node messaging primitive (vetted-specs.md) | dev-dispatchable |
| In-flight run recovery — part 2 (SqliteSaver-keyed resume, node-escrow aware) | dev-dispatchable |
| publish_version + canonical_branch + fork_from + gate_event + gate-leaderboard | dev-dispatchable (multi-day) |
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

**Session 2026-04-25 wrap-state landed:** `55a874f` (17+ specs across 7 verifier-cleared bundles + post-sweep additive: scheduler, evaluation, idempotency, sandbox, memory, api/prompts, gates+payments+treasury+outcomes+attribution scaffolding, sub-branch, teammate_message, publish_version), `b2b3a25` (docs+skills+agents companion), `3c15cf9` (scheduler DOW fix + edge-case tests + gate_events scaffolding). Net `~25,000 insertions` across 250+ files. Last commit: `3c15cf9`.

**P0 #59 closed** — uptime canary back to green after pause-aware fix landed.

**Now-active dev queue:** continue_branch handler (#37), gate bonuses MCP wiring (#38), payments escrow MCP wiring (#41) — dev. patch_branch batch docs (#39), Maya vocabulary leak (#40) — dev-2. All on writable-now main; additive-only constraint lifted.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| continue_branch MCP handler (#37) | universe_server.py + mirror | — | in_progress:dev |
| gate bonuses MCP wiring (#38) | universe_server.py + gates/actions.py | #37 | claimed:dev |
| Payments escrow MCP wiring (#41) | universe_server.py + payments/actions.py | #38 | claimed:dev |
| patch_branch batch docs (#39) | universe_server.py docstring + prompt | — | claimed:dev-2 |
| Maya LIVE-F3 vocabulary leak (#40) | _CONTROL_STATION_PROMPT + grep test | #39 | claimed:dev-2 |
| Arch audit #5/#6 + multi-week #9-#11 | `docs/design-notes/2026-04-24-architecture-audit.md` | host-review | host-review |
| Layer-3 design session | `docs/design-notes/2026-04-23-layer-3-design-session-*.md` | host schedules | half-day |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | — | host or lead-with-PAT |
| Mission 10 retest | user-sim | host watches browser | claimed:user |
| Memory-scope Stage 2c flag | — | 30d clean | monitoring |
| Remove provider+DO keys from persistent uptime surfaces (code landed, e2e blocked) | `deploy/*` | host Qs answered | host→e2e |
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
