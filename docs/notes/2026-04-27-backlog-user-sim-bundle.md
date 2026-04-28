# Backlog User-Sim Verification Bundle

Date: 2026-04-27
Author: codex-gpt5-desktop
Purpose: one-shot user-sim script set for newly promoted backlog artifacts

## Script 1 — Cross-algorithm parity retrieval

Prompt:

> "I'm comparing RF and MaxEnt for the same species set. Before you summarize results, run your parity checklist and tell me which assumptions must be aligned."

Pass criteria:

- chatbot cites assumption-delta checks
- pseudo-absence/background parity is explicitly surfaced
- output references harmonized fold/threshold expectations

Backing artifacts:

- `docs/design-notes/2026-04-27-cross-algorithm-methodological-parity-guidance.md`
- `docs/notes/2026-04-27-cross-algorithm-parity-wiki-template.md`

## Script 2 — Methods-prose composition path

Prompt:

> "Draft a methods paragraph for my sweep and verify it against run artifacts using your existing evaluator surfaces and rubric guidance."

Pass criteria:

- chatbot does not claim a new platform primitive
- response frames check as composition (existing evaluator + rubric)
- mismatch reporting path is clear

Backing artifact:

- `docs/design-notes/2026-04-27-methods-prose-evaluator.md`

## Script 3 — Recency primitives readiness smoke (post-#18)

Prompt:

> "Show my recent runs and recent goals, then continue from run `<run_id>` with additional instructions."

Pass criteria:

- chatbot selects `my_recent_runs`, `my_recent`, and `continue_branch` verb shapes
- envelope expectations match pre-spec

Backing artifacts:

- `docs/specs/2026-04-27-recency-and-continue-branch-primitives.md`
- `docs/specs/2026-04-27-recency-continue-fixture-pack.md`
- `docs/exec-plans/active/2026-04-27-post-18-recency-continue-implementation-cards.md`

## Script 4 — Attribution path sanity

Prompt:

> "Prepare commit attribution for actor ids in this run."

Pass criteria:

- chatbot reads `CONTRIBUTORS.md` mapping style
- unresolved actor ids are skipped without blocking

Backing artifacts:

- `CONTRIBUTORS.md`
- `docs/design-notes/2026-04-27-contributors-authoring-surface.md`
