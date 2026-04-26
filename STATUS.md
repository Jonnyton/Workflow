# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; landed rows are deleted; Forever rule = 24/7 uptime with zero hosts online.

## Concerns

- [2026-04-23] **P0 revert-loop: daemon PAUSED.** Auto-recovery outran pruner. Trace: `docs/audits/2026-04-23-p0-auto-recovery-trace.md`.
- [2026-04-20] Canonical public MCP: `tinyassets.io/mcp` -> 200; `mcp.tinyassets.io/mcp` -> gated internal origin only.
- [2026-04-22→25] `/etc/workflow/env` mode flip — Fix A landed (bc079a0: atomic mutator); awaits host review of installer behavior.
- [2026-04-20] `test_node_eval::test_record_and_get_stats_roundtrip` pre-existing flake. Passes alone, flaky in full suite.
- [2026-04-17] Privacy mode note has 3 host Qs: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`.
- [2026-04-18] `add_canon_from_path` sensitivity note has 3 host asks: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`.
- [2026-04-18] Claude.ai injection mitigation blocked on host-Q batch: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`.
- [2026-04-18] Full-platform architecture supersedes phased plan; migrate candidate: `docs/design-notes/2026-04-18-full-platform-architecture.md`.
- [2026-04-19] Navigator follow-up: modularity audit flags `universe_server`, discovery, and `daemon_server` seams.
- [2026-04-24] Task #9 host Qs: are GROQ/GEMINI/XAI in GH Actions secrets? Host validates rotation e2e after deploy step ships.
- [2026-04-25] ChatGPT publish blocked in current login: `Workflow DEV` is connected as Plus/private app, not workspace admin.
- [2026-04-25] ChatGPT connector approval bug: Update Node approval errored; retry saved node v2.
- [2026-04-25] ChatGPT Run Branch approval stalled after access grant; no run ID rendered.
- [2026-04-25] ChatGPT UX: normal users need name-based workflow refs, not raw branch IDs.
- [2026-04-26] BUG-034 ("All extensions actions: No approval received") triaged: ChatGPT connector approval-prompt failure, NOT Workflow server bug (no `git grep` match in repo). Workaround documented in wiki `pages/plans/chatbot-builder-behaviors.md` §"When MCP actions return 'No approval received'": use `goals action=get goal_id=<id>` for read-only branch inspection. BUG-034 wiki page status-comment deferred until cloud redeploy lands BUG-028 alias-fix.

## Approved Specs

Full specs: `docs/vetted-specs.md` (H2 heading per spec). Dev reads there, never wiki. On land, delete row + H2 section together.

| Spec | Status |
|---|---|
| [deferred] Daemon roster + node soul/ledger/attribution/royalty/outcome/bounty/fair-distribution items | needs-scoping |

## Work

2026-04-26 baseline: 6113p / 0f / 14 skipped (vs 2811p/42f at 2026-04-15). Decomp Step 1 LANDED (4f98654 helpers extraction); Step 2 (wiki.py) verifier-pending; Steps 3-5 prep docs landed (004afd9 + 3ea263a-followup). PROBE-003 wiki_canary CI wiring LANDED (3ea263a). Host decisions outstanding: R7 storage split, Mark-branch-canonical, cloud daemon redeploy, audit-doc review for #28/#29.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Cloud daemon redeploy — picks up BUG-028 + #30 + #14 + others | DO droplet | host | host-action |
| R7 storage-split status confirmation | exec-plan: `docs/exec-plans/active/2026-04-19-rename-end-state.md` | host | host-decision |
| Mark-branch canonical decision (Task #33 phase 0) | live MCP `goals action=propose/bind/set_canonical` | host | host-decision |
| #28 + #29 audit-doc review | `docs/audits/2026-04-25-{engine-domain-api-separation,universe-server-decomposition}.md` | host | host-review |
| Wiki status migration (#32) — BUG-002/003/007/014A/015/016/018/020 + tier-1 page closing paragraph + BUG-003 dup cleanup | live wiki via `wiki action=write` | cloud-redeploy | post-deploy |
| Arch audit #5/#6 + multi-week #9-#11 | `docs/design-notes/2026-04-24-architecture-audit.md` | host-review | host-review |
| Layer-3 design session | `docs/design-notes/2026-04-23-layer-3-design-session-*.md` | host schedules | half-day |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | - | host or lead-with-PAT |
| Mission 10 retest | user-sim | host watches browser | claimed:user |
| Memory-scope Stage 2c flag | - | 30d clean | monitoring |
| Remove provider+DO keys from persistent uptime surfaces | `deploy/*` | host Qs answered | host->e2e |

## Next

1. Keep public-surface probes mandatory after any DNS/tunnel/Worker/connector change; canonical endpoint is `https://tinyassets.io/mcp`.
2. Continue active dev queue with verifier sweep before landing each group.
3. Host queue: answer task #9 key questions; decide arch audit #5/#6/#9-#11; curate remaining STATUS concerns.
4. User-sim: Mission 10 retest when host watches browser; subordinated rename/modularity seams remain nonblocking.
