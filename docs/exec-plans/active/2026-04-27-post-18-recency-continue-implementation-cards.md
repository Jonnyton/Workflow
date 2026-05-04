# Post-#18 Implementation Cards: Recency + Continue Primitives

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: ready to execute on lock release

## Card A — `extensions action=my_recent_runs`

- **Files:** `workflow/api/runs.py`, `tests/`
- **Goal:** add `_action_my_recent_runs` with actor-scoped recent run summaries
- **Input contract:** from `docs/specs/2026-04-27-recency-and-continue-branch-primitives.md`
- **Tests:** use fixture pack `docs/specs/2026-04-27-recency-continue-fixture-pack.md`
- **Done when:** actor filter + limit behavior + envelope shape pass

## Card B — `goals action=my_recent`

- **Files:** `workflow/api/market.py`, `tests/`
- **Goal:** add `_action_my_recent` for actor-scoped goal recency
- **Dependency:** Card A conventions for ordering + bounds
- **Done when:** parity with runs recency behavior and deterministic output

## Card C — `extensions action=continue_branch`

- **Files:** `workflow/api/runs.py`, `tests/`
- **Goal:** add `_action_continue_branch` with `from_run_id` + `instructions`
- **Mode:** v1 `sibling-branch` only
- **Done when:** success + not-found + forbidden paths pass with stable envelopes

## Card D — Dispatch and fail-loud guarantees

- **Files:** `workflow/api/runs.py`, `workflow/api/market.py`, tests touching action routing
- **Goal:** ensure unknown actions remain explicit fail-loud errors
- **Done when:** no silent fallback behavior introduced

## Card E — Verification runbook

- focused tests for cards A-D
- full relevant suite slice for runs/market dispatch
- one live MCP probe sequence post-merge

## Sequencing

1. A
2. B
3. C
4. D
5. E

No re-scoping required unless `#18` changes dispatch architecture.
