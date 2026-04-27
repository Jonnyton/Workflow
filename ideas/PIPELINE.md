# Idea Pipeline

This file turns captured ideas into deliberate outcomes instead of leaving them
as orphaned notes.

## States

- `captured`: recorded in `ideas/INBOX.md`, not yet clarified.
- `triaged`: deduplicated, sized, and given a next home.
- `promoted`: moved into a concrete surface such as `STATUS.md`,
  `docs/design-notes/`, `docs/exec-plans/active/`, or `PLAN.md`.
- `landed`: implemented and recorded in `ideas/SHIPPED.md`.
- `dropped`: intentionally declined or deferred with a reason.

## Promotion Paths

| Idea Shape | Next Home | Why |
|------------|-----------|-----|
| Small, ready, clearly bounded | `STATUS.md` `Work` | It is actionable now. |
| New truth, risk, or contradiction | `STATUS.md` `Concerns` | It changes what is currently true. |
| Needs reasoning or tradeoff analysis | `docs/design-notes/` | It needs durable thinking before build work. |
| Changes design truth | `PLAN.md` after user approval | The architecture or principles change. |
| Multi-step delivery with checkpoints | `docs/exec-plans/active/` | It is too large for one board row. |
| Already landed | `ideas/SHIPPED.md` | Keep the idea-to-shipping trail. |

## Session Triage Rule

1. Scan the oldest untriaged inbox items.
2. Merge duplicates and add links.
3. Promote at least one real item when the inbox is non-empty.
4. If nothing should move yet, record the blocker instead of leaving silence.

## Active Promotions

| Idea | State | Next Home | Owner | Notes |
|------|-------|-----------|-------|-------|
| Runtime fiction memory graph | promoted | `docs/design-notes/2026-04-09-runtime-fiction-memory-graph.md`, `docs/exec-plans/active/2026-04-09-runtime-fiction-memory-graph.md`, `docs/design-notes/2026-04-09-memory-graph-research-brief.md` | future session | Turn worldbuilding/docs output into typed world truth, event, epistemic, and narrative-debt memory with scene packets and generated indexes. Research brief added 2026-04-09 with frontier validation (DOME, SCORE, StoryWriter, A-Mem, LightRAG, MemOS) and concrete gap analysis. |
| Methods-prose evaluator (Priya signal #2 / Proposal C) | reframed-community-build | `docs/design-notes/2026-04-27-methods-prose-evaluator.md` (header reframe pending — STATUS Concern 2026-04-26 by lead) | navigator | **REFRAMED 2026-04-26 per host directive** (memory: `project_community_build_over_platform_build`): platform will NOT ship methods-prose evaluator as a primitive. Chatbot composes from existing evaluator surface + wiki rubrics. Design-note header needs reframe to "considered + declined as platform-build; community-build path." No `EvaluatorKind` extension. INBOX provenance: 2026-04-27 entry. |
| Recency primitives — `extensions action=my_recent_runs` + `goals action=my_recent` (Priya signal #1) | promoted | STATUS.md Work row "Recency + continue_branch primitives APPROVED" (dev-ready, post-#18). Next: `docs/specs/` for verb shapes + dispatch-table conventions. | navigator + dev | INBOX provenance: 2026-04-27 (recency-primitives). **APPROVED by host 2026-04-26** — extensions/goals action=verbs only (no new top-level tool). Files when scoped: `workflow/api/runs.py` (`_action_my_recent_runs`) + `workflow/api/market.py` (`_action_my_recent_goals`). Verification: live MCP via `mcp_probe.py`. Queued post-#18. |
| Continue-branch run primitive — `extensions action=continue_branch from_run_id=...` (Priya signal #6 + Devin Session 2 + 2026-04-24 extend-run dup) | promoted | STATUS.md Work row "Recency + continue_branch primitives APPROVED" (dev-ready, post-#18). Next: design-note enumerating clone-vs-extend semantics, then `docs/specs/`. | navigator + dev | INBOX provenance: 2026-04-27 (continue_branch) + 2026-04-24 (extend-run/continue-branch — MERGED, both reference same primitive gap). Distinct from `branches.py`'s authoring `_action_continue_branch`. **APPROVED by host 2026-04-26** — extensions/goals action=verbs only. Scoping qs from 2026-04-24 entry: (a) clone-and-add-nodes vs. re-run-with-params vs. sibling branch, (b) verb-name + signature, (c) state carryover. Depends on Step 8 + my_recent_runs. Queued post-#18. |
| Cross-algorithm methodological-parity guidance — `node action=compatibility_with` or wiki concept page (Priya signal #4) | triaged | `docs/design-notes/` first to choose surface — strong lean toward wiki concept page per `project_community_build_over_platform_build` (chatbot reads wiki, no platform primitive needed unless structurally impossible). | navigator | INBOX provenance: 2026-04-27 (cross-algorithm-parity). Per community-build-over-platform-build rule: default = wiki concept page, only escalate to MCP verb if structurally impossible. RF-vs-MaxEnt pseudo-absences is the seed example. Lower urgency than recency / continue_branch. |
| Trust-graduation observability — "% users skipping dry-inspect on session N" (Priya signal #7) | triaged | observability backlog — capture as STATUS Watch row when observability tooling exists | navigator | INBOX provenance: 2026-04-27 (trust-graduation). Small + platform-instrumentation, not chain-break. Deferred until observability surface lands. |
| CONTRIBUTORS.md authoring surface (Co-Authored-By attribution) | triaged | `docs/design-notes/` to decide standalone-file-convention vs. daemon_server.py table + MCP surface | navigator | INBOX provenance: 2026-04-25. Already partially anchored in `AGENTS.md` Hard Rule #10 (read CONTRIBUTORS.md → emit Co-Authored-By). Ilse persona (OSS-contributor tier) is the natural first user — good user-sim mission candidate. Seeded from `project_designer_royalties_and_bounties` agent memory. Promotion path = needs reasoning (verb vs file convention). |
| `hyperparameter_importance` evaluator node (Priya W&B signal #4) | triaged | science-domain skill catalog when that module is scoped — no current home | navigator | INBOX provenance: 2026-04-24 (Priya-W&B-trial). Domain-specific (scientific-computing skill, NOT engine). W&B-Sweeps parity. Cheap to add, high-value for scientific users. Waitlist until science-domain catalog exists. |
| Agent-teams-on-Workflow (open-source-Claude-Code-analog as a user project) | triaged | `docs/notes/2026-04-20-agent-teams-on-workflow-research.md` (research-note landed) → next: scoping exercise after uptime-track + daemon-economy first-draft land | navigator-followup | INBOX provenance: 2026-04-20 (host-source). Research note maps 11-seam gaps + viral-moment considerations + foundation/UX/commons rankings; recommends nano-claude-code as Python reference base. Required primitives: cross-branch teammate spawn, soul-file per teammate, inter-teammate messaging via bid market, partial-failure tolerance. **This is a USER project, not ours to build** — our job is platform primitives. **Blocked on uptime-track close + daemon-economy first-draft.** Scoping exercise opens after both unblock. |

## Archive

- [YYYY-MM-DD] Workflow seed-style retrofit initialized.
# 2026-04-09

- Research pipeline item: translate BettaFish's strongest pattern set into Workflow-native architecture.
- Source document: `docs/bettafish-refactor-research-2026-04-09.md`.
- Target outcome: narrative IR, staged drafting, typed deliberation bus, durable run ledger, and hard validation gates without adopting BettaFish's log-scraping transport, framework sprawl, or GPL-covered code.
