---
status: active
---

# Recency + Continue Primitives Fixture Pack (Post-#18)

**Date:** 2026-04-27
**Author:** codex-gpt5-desktop
**Purpose:** eliminate test-data design time once `workflow/api/runs.py` lock clears.

## 1. Canonical fixture datasets

Create reusable fixtures in `tests/fixtures/`:

1. `runs_recent_mixed_authors.json`
   - 12 runs total
   - 7 for actor `alice`
   - 5 for actor `bob`
   - interleaved timestamps

2. `goals_recent_mixed_authors.json`
   - 9 goals total
   - mixed ownership + creation times

3. `runs_continue_source_catalog.json`
   - valid source run ids
   - missing run id case
   - cross-user run id case

## 2. Golden response snapshots

Expected payloads for stable assertions:

- `expected_my_recent_runs_limit_5_alice.json`
- `expected_my_recent_goals_limit_5_alice.json`
- `expected_continue_branch_success.json`
- `expected_continue_branch_not_found.json`
- `expected_continue_branch_forbidden.json`

## 3. Determinism rules

- Freeze timestamps to fixed ISO values.
- Name-sort tiebreaker for equal timestamps.
- Stable ordering required in all expected snapshots.

## 4. Test mapping

- `test_my_recent_runs_filters_by_actor`
- `test_my_recent_runs_limit_bounds`
- `test_my_recent_goals_filters_by_actor`
- `test_continue_branch_success_envelope`
- `test_continue_branch_not_found`
- `test_continue_branch_cross_user_forbidden`

## 5. Acceptance

Fixture pack is complete when a dev can implement action handlers and plug in these fixtures/snapshots without inventing additional data models.
