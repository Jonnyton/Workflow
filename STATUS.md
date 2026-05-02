# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; landed rows are deleted; Forever rule = 24/7 uptime with zero hosts online.

## Concerns

- **[P0 filed:2026-04-23]** Revert-loop daemon PAUSED; auto-recovery outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`.
- [filed:2026-04-22 verified:2026-04-25] `/etc/workflow/env` mode flip: Fix A landed bc079a0; host installer review pending.
- [filed:2026-04-20 verified:2026-04-27] `test_node_eval` roundtrip flake: Fix B landed 16d4823; watch ≥30d.
- [filed:2026-04-18 verified:2026-04-28] `add_canon_from_path` sensitivity: host Qs reframed by commons-first audit F3.
- [filed:2026-04-24] Task #9 host Qs: GH Actions GROQ/GEMINI/XAI secrets + rotation e2e after deploy step.
- **[P1 filed:2026-04-25 verified:2026-05-02]** BUG-034: PR #161 fixed legacy alias/`Unknown action`; public canaries green 2026-05-02T12:34-07:00; clean ChatGPT approval/write proof still pending. (see BUG-034)
- [filed:2026-04-28] Claude card matcher cleanup conflicts with legacy connector fallback test.
- **[P1 filed:2026-04-30]** Castles II run `28479d8ddfb44488` failed `provider_exhausted` at discovery; blocks branch-run proof (BUG-038).

## Work

Path: #18 cleared 2026-05-02 -> Arc C cleared -> Phase 6 db rename cleared. universe_server.py: 14012 -> 972 LOC live in main.

Run `python scripts/claim_check.py --provider <name>` before claiming. Claim by setting Status to `claimed:<name>`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Scorched exact-original proof - mount guard green; needs rights-cleared Kickstart + input/sound/tank-hit acceptance. | WebSite/site/static/play/scorched-tanks/licensed/kickstart-a500-1.3.rom (deployment-only; do not commit ROM) | rights-cleared Kickstart | host-action |
| Directory submissions + first-use evidence - PRs #123-#133 + #161 live; public canaries green 2026-05-02T12:34-07:00; needs clean ChatGPT/Claude proof + first-user evidence. | chatgpt-app-submission.json, docs/ops/mcp-*.md, docs/ops/openai-app-submission-prep-2026-05-02.md, docs/ops/mcp-host-proof-registry.md | action-time compliance/final-submit approval | host-action |
| OpenAI app submission hardening - refresh official requirements, audit `/mcp-directory` tools vs source hints, refactor submission packet/docs, and leave final submit blocked on action-time approval. | chatgpt-app-submission.json, docs/ops/openai-app-submission-prep-2026-05-02.md, docs/ops/openai-app-submission-readiness-2026-05-02.md, docs/ops/openai-app-submission-chatgpt-proof-2026-05-02.md, docs/ops/mcp-host-proof-registry.md, workflow/directory_server.py, packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/directory_server.py, tests/test_directory_server.py | clean ChatGPT approval/mobile proof; action-time final-submit approval | claimed:codex-gpt5-desktop-openai-submission |
| Community loop post-merge proof - #157 merged at `d897177`; verify deployed MCP, rerun canonical invoke smoke, then rendered connector proof. | output/user_sim_session.md, output/claude_chat_trace.md, .agents/uptime.log, MCP live branches fd5c66b1d87d/e019229850f9 | deploy of `d897177` | claimed:codex-loop-uptime-chatgpt |
| Daemon soul followups - flagship core routing + host review/editor. | workflow/daemon_{registry,wiki,memory}.py, workflow/dispatcher.py, workflow/api/universe.py, fantasy_daemon/api.py, tests/ | - | dev-ready |
| Enable Actions PR creation for auto-fix - repo has read-only workflow perms; permission flip needs action-time confirmation. | GitHub repo settings | PR #100/#104 show branch push works | host-action |
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

1. **Current uptime priority 2026-05-02:** live community patch loop; #157 is merged to main, next is deploy/canary/rendered proof; P1a `attach_existing_child_run` follows.

2. **Five Scoping Rules now in PLAN.md** (2026-04-28): minimal-primitives / community-build-over-platform / privacy-via-community-composition / commons-first-architecture / user-capability-axis. Cross-provider source. Depth in lead memory.
3. **Decision pile awaiting host:** primitive-set §7 + engine substrate §7 + Tomas + A.1 unpack §7 + Phase 6 db rename + parked Q D.
4. **No-shims-ever**, platform responsibility model, and public-surface probes after DNS/tunnel/Worker/connector changes are active.
