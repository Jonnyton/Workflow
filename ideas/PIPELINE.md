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
| Methods-prose evaluator (Priya signal #2 / Proposal C) | design-note-landed | `docs/design-notes/2026-04-27-methods-prose-evaluator.md` → next: `docs/specs/methods-prose-evaluator-v1.md` | navigator (pending host go) | Cross-layer chain-break: platform pitches "evaluator-driven workflows" but methods-section prose has no first-class evaluator. Note recommends Option 2 (ship `prose-versions` + `prose-reproducibility` for v1; defer citation + completeness to v2). Substrate change: add new kinds to `EvaluatorKind` literal at `workflow/evaluation/__init__.py:60`. **Blocked on host approval** of substrate extension + auto-invocation default — STATUS Concern row added 2026-04-27 by lead. INBOX provenance: 2026-04-27 entry. v2 follow-ups (citation + completeness) captured separately on next sweep. |

## Archive

- [YYYY-MM-DD] Workflow seed-style retrofit initialized.
# 2026-04-09

- Research pipeline item: translate BettaFish's strongest pattern set into Workflow-native architecture.
- Source document: `docs/bettafish-refactor-research-2026-04-09.md`.
- Target outcome: narrative IR, staged drafting, typed deliberation bus, durable run ledger, and hard validation gates without adopting BettaFish's log-scraping transport, framework sprawl, or GPL-covered code.
