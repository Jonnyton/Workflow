# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; landed rows are deleted; Forever rule = 24/7 uptime with zero hosts online.

## Concerns

- [filed:2026-04-23] **P0 revert-loop: daemon PAUSED.** Auto-recovery outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`.
- [filed:2026-04-22 verified:2026-04-25] `/etc/workflow/env` mode flip — Fix A landed (bc079a0: atomic mutator); awaits host review of installer behavior.
- [filed:2026-04-20 verified:2026-04-27] `test_node_eval::test_record_and_get_stats_roundtrip` flake — Fix B landed (16d4823: wal_checkpoint(PASSIVE)); watching for recurrence ≥30d.
- [filed:2026-04-17 verified:2026-04-28] Privacy mode note: 2 of 3 host-Qs OBVIATED by `project_privacy_via_community_composition` (Q6.1 threat-model + Q6.2 metadata are per-conversation chatbot calls). 1 STILL-PLATFORM: Q6.3 third-party providers in fallback chain (`workflow/providers/router.py` policy). Audit: `docs/audits/2026-04-28-rows-6-7-8-community-build-obviation-addendum.md`.
- [filed:2026-04-18 verified:2026-04-28] `add_canon_from_path` sensitivity note: 3 host-Qs all REFRAMED by commons-first audit F3 (self-auditing-tools structured caveats, not tool extraction). Audit: same as above.
- [filed:2026-04-24] Task #9 host Qs: are GROQ/GEMINI/XAI in GH Actions secrets? Host validates rotation e2e after deploy step ships.
- **[P1 filed:2026-04-25 verified:2026-05-01]** BUG-034 ("No approval received") = ChatGPT connector approval/post-approval stall; direct MCP needed to repair live branches. Audit: `docs/audits/2026-04-28-status-md-coordination-gap.md`.
- [filed:2026-04-28] Claude card matcher cleanup conflicts with `tests/test_claude_chat_inline_dismiss.py` legacy-connector fallback contract.
- **[P1 filed:2026-04-30]** Castles II live branch run `28479d8ddfb44488` failed `provider_exhausted` at `candidate_discovery`; blocks branch-run proof (see BUG-038).

## Approved Specs
Specs live in `docs/vetted-specs.md`; one deferred chatbot-first host-controls spec still needs scoping. On land, delete row + H2 together.

## Work

Path: #18 retarget sweep (live) → Arc B phase 2 → Arc C → Phase 6 db rename. universe_server.py: 14012 → 972 LOC live in main.

**Multi-provider note:** any provider runs `python scripts/claim_check.py --provider <yourname>` to discover what's safe to claim. AGENTS.md §"Parallel Dispatch" has the full ritual. Claim by editing the row's Status cell to `claimed:<yourname>`; reap stale claims with `reaped:<yourname>:<reason>`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Scorched exact-original proof — live mount guard green; acceptance still requires rights-cleared Kickstart path plus input, sound, and tank hit. | WebSite/site/static/play/scorched-tanks/licensed/kickstart-a500-1.3.rom (deployment-only; do not commit ROM) | rights-cleared Kickstart entitlement/source | host-action |
| External directory acceptance — MCP Registry + Claude/ChatGPT directory submissions; Open WebUI + LibreChat Docker proofs green; needs next local/IDE proof + first-user evidence. | packaging/registry/server.json, chatgpt-app-submission.json, docs/ops/mcp-*.md, docs/ops/open-webui-*.md, docs/ops/librechat-*.md, docs/design-notes/2026-05-01-mcp-host-customer-matrix.md, docs/exec-plans/active/2026-05-01-host-discoverability-and-onboarding-rollout.md | host/admin publisher + directory submissions | host-action |
| **#18 retarget sweep + Arc A/E shim deletion** — IN FLIGHT. Lock: universe_server/API helpers/plugin mirror/tests/storage. | workflow/universe_server.py, workflow/api/{evaluation,market,runs,status,helpers}.py, packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/, tests/, workflow/storage/__init__.py | - | claimed:dev |
| **#24 Arc C** — Phase 1 entrypoint env migration landed; remaining fixture migration + resolver deletion. | workflow/storage/__init__.py, workflow/api/helpers.py, packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/, tests/, AGENTS.md, deploy/README.md | #18 | dev-ready |
| **Phase 6** (nav 2026-04-28): `.workflow.db`, `db_path()` fn, Option A migration, 30s restart, plugin minor-bump. ~2-3h dev + 1h host. | workflow/storage/__init__.py, packaging/claude-plugin/plugins/workflow-universe-server/runtime/workflow/storage/__init__.py, tests/ | #24 | dev-ready |
| `run_branch resume_from=<run_id>` param (F2 ACCEPTED 2026-04-28). Single param add. | workflow/api/runs.py, tests/ | #18 | dev-ready |
| Claude.ai injection mitigation — §5+§5.5 prompt-discipline edits. Per audit `docs/audits/2026-04-28-rows-6-7-8-community-build-obviation-addendum.md` §3. | workflow/universe_server.py, workflow/prompts/ | #18 | dev-ready |
| Community change loop — controls live + rendered chatbot proof green; still needs post-fix real-user clean-use evidence. | docs/exec-plans/active/2026-04-30-live-community-reiteration-loop.md, docs/ops/auto-fix-runbook.md | #18 lock overlaps tests/docstrings | monitoring |
| Enable Actions PR creation for auto-fix — 2026-05-01 repo setting is `default_workflow_permissions=read`, `can_approve_pull_request_reviews=false`; flipping this GitHub permission requires action-time confirmation. | GitHub repo settings | PR #100/#104+ prove branch push works but PR creation blocked | host-action |
| Legacy-branding + architecture-edges cleanup arcs — remaining test/rename/doc batches after #18; A.1 unpack is multi-week. | tests/, workflow/{branches,runs}.py, docs/{specs,design-notes,exec-plans,audits}/ | #18 | nav-then-dev |
| Windows full-suite backup.sh path fix — clean HEAD: `bash.exe` receives raw `C:\...` path and cannot find script. | tests/test_backup_script.py | #18 | dev-ready |
| Clean-clone MCP config test mismatch — test expects ignored local `.mcp.json`; retarget to safe example config. | tests/test_mcp_server.py, .mcp.example.json, .gitignore | #18 | dev-ready |
| R7 closure pass — items 6+7 OBVIATED (audit `2026-04-28-internal-scoping-threads-abc.md` §3); 1-5 cover Arc B/C; 8 by #25. Doc-only retirement when #25 ships. | docs/exec-plans/active/2026-04-19-rename-end-state.md | #25 | nav-then-dev |
| #28 domain extraction host questions — #29 decomposition is done; remaining Qs are tool shape, upload-policy placement, registration hook. | `docs/audits/2026-04-25-engine-domain-api-separation.md` | #18 / rename locks | host-review |
| Wiki #32 — loop-owned cleanup: lowercase BUG-003/023 rm + BUG-018 old-canonical cleanup. | wiki droplet + MCP | loop dev | claimed:loop-dev |
| Loop action: `rm pages/bugs/bug-003-...md` + `rm pages/bugs/bug-023-...md` (lowercase duplicates) | wiki droplet | Wiki #32 | claimed:loop-dev |
| Loop action: BUG-018 cleanup — live canonical is `pages/bugs/BUG-018-...-.md` and draft is `drafts/bugs/bug-018-....md`; rename/delete old canonical before promoting or merging the cleaned slug. | wiki droplet + MCP | Wiki #32 | claimed:loop-dev |
| Arch audit residual — R7 `daemon_server.py` storage split + `catalog/backend.py` service-layer inversion remain. | `docs/design-notes/2026-04-{24-architecture-audit,25-arch-audit-5-r7-split-scoping}.md` | #18 / Arc B | host-review |
| Layer-3 design session | `docs/design-notes/2026-04-23-layer-3-design-session-*.md` | host schedules | half-day |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | - | host or lead-with-PAT |
| Mission 10 retest | user-sim | host watches browser | claimed:user |
| Host-action: re-register `Workflow DEV` ChatGPT connector as workspace admin (was filed as Plus/private app 2026-04-25, blocks publish). | OpenAI workspace admin | - | host-action |
| Memory-scope Stage 2c flag — 30d clean watch started 2026-04-16; earliest flip date 2026-05-16. Prep checklist exists; do not dispatch NodeScope dedup or flag flip before watch ends. | `docs/exec-plans/active/2026-04-27-memory-scope-stage-2c-flip-prep.md` | date gate | monitoring |
| Provider/DO key exposure audit — no concrete tokens found 2026-05-01; remaining DO refs are GH secret names for DR/P0 workflows. | `deploy/*`, `.github/workflows/{dr-drill,p0-outage-triage}.yml` | host decision | host-decision |
| Site cert flip — GitHub Pages HTTPS enforcement still blocked: 2026-05-01 recheck returned "certificate does not exist yet"; CF edge green via MCP canaries + in-app `/loop` to `/connect`/`/host` smoke. | - | - | monitoring |

## Next

1. **Today 2026-05-01:** `/mcp-directory` is live/protocol-green; completion now means MCP Registry publish + Claude/ChatGPT directory acceptance + no-dev-mode proof + first-user evidence.

2. **Five Scoping Rules now in PLAN.md** (2026-04-28): minimal-primitives / community-build-over-platform / privacy-via-community-composition / commons-first-architecture / user-capability-axis. Cross-provider source. Depth in lead memory.
3. **Decision pile awaiting host (large):** primitive-set proposal section 7 (10 asks) + engine substrate section 7 (4 asks) + Tomas persona approval + A.1 fantasy_daemon unpack section 7 (7 asks) + Phase 6 db rename (6 asks) + parked Q D (file-reading split). Commons-first audit deliverables have landed.
4. **No-shims-ever rule active** + **platform responsibility model** + **public-surface probes after DNS/tunnel/Worker/connector changes** (canonical: https://tinyassets.io/mcp).
