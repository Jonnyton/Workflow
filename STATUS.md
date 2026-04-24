# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; Concerns host-managed; Work rows delete when landed; Next replaced each session. Forever rule = 24/7 uptime with zero hosts online (see AGENTS.md top-of-file).

## Concerns

- [2026-04-23] **P0 revert-loop — daemon PAUSED**. 3 auto-recoveries (#51/#52/#53) but generator outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`. Task #8/#9 retire symptom/cause.
- [2026-04-20] **Option 1 LIVE 01:50 UTC** 976ba1c. `tinyassets.io/mcp` → 200 canonical; `mcp.tinyassets.io/mcp` → 403 gated. Worker `tinyassets-mcp-proxy` deployed w/ CF Access headers. **Host: rotate Global API Key** (used in session + terminal history).
- [2026-04-22] **P0 resolved 01:03 UTC** — `/etc/workflow/env` mode regressed 600 root:workflow on 2026-04-21 07:22; unit runs as user=workflow → EnvironmentFile unreadable → compose crash-loop (67 restarts) → cloudflared down → `tinyassets.io/mcp` 502 for ~18h. Fix: `chmod 640`. Root cause of mode flip unknown — `deploy-prod.yml` or bootstrap path may be overwriting w/ 600; needs audit so this doesn't recur silently overnight again.
- [2026-04-20] `test_node_eval::test_record_and_get_stats_roundtrip` pre-existing flake. Passes in isolation, flaky in full suite. Surface, not block.
- [2026-04-17] 589e1fb REST changes need tests: `/votes/{id}/resolve` forced; `/votes/{id}/ballots` now `{"vote": ...}`.
- [2026-04-17] Privacy mode note landed: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`; 3 host Qs remain.
- [2026-04-18] `add_canon_from_path` sensitivity note landed: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`; 3 host asks remain.
- [2026-04-18] Claude.ai injection mitigation work blocked on host-Q batch: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`.
- [2026-04-18] `fantasy_daemon/author_server.py` alias risk: snapshot export, not sys.modules rebind; fix there if cross-alias drift appears.
- [2026-04-18] Full-platform architecture supersedes phased plan: `docs/design-notes/2026-04-18-full-platform-architecture.md` (migrate to PLAN.md candidate).
- [2026-04-19] Navigator follow-up: `docs/design-notes/2026-04-19-modularity-audit.md` flags `universe_server`, discovery, and `daemon_server` seams.

---

## Approved specs (navigator-vetted)

Full specs: `docs/vetted-specs.md` (H2 heading per spec). Dev reads there, never wiki. On land, delete row + H2 section together.

| Spec | Status |
|---|---|
| Per-node llm_policy override | dev-dispatchable |
| In-flight run recovery — part 2 (SqliteSaver-keyed resume, node-escrow aware) | dev-dispatchable |
| Node checkpoints — partial-credit boundaries authored into node_def | dev-dispatchable |
| Gate bonuses — staked payouts attached to gate milestones | dev-dispatchable |
| Concurrency budget + observability for fan-out nodes | dev-dispatchable |
| Loud sandbox-unavailable surface for dev/checker exec nodes | dev-dispatchable |
| Sub-branch invocation primitive | dev-dispatchable |
| Cross-run state query primitive | dev-dispatchable |
| Scheduled + event-triggered branch invocation | dev-dispatchable |
| Project-scope persistent memory primitive | dev-dispatchable |
| file_bug is the feature-request verb — docstring + optional kind field | dev-dispatchable |
| Prompt_template literal-brace escape + build-time missing-key validation | claimed:dev |
| 8 navigator-promoted specs 2026-04-23 — see `docs/vetted-specs.md` §Navigator-promoted 2026-04-23 | dev-dispatchable |
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

Claim by setting Status to `claimed:yourname`. Files is the collision boundary. All Row-X tasks live in `docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Bundle ship (#2+#3+#5+#6) | 10 files listed in task #9 handoff | #6 verifier SHIP | claimed:team-lead |
| Tier 1 routing investigation (BUG-019/021/022) | `workflow/graph_compiler.py`, tests | bundle landed | claimed:dev |
| Lane 2: BUG-023 storage observability | TBD | BUG-023 body re-authored | claimed:dev (queued) |
| Lane 4: GH Actions auto-recovery.yml | `.github/workflows/auto-recovery.yml` | DO_API_TOKEN minted | claimed:team-lead |
| Layer-3 design session | `docs/design-notes/...` | host schedules | claimed:navigator (agenda draft) |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | #4 merged (4f936fe) | in-progress: run 24756582461 |
| Row F — 48h smoke + acceptance | `scripts/selfhost_smoke.py` | 48h green window | monitoring |
| Mission 10 retest | user-sim | host scope call | claimed:user |
| #19 Memory-scope Stage 2c flag | — | 30d clean | monitoring |

---

## Next

1. **Stack live:** canonical `tinyassets.io/mcp` 200 verified 2026-04-23 session start; DO Droplet auto-restart + nightly backup + offsite GH Release + 6 timers green. P0 RCA hardening fully landed (0217175/19c2261/a62ae30/4f936fe). Pushover priority=2 validated end-to-end; Bitwarden vault migration complete; CF Global Key rotated.
2. **Host or lead-with-PAT:** fire DR drill #3 via `workflow_dispatch`. Needs GH token w/ `actions:write` scope. Host dashboard click works too.
3. **Dev priority cascade:** pick next from approved-specs dev-dispatchable list (top: per-node llm_policy override, in-flight run recovery part 2, node checkpoints). Full specs in `docs/vetted-specs.md`.
4. **User-sim:** Mission 10 retest when host is watching browser. Until then user-sim runs offline persona work.
5. Subordinated: rename-end-state, #11 API asks, modularity-audit seams. Not blocking 24/7 uptime.
