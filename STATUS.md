# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; landed rows are deleted; Forever rule = 24/7 uptime with zero hosts online.

## Concerns

- **[P0 filed:2026-04-23]** Revert-loop daemon PAUSED; auto-recovery outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`.
- [filed:2026-04-22 verified:2026-04-25] `/etc/workflow/env` mode flip: Fix A landed bc079a0; host installer review pending.
- [filed:2026-04-20 verified:2026-04-27] `test_node_eval` roundtrip flake: Fix B landed 16d4823; watch ≥30d.
- [filed:2026-04-17 verified:2026-04-28] Privacy Q6.3 still-platform: third-party provider fallback policy in `workflow/providers/router.py`.
- [filed:2026-04-18 verified:2026-04-28] `add_canon_from_path` sensitivity: host Qs reframed by commons-first audit F3.
- [filed:2026-04-24] Task #9 host Qs: GH Actions GROQ/GEMINI/XAI secrets + rotation e2e after deploy step.
- **[P1 filed:2026-04-25 verified:2026-05-01]** BUG-034 ChatGPT approval stall; direct MCP needed to repair live branches.
- [filed:2026-04-28] Claude card matcher cleanup conflicts with legacy connector fallback test.
- **[P1 filed:2026-04-30]** Castles II run `28479d8ddfb44488` failed `provider_exhausted` at discovery; blocks branch-run proof (BUG-038).

## Work

Path: #18 cleared 2026-05-02 -> Arc C -> Phase 6 db rename. universe_server.py: 14012 -> 972 LOC live in main.

Run `python scripts/claim_check.py --provider <name>` before claiming. Claim by setting Status to `claimed:<name>`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Scorched exact-original proof - mount guard green; needs rights-cleared Kickstart + input/sound/tank-hit acceptance. | WebSite/site/static/play/scorched-tanks/licensed/kickstart-a500-1.3.rom (deployment-only; do not commit ROM) | rights-cleared Kickstart | host-action |
| Directory submissions + first-use evidence - OpenAI public/full/global intent supplied; app packet blocked on `/mcp` vs `/mcp-directory` mismatch, data disclosure, demo URL, tested prompts. | chatgpt-app-submission.json, docs/ops/mcp-*.md, docs/ops/openai-app-submission-prep-2026-05-02.md | choose URL/data policy; action-time upload/final-submit approval | host-decision |
| **#24 Arc C** - fixture migration + resolver deletion. | workflow/storage/__init__.py, workflow/api/{helpers,engine_helpers,wiki}.py, packaging/{mcpb,claude-plugin/plugins/workflow-universe-server/runtime}/, workflow_tray.py, fantasy_daemon/__main__.py, tests/, AGENTS.md, deploy/README.md | - | claimed:codex-gpt5-desktop ACTIVE 2026-05-02 |
| **Phase 6** (nav 2026-04-28): `.workflow.db`, `db_path()` fn, Option A migration, 30s restart, plugin minor-bump. ~2-3h dev + 1h host. | workflow/storage/__init__.py, packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/storage/__init__.py, tests/ | #24 | dev-ready |
| Community change loop - watch/canary green 2026-05-02 02:52Z; Claude Opus proof green; next blockers: goal_pool pickup + true child invoke. | docs/exec-plans/active/2026-04-30-live-community-reiteration-loop.md, docs/ops/auto-fix-runbook.md | - | monitoring |
| Goal-pool prod pickup flip - enable restart-time pool producer for public daemon/worker, then set live tier config. | deploy/compose.yml, deploy/workflow-env.template | Community loop proof 2026-05-02 | claimed:codex-loop-uptime |
| Daemon soul followups - mini-brain pytest promotion and flagship core routing. | workflow/daemon_{registry,wiki,memory,brain}.py, workflow/dispatcher.py, workflow/api/universe.py, fantasy_daemon/api.py, tests/ | #24 Arc C | dev-ready |
| Enable Actions PR creation for auto-fix - repo has read-only workflow perms; permission flip needs action-time confirmation. | GitHub repo settings | PR #100/#104 show branch push works | host-action |
| Legacy-branding + architecture-edges cleanup arcs - remaining batches after #18; A.1 unpack is multi-week. | tests/, workflow/{branches,runs}.py, docs/{specs,design-notes,exec-plans,audits}/ | - | nav-then-dev |
| R7 closure pass — items 6+7 obviated; 1-5 cover Arc B/C; 8 by #25. | docs/exec-plans/active/2026-04-19-rename-end-state.md | #25 | nav-then-dev |
| #28 domain extraction host questions — #29 decomposition is done; remaining Qs are tool shape, upload-policy placement, registration hook. | `docs/audits/2026-04-25-engine-domain-api-separation.md` | rename locks | host-review |
| Wiki #32 — loop-owned cleanup: lowercase BUG-003/023 rm + BUG-018 old-canonical cleanup. | wiki droplet + MCP | loop dev | claimed:loop-dev |
| Loop action: `rm pages/bugs/bug-003-...md` + `rm pages/bugs/bug-023-...md` (lowercase duplicates) | wiki droplet | Wiki #32 | claimed:loop-dev |
| Loop action: BUG-018 cleanup — fix old canonical before promoting/merging cleaned slug. | wiki droplet + MCP | Wiki #32 | claimed:loop-dev |
| Arch audit residual — R7 `daemon_server.py` storage split + `catalog/backend.py` service-layer inversion remain. | `docs/design-notes/2026-04-{24-architecture-audit,25-arch-audit-5-r7-split-scoping}.md` | Arc B | host-review |
| Layer-3 design session | `docs/design-notes/2026-04-23-layer-3-design-session-*.md` | host schedules | half-day |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | - | host or lead-with-PAT |
| Mission 10 retest | user-sim | host watches browser | claimed:user |
| Host-action: re-register `Workflow DEV` ChatGPT connector as workspace admin. | OpenAI workspace admin | - | host-action |
| Memory-scope Stage 2c flag — watch started 2026-04-16; earliest flip 2026-05-16. | `docs/exec-plans/active/2026-04-27-memory-scope-stage-2c-flip-prep.md` | date gate | monitoring |
| Provider/DO key exposure audit — no concrete tokens found 2026-05-01; remaining DO refs are GH secret names for DR/P0 workflows. | `deploy/*`, `.github/workflows/{dr-drill,p0-outage-triage}.yml` | host decision | host-decision |
| Site cert flip — GitHub Pages still says "certificate does not exist yet"; CF edge green via MCP canaries + in-app smoke. | - | - | monitoring |

## Next

1. **Current uptime priority 2026-05-02:** live community patch loop stays top lane; P1a attach + incentive pickup v0 + Claude rendered proof green; next is goal_pool pickup + true child invoke.

2. **Five Scoping Rules now in PLAN.md** (2026-04-28): minimal-primitives / community-build-over-platform / privacy-via-community-composition / commons-first-architecture / user-capability-axis. Cross-provider source. Depth in lead memory.
3. **Decision pile awaiting host:** primitive-set §7 + engine substrate §7 + Tomas + A.1 unpack §7 + Phase 6 db rename + parked Q D.
4. **No-shims-ever**, platform responsibility model, and public-surface probes after DNS/tunnel/Worker/connector changes are active.
