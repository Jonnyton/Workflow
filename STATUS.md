# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; landed rows are deleted; Forever rule = 24/7 uptime with zero hosts online.

## Concerns

- [2026-04-23] **P0 revert-loop: daemon PAUSED.** Auto-recovery outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`.
- [2026-04-20] Canonical public MCP: `tinyassets.io/mcp` -> 200; `mcp.tinyassets.io/mcp` -> gated internal origin only.
- [2026-04-22→25] `/etc/workflow/env` mode flip — Fix A landed (bc079a0: atomic mutator); awaits host review of installer behavior.
- [2026-04-20→27] `test_node_eval::test_record_and_get_stats_roundtrip` flake — Fix B landed (16d4823: wal_checkpoint(PASSIVE)); watching for recurrence ≥30d.
- [2026-04-26] Methods-prose evaluator REFRAMED community-build (host directive 2026-04-26): platform won't ship as primitive; chatbot composes from existing evaluator surface + wiki rubrics. Design-note header needs reframe.
- [2026-04-17] Privacy mode note has 3 host Qs: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`.
- [2026-04-18] `add_canon_from_path` sensitivity note has 3 host asks: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`.
- [2026-04-18] Claude.ai injection mitigation blocked on host-Q batch: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`.
- [2026-04-18] Full-platform architecture supersedes phased plan; migrate candidate: `docs/design-notes/2026-04-18-full-platform-architecture.md`.
- [2026-04-19] Navigator follow-up: modularity audit flags `universe_server`, discovery, and `daemon_server` seams.
- [2026-04-24] Task #9 host Qs: are GROQ/GEMINI/XAI in GH Actions secrets? Host validates rotation e2e after deploy step ships.
- **[P1 — provider-parity per 2026-04-26 capability-axis principle]** ChatGPT publish blocked: `Workflow DEV` connected as Plus/private app, not workspace admin (2026-04-25).
- **[P1]** ChatGPT connector approval bug: Update Node approval errored; retry saved node v2 (2026-04-25).
- **[P1]** ChatGPT Run Branch approval stalled after access grant; no run ID rendered (2026-04-25).
- **[P1]** ChatGPT UX: normal users need name-based workflow refs, not raw branch IDs (2026-04-25).
- **[P1]** BUG-034 ("No approval received") = ChatGPT connector approval bug — RECLASSIFIED P1 per provider-parity principle (was parked as "not server bug"). Platform-side mitigation track + OpenAI-side escalation track both needed. Workaround in wiki chatbot-builder-behaviors; status-comment post-redeploy.
- [2026-04-26] **NEW PRINCIPLES** in lead memory (foundational): `project_minimal_primitives_principle` (tool count is a budget that shrinks toward irreducible building blocks); `project_community_build_over_platform_build` (community evolves features, platform ships only primitives); `project_privacy_via_community_composition` (privacy modes = community-build, not platform). All future scoping runs the irreducibility test FIRST.
- [2026-04-26] `.codex/skills/` exists locally but is fully untracked + unsynced (per dev-2 #17 finding). Drift risk vs `.agents/skills/` + `.claude/skills/`. Decide: delete or add to sync-skills.ps1 targets.

## Approved Specs

Full specs: `docs/vetted-specs.md` (H2 heading per spec). Dev reads there, never wiki. On land, delete row + H2 section together.

| Spec | Status |
|---|---|
| [deferred] Daemon roster + node soul/ledger/attribution/royalty/outcome/bounty/fair-distribution items | needs-scoping |

## Work

State: Decomp Steps 8-11 LANDED (universe_server.py 14012 → 1771 LOC). Path: #18 retarget sweep (in flight) → Arc B (rename caller migration phase 2 — tests + workflow/api/runs.py) → Arc C (env-var aliases) → Phase 6 (.author_server.db rename, host-decision).

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| **#18 Step 11+ retarget sweep + Arc A/E shim deletion** — IN FLIGHT (dev Step 7/10; full-suite iteration). Realistic target ≈940 LOC residual, NOT ≤200 — ROI §5.2 enumerates ~470 LOC of Pattern A2 wrappers as floor; §5.1's ≤200 was internally inconsistent. | ~53 test files, universe_server.py, storage/__init__.py | - | claimed:dev |
| **#23 Arc B — caller-migration phase 1 LANDED (0cbdea9, 11 primary + 9 mirror, 11h ago); phase 2 (tests/ 192 sites + workflow/api/runs.py 3 sites) blocked on #18; phase 3 = 4-file deletion + smoke. Prep doc: docs/exec-plans/active/2026-04-26-decomp-arc-b-prep.md** | _rename_compat.py + 3 alias modules + tests/ + workflow/api/runs.py | #18 | dev (phase 2) |
| **#24 Arc C — env-var deprecation aliases (UNIVERSE_SERVER_BASE, WIKI_PATH)** | workflow/storage/__init__.py | #23 | dev |
| Phase 6 .author_server.db → .workflow.db migration (navigator review: APPROVE + 1 spec reconciliation §3 lazy-per-universe migration) | per design note 2026-04-27; 6 host asks: filename .workflow.db vs .daemon.db; fn name workflow_db_path() vs db_path(); approve scope/option-A/restart-window/plugin-bump | Arc C | host-decision |
| Architecture audit findings dispatched — see `docs/audits/2026-04-26-{legacy-branding-comprehensive-sweep,architecture-edges-sweep}.md`. ~10-15h cleanup queue + 1 multi-week structural arc (A.1 fantasy_daemon/ unpack) for navigator design note. | per audits | - | nav-then-dev |
| **Recency + continue_branch primitives APPROVED** (host 2026-04-26) — queue for dev post-#18. extensions/goals action=verbs only (no new top-level tool). | workflow/api/runs.py + workflow/api/market.py + new tests | #18 | dev-ready |
| Legacy-branding comprehensive cleanup (audit-then-execute) | per nav audit: docs/audits/2026-04-26-legacy-branding-comprehensive-sweep.md | nav SWEEP 1 | nav-then-dev |
| Architecture edges refactor (audit-then-execute, "button up not unplug") | per nav audit: docs/audits/2026-04-26-architecture-edges-sweep.md | nav SWEEP 2 | nav-then-dev |
| PLAN.md retirement of phased plan, full-platform architecture canonical | PLAN.md + docs/design-notes/2026-04-18-full-platform-architecture.md | nav SWEEP 2 finding | nav-then-dev |
| R7 storage-split status confirmation | exec-plan: `docs/exec-plans/active/2026-04-19-rename-end-state.md` | host | host-decision |
| Mark-branch canonical decision (Task #33 phase 0) | live MCP `goals action=propose/bind/set_canonical` | host | host-decision |
| #28 + #29 audit-doc review | `docs/audits/2026-04-25-{engine-domain-api-separation,universe-server-decomposition}.md` | host | host-review |
| Wiki status migration (#32) | live wiki via `wiki action=write` | cloud-redeploy | post-deploy |
| Arch audit #5/#6 + multi-week #9-#11 | `docs/design-notes/2026-04-24-architecture-audit.md` | host-review | host-review |
| Layer-3 design session | `docs/design-notes/2026-04-23-layer-3-design-session-*.md` | host schedules | half-day |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | - | host or lead-with-PAT |
| Mission 10 retest | user-sim | host watches browser | claimed:user |
| Memory-scope Stage 2c flag | - | 30d clean | monitoring |
| Remove provider+DO keys from persistent uptime surfaces | `deploy/*` | host Qs answered | host->e2e |

## Next

1. **dev's Task #18 WIP preserved in worktree.** universe_server.py at 972 LOC (target ~940 per ROI §5.2 reconciliation, NOT ≤200). Step 7/10 — full-suite iteration mid-flight. ~87 files modified including workflow/api/{evaluation,market,runs,status}.py + plugin mirror + ~50 test files. Next session: spawn dev fresh, point at the WIP, resume from full-suite green chase. Don't redo the script — it's already applied.
2. **Five foundational principles in lead memory** (all 2026-04-26/27): minimal-primitives / community-build-over-platform / privacy-via-community-composition / user-capability-axis / commons-first-architecture. Read MEMORY.md before scoping anything new.
3. **Decision pile awaiting host (large):** primitive-set proposal §7 (10 asks) + engine substrate §7 (4 asks) + Tomás persona approval + A.1 fantasy_daemon unpack §7 (7 asks) + Phase 6 db rename (6 asks) + parked Q D (file-reading split). Plus Task #29 commons-first audit deliverables when navigator lands them next session.
4. **No-shims-ever rule active** + **platform responsibility model** + **public-surface probes after DNS/tunnel/Worker/connector changes** (canonical: https://tinyassets.io/mcp).
5. dev-2 standing by post-#9/#17/#18-partial; Task #21 + #22 + #26 all blocked on dev's #18 ship. Task #29 (navigator commons-first audit) just dispatched; resumes next session.
