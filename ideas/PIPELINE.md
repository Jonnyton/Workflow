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
- `reframed-community-build`: feature was approved as a concept but declined as a platform primitive per `project_community_build_over_platform_build` / `project_minimal_primitives_principle`; intent lives on as a community-build pattern (wiki rubric, chatbot composition, remixable node template) rather than platform code. Capture the composition path so the user-facing intent isn't lost.

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
| Methods-prose evaluator (Priya signal #2 / Proposal C) | reframed-community-build | `docs/design-notes/2026-04-27-methods-prose-evaluator.md` (reframe landed; platform-primitive path closed) | navigator + codex-gpt5-desktop | **REFRAMED 2026-04-26 per host directive** (memory: `project_community_build_over_platform_build`): platform will NOT ship methods-prose evaluator as a primitive. Chatbot composes from existing evaluator surface + wiki rubrics. Header/body reframe is now reflected in the design note and the matching STATUS concern was retired. No `EvaluatorKind` extension. INBOX provenance: 2026-04-27 entry. |
| Recency primitives — `extensions action=my_recent_runs` + `goals action=my_recent` (Priya signal #1) | promoted | `docs/specs/2026-04-27-recency-and-continue-branch-primitives.md` (contracts + dispatch conventions frozen; implementation remains post-#18). | codex-gpt5-desktop + dev | INBOX provenance: 2026-04-27 (recency-primitives). **APPROVED by host 2026-04-26** — extensions/goals action=verbs only (no new top-level tool). Pre-spec landed 2026-04-27 so implementation can start immediately when `workflow/api/runs.py` unlocks. |
| Continue-branch run primitive — `extensions action=continue_branch from_run_id=...` (Priya signal #6 + Devin Session 2 + 2026-04-24 extend-run dup) | promoted | `docs/specs/2026-04-27-recency-and-continue-branch-primitives.md` (v1 sibling-branch semantics + carry-over envelope frozen pre-implementation). | codex-gpt5-desktop + dev | INBOX provenance: 2026-04-27 (continue_branch) + 2026-04-24 (extend-run/continue-branch — MERGED, both reference same primitive gap). Distinct from `branches.py`'s authoring `_action_continue_branch`. **APPROVED by host 2026-04-26** — extensions/goals action=verbs only. Pre-spec landed 2026-04-27; implementation remains blocked by `#18` files lock. |
| Cross-algorithm methodological-parity guidance — `node action=compatibility_with` or wiki concept page (Priya signal #4) | promoted | `docs/design-notes/2026-04-27-cross-algorithm-methodological-parity-guidance.md` (wiki-first template selected; platform verb explicitly deferred unless structural insufficiency appears). | codex-gpt5-desktop | INBOX provenance: 2026-04-27 (cross-algorithm-parity). Promoted 2026-04-27: wiki concept-template path + RF-vs-MaxEnt seed checklist landed; next is a single wiki page + user-sim retrieval pass. |
| Trust-graduation observability — "% users skipping dry-inspect on session N" (Priya signal #7) | promoted | `docs/design-notes/2026-04-27-trust-graduation-observability-metric.md` (event contract + metric formula + guardrails frozen; implementation waits for observability lane). | codex-gpt5-desktop | INBOX provenance: 2026-04-27 (trust-graduation). Promoted 2026-04-27 as docs-ready instrumentation slice with one concrete metric definition. |
| CONTRIBUTORS.md authoring surface (Co-Authored-By attribution) | promoted | `docs/design-notes/2026-04-27-contributors-authoring-surface.md` (file-first canonical decision; daemon/MCP API deferred behind explicit volume/pain triggers). | codex-gpt5-desktop | INBOX provenance: 2026-04-25. Anchored in `AGENTS.md` Hard Rule #10 (read CONTRIBUTORS.md → emit Co-Authored-By). Promotion landed 2026-04-27 with decision + escalation criteria. |
| `hyperparameter_importance` evaluator node (Priya W&B signal #4) | triaged | science-domain skill catalog when that module is scoped — no current home | navigator | INBOX provenance: 2026-04-24 (Priya-W&B-trial). Domain-specific (scientific-computing skill, NOT engine). W&B-Sweeps parity. Cheap to add, high-value for scientific users. Waitlist until science-domain catalog exists. |
| Agent-teams-on-Workflow (open-source-Claude-Code-analog as a user project) | triaged | `docs/notes/2026-04-20-agent-teams-on-workflow-research.md` (research-note landed) → next: scoping exercise after uptime-track + daemon-economy first-draft land | navigator-followup | INBOX provenance: 2026-04-20 (host-source). Research note maps 11-seam gaps + viral-moment considerations + foundation/UX/commons rankings; recommends nano-claude-code as Python reference base. Required primitives: cross-branch teammate spawn, soul-file per teammate, inter-teammate messaging via bid market, partial-failure tolerance. **This is a USER project, not ours to build** — our job is platform primitives. **Blocked on uptime-track close + daemon-economy first-draft.** Scoping exercise opens after both unblock. |

## Backlog Burn-Down Queue (2026-04-28)

Ordered for fastest de-risking while #18/#23 remain in flight. Before moving
any row to `STATUS.md`, run
`python scripts/claim_check.py --provider <name> --check-files "<Files>"`.

| Priority | Claim-ready slice | Files boundary | Depends / blocker | Suggested owner | Exit check |
|---|---|---|---|---|---|
| 1 | Methods-prose evaluator community-build reframe. Reframe the design note as "declined platform primitive; accepted chatbot + wiki composition path." | `docs/design-notes/2026-04-27-methods-prose-evaluator.md`, `ideas/PIPELINE.md` | None; do not edit `workflow/*`. | navigator/docs | Header and TL;DR clearly say no `EvaluatorKind` extension; pipeline row state remains `reframed-community-build`. |
| 2 | Cross-algorithm methodological-parity wiki template. Draft the concept-page shape and one RF-vs-MaxEnt pseudo-absence example. | `wiki` draft page or `docs/notes/2026-04-28-methodological-parity-template.md`, `ideas/PIPELINE.md` | None; no MCP verb unless the example proves composition cannot work. | navigator/wiki | One reusable template exists; no platform primitive is proposed without structural blocker evidence. |
| 3 | CONTRIBUTORS.md authoring surface design. Choose file-only convention vs daemon/MCP surface. | `docs/design-notes/2026-04-28-contributors-authoring-surface.md`, `CONTRIBUTORS.md` (read), `AGENTS.md` (read) | None; keep Hard Rule #10 as current minimum path. | navigator/docs | Design note names the chosen surface, rejected alternative, and first user-sim persona (Ilse). |
| 4 | Recency primitives API shape spec (`my_recent_runs`, `my_recent`). Pre-write action contracts so dev can implement after #18. | `docs/specs/2026-04-28-recency-primitives.md`, `ideas/PIPELINE.md` | Blocked for code by #18 (`workflow/api/runs.py`, tests); docs-only spec can land now if `docs/specs/` is clear. | navigator then dev | Spec has request/response shapes, privacy scope, and MCP probe examples. |
| 5 | Continue-branch run semantics note (`continue_branch from_run_id`). Pin clone-vs-extend-vs-sibling semantics and carry-over fields. | `docs/design-notes/2026-04-28-continue-branch-run-semantics.md`, `ideas/PIPELINE.md` | Blocked for code by #18 and should follow recency primitive conventions. | navigator then dev | Note chooses one semantic model and lists exact state copied from the source run. |
| 6 | Trust-graduation observability metric. Convert "% users skipping dry-inspect on session N" into one watch metric. | `docs/design-notes/2026-04-28-trust-graduation-observability.md`, `ideas/PIPELINE.md` | Observability surface not open; do not instrument yet. | navigator/observability | Metric has numerator, denominator, event source, retention window, and dashboard/watch destination. |
| 7 | `hyperparameter_importance` evaluator node scoping. Park as scientific-computing domain catalog work. | Future science-domain catalog, `ideas/PIPELINE.md` | Domain catalog does not exist; no engine work. | future science-domain owner | A catalog row exists before any code task; engine remains untouched. |
| 8 | Agent-teams-on-Workflow scoping exercise. Treat as user project validation of platform primitives, not a platform build item. | `docs/notes/2026-04-20-agent-teams-on-workflow-research.md`, future scoping note | Blocked on uptime-track close + daemon-economy first draft. | navigator-followup | Scoping note maps required user-project primitives to existing roadmap without inventing a new platform track. |

## Archive

- [YYYY-MM-DD] Workflow seed-style retrofit initialized.
# 2026-04-09

- Research pipeline item: translate BettaFish's strongest pattern set into Workflow-native architecture.
- Source document: `docs/bettafish-refactor-research-2026-04-09.md`.
- Target outcome: narrative IR, staged drafting, typed deliberation bus, durable run ledger, and hard validation gates without adopting BettaFish's log-scraping transport, framework sprawl, or GPL-covered code.
