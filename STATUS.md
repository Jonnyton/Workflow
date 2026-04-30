# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; landed rows are deleted; Forever rule = 24/7 uptime with zero hosts online.

## Concerns

- [filed:2026-04-23] **P0 revert-loop: daemon PAUSED.** Auto-recovery outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`.
- [filed:2026-04-22 verified:2026-04-25] `/etc/workflow/env` mode flip — Fix A landed (bc079a0: atomic mutator); awaits host review of installer behavior.
- [filed:2026-04-20 verified:2026-04-27] `test_node_eval::test_record_and_get_stats_roundtrip` flake — Fix B landed (16d4823: wal_checkpoint(PASSIVE)); watching for recurrence ≥30d.
- [filed:2026-04-17 verified:2026-04-28] Privacy mode note: 2 of 3 host-Qs OBVIATED by `project_privacy_via_community_composition` (Q6.1 threat-model + Q6.2 metadata are per-conversation chatbot calls). 1 STILL-PLATFORM: Q6.3 third-party providers in fallback chain (`workflow/providers/router.py` policy). Audit: `docs/audits/2026-04-28-rows-6-7-8-community-build-obviation-addendum.md`.
- [filed:2026-04-18 verified:2026-04-28] `add_canon_from_path` sensitivity note: 3 host-Qs all REFRAMED by commons-first audit F3 (self-auditing-tools structured caveats, not tool extraction). Audit: same as above.
- [filed:2026-04-19] Navigator follow-up: modularity audit flags `universe_server`, discovery, and `daemon_server` seams.
- [filed:2026-04-24] Task #9 host Qs: are GROQ/GEMINI/XAI in GH Actions secrets? Host validates rotation e2e after deploy step ships.
- **[P1 filed:2026-04-25 verified:2026-04-28]** BUG-034 ("No approval received") = ChatGPT connector approval bug (see BUG-034). Platform-side mitigation track + OpenAI-side escalation track both needed. Status comment landed on wiki page during 2026-04-28 drain. Rows 19/20 (Update Node + Run Branch approval) RETIRED as duplicates; row 21 (name-vs-ID UX) RETIRED — self-resolved per `.agents/activity.log:2026-04-24T20:11Z`. Audit: `docs/audits/2026-04-28-status-md-coordination-gap.md`.
- [filed:2026-04-28] Commons-first audit landed: 5 findings. F1 (`mcp_server.py` 12 stdio tools collapse to canonical-adapter) UNGATED — host 2026-04-28: no real users yet, dev-phase, deprecate freely. Auth-parity = navigator-internal investigation, not host-decision.
- [filed:2026-04-28] Internal-scoping items moved off host queue per `feedback_dont_ask_host_internal_scoping`: Phase 6 db rename + fantasy_author_original timing + R7 state + ChatGPT P1 fold-in are navigator+lead autonomous now.
- [filed:2026-04-28] Claude card matcher cleanup conflicts with `tests/test_claude_chat_inline_dismiss.py` legacy-connector fallback contract.
- **[P1 filed:2026-04-30]** Castles II live branch run `28479d8ddfb44488` failed `provider_exhausted` at `candidate_discovery`; blocks branch-run proof (see BUG-038).
- [filed:2026-04-30 verified:2026-04-30] Claude.ai rendered `ui-test` blocked until 2026-05-01 19:00 PT; rendered ChatGPT UI fallback green: `get_status` succeeded, universe `echoes-of-the-cosmos`.
- [filed:2026-04-30] Scorched Tanks exact-media page + branch shipped; needs post-fix real-user/Claude.ai clean-use check after `ui-test` unblock.

## Approved Specs

Full specs: `docs/vetted-specs.md` (H2 heading per spec). Dev reads there, never wiki. On land, delete row + H2 section together.

| Spec | Status |
|---|---|
| [deferred] Daemon roster + node soul/ledger/attribution/royalty/outcome/bounty/fair-distribution items | needs-scoping |

## Work

Path: #18 retarget sweep (live) → Arc B phase 2 → Arc C → Phase 6 db rename. universe_server.py: 14012 → 972 LOC live in main.

**Multi-provider note:** any provider runs `python scripts/claim_check.py --provider <yourname>` to discover what's safe to claim. AGENTS.md §"Parallel Dispatch" has the full ritual. Claim by editing the row's Status cell to `claimed:<yourname>`; reap stale claims with `reaped:<yourname>:<reason>`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| **#18 retarget sweep + Arc A/E shim deletion** — IN FLIGHT (dev Step 7/10, fail-fast iteration; first failure landed). Target ~940 LOC residual (ROI §5.2 floor). Lock: workflow/universe_server.py, workflow/api/{evaluation,market,runs,status,helpers}.py, plugin mirror, ~53 test files, workflow/storage/__init__.py. | workflow/universe_server.py, workflow/api/evaluation.py, workflow/api/market.py, workflow/api/runs.py, workflow/api/status.py, workflow/api/helpers.py, packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/, tests/ | - | claimed:dev |
| **#24 Arc C** — env-var deprecation aliases (UNIVERSE_SERVER_BASE, WIKI_PATH) | workflow/storage/__init__.py | - | dev-ready |
| **Phase 6** (nav 2026-04-28): `.workflow.db`, `db_path()` fn, Option A migration, 30s restart, plugin minor-bump. ~2-3h dev + 1h host. | workflow/storage/__init__.py, packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/storage/__init__.py, tests/ | #24 | dev-ready |
| `run_branch resume_from=<run_id>` param (F2 ACCEPTED 2026-04-28). Single param add. | workflow/api/runs.py, tests/ | #18 | dev-ready |
| Claude.ai injection mitigation — §5+§5.5 prompt-discipline edits. Per audit `docs/audits/2026-04-28-rows-6-7-8-community-build-obviation-addendum.md` §3. | workflow/universe_server.py, workflow/prompts/ | #18 | dev-ready |
| Community change loop — loop watch live: #90 red; request/gate/bounty contract is on main. Next: #18-blocked runtime gate-claim enforcement + writer queue/auth drain. | docs/exec-plans/active/2026-04-30-live-community-reiteration-loop.md, docs/ops/{auto-fix-runbook,wiki-bug-sync-runbook}.md, docs/conventions/gate-branch-shape.md, scripts/{wiki_bug_sync,community_loop_watch}.py, .github/workflows/{auto-fix-bug,daemon-request-policy,wiki-bug-sync,community-loop-watch,actionlint}.yml | #18 for runtime/test filing verb and market.py enforcement | claimed:codex-gpt5-desktop ACTIVE 2026-04-30 |
| Public endpoint + retired-branding docs hygiene — ACTIVE 2026-04-28 cursor-gpt55; stale tunnel-origin/api operator guidance fixed in ops/audits; continuing narrow docs sweep. | deploy/cloudflare-worker/README.md, deploy/cloudflared-README.md, docs/ops/acceptance-probe-catalog.md, docs/ops/day-of-cutover.md, docs/ops/launch-readiness-checklist.md, docs/audits/user-chat-intelligence/2026-04-19-p0-uptime-canary-probe.md, docs/audits/2026-04-20-public-mcp-outage-postmortem.md, docs/audits/2026-04-25-acceptance-probe-catalog-audit.md, docs/audits/2026-04-28-agent-memory-cross-drift-sweep.md, docs/audits/2026-04-28-project-instruction-files-cross-check.md, docs/design-notes/2026-04-19-uptime-canary-layered.md, docs/specs/2026-04-19-plan-b-selfhost-migration-playbook.md, docs/specs/phase_d_preflight.md, docs/specs/phase_e_preflight.md, docs/specs/phase_f_preflight.md, docs/specs/phase_h_preflight.md, docs/phase7_repo_setup.md, docs/plan_revalidation.md, docs/reality_audit.md | - | claimed:cursor-gpt55 |
| Legacy-branding + architecture-edges cleanup arcs — phase-docstring/live-terminology slice landed (36d3598); remaining test/rename/doc batches after #18. A.1 fantasy_daemon unpack is a multi-week design arc. | tests/, workflow/branches.py, workflow/runs.py, docs/specs/, docs/design-notes/, docs/exec-plans/active/, docs/audits/2026-04-26-legacy-branding-comprehensive-sweep.md (READ), docs/audits/2026-04-26-architecture-edges-sweep.md (READ) | #18 | nav-then-dev |
| Windows full-suite backup.sh path fix — clean HEAD: `bash.exe` receives raw `C:\...` path and cannot find script. | tests/test_backup_script.py | #18 | dev-ready |
| Clean-clone MCP config test mismatch — test expects ignored local `.mcp.json`; retarget to safe example config. | tests/test_mcp_server.py, .mcp.example.json, .gitignore | #18 | dev-ready |
| R7 closure pass — items 6+7 OBVIATED (audit `2026-04-28-internal-scoping-threads-abc.md` §3); 1-5 cover Arc B/C; 8 by #25. Doc-only retirement when #25 ships. | docs/exec-plans/active/2026-04-19-rename-end-state.md | #25 | nav-then-dev |
| #28 + #29 audit-doc review | `docs/audits/2026-04-25-{engine-domain-api-separation,universe-server-decomposition}.md` | host | host-review |
| Wiki #32 — wiki.py fix LIVE in prod (116a657 deployed 05:04Z); F4 composition-patterns promoted (45 pages); awaits 2 host `rm`s (lowercase BUG-003 + BUG-023 dupes) + BUG-018 promote Option B per `.claude/agent-memory/navigator/bug018_recommendation.md`. | wiki droplet + MCP | host | host-action |
| Host action: `rm pages/bugs/bug-003-...md` + `rm pages/bugs/bug-023-...md` (lowercase duplicates) | wiki droplet | - | host-action |
| Host decision: BUG-018 canonical filename has trailing hyphen — rename canonical to drop, or `wiki action=promote` draft to overwrite? | wiki | - | host-decision |
| Arch audit #5/#6 + multi-week #9-#11 | `docs/design-notes/2026-04-24-architecture-audit.md` | host-review | host-review |
| Layer-3 design session | `docs/design-notes/2026-04-23-layer-3-design-session-*.md` | host schedules | half-day |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | - | host or lead-with-PAT |
| Mission 10 retest | user-sim | host watches browser | claimed:user |
| Host-action: re-register `Workflow DEV` ChatGPT connector as workspace admin (was filed as Plus/private app 2026-04-25, blocks publish). | OpenAI workspace admin | - | host-action |
| Memory-scope Stage 2c flag | - | 30d clean | monitoring |
| Remove provider+DO keys from persistent uptime surfaces | `deploy/*` | host Qs answered | host->e2e |
| **Site shipped 2026-04-29 17:40Z** (commit 1e72ecd; cutover via `.github/workflows/site-dns-cutover.yml`). Post-launch backlog (nav forward-look): /host installer link → 404 GH releases (disable or "git clone"); footer socials drop/swap; /status static green pulse (false during outage); /alliance alert→mailto; legal refs missing `Workflow-catalog` repo; /account auth, baked-snapshot CI freshness, /contribute hard-coded counts. Forever-Rule add: PROBE-001 should also check `/` 200 (apex now shares with `/mcp`). | WebSite/site/src/{lib,routes}/, docs/ops/acceptance-probe-catalog.md, scripts/uptime_canary.py | - | dev-ready |
| Site cert flip — `gh api -X PUT repos/Jonnyton/Workflow/pages -F https_enforced=true` once GH Pages cert lands (5-15min from 17:40Z 2026-04-29). Edge HTTPS via CF proxy already serves. | - | - | monitoring |

## Next

1. **Active session 2026-04-27c**: dev resuming #18 (171 files unstaged, 972 LOC); dev-2 = #2 Layer-2 smoke DONE (exit 10 — module fix confirmed; heuristic loosen filed Task #7) → #3 methods-prose reframe → #4 Q6.3 platform impl; navigator = wiki sweep clean + Option C scoping rules → PLAN.md; verifier standby.
2. **Five Scoping Rules now in PLAN.md** (2026-04-28): minimal-primitives / community-build-over-platform / privacy-via-community-composition / commons-first-architecture / user-capability-axis. Cross-provider source. Depth in lead memory.
3. **Decision pile awaiting host (large):** primitive-set proposal §7 (10 asks) + engine substrate §7 (4 asks) + Tomás persona approval + A.1 fantasy_daemon unpack §7 (7 asks) + Phase 6 db rename (6 asks) + parked Q D (file-reading split). Plus Task #29 commons-first audit deliverables when navigator lands them next session.
4. **No-shims-ever rule active** + **platform responsibility model** + **public-surface probes after DNS/tunnel/Worker/connector changes** (canonical: https://tinyassets.io/mcp).
5. **BUG-028 reframe (nav 2026-04-27 evidence)**: alias-resolution at `wiki.py:409-423` is live in prod (6/8 writes succeeded 2026-04-28). 2 misroutes are CODE GAPS (BUG-003 `path.exists` wins; BUG-018 `.strip("-")` breaks trailing-hyphen) — dev-2 patching now. Not a redeploy gate.
