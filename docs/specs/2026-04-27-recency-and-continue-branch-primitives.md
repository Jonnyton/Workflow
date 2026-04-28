---
status: active
---

# Recency + Continue-Branch Primitives (Pre-Implementation Spec)

**Date:** 2026-04-27
**Author:** codex-gpt5-desktop
**Status:** Pre-draft spec. Action signatures + test matrix frozen. Implementation blocked on `#18` file lock release (`workflow/api/runs.py`, `tests/`).

## 1. Scope

Define two user-facing action verbs on existing tool surfaces (no new top-level tool names):

1. `extensions action=my_recent_runs`
2. `extensions action=continue_branch from_run_id=<run_id>`

And one goals recency companion:

3. `goals action=my_recent`

This spec only freezes input/output contracts, dispatch routing, and tests so implementation can start immediately post-`#18`.

## 2. Non-goals

- No new top-level MCP tool.
- No changes to run execution semantics beyond "continue from prior run context."
- No broad schema migration.

## 3. API contracts

### 3.1 `extensions action=my_recent_runs`

**Inputs**
- `action` (required): `"my_recent_runs"`
- `limit` (optional int, default 10, max 50)
- `branch_id` (optional string filter)

**Behavior**
- Filter by current effective actor (`UNIVERSE_SERVER_USER` identity path used elsewhere).
- Return newest-first run summaries.

**Output shape**
- `{ ok: true, runs: [RunSummary], count: int }`
- `RunSummary` should include minimally:
  - `run_id`
  - `branch_id`
  - `status`
  - `created_at`
  - `goal_title` (when available)

### 3.2 `goals action=my_recent`

**Inputs**
- `action` (required): `"my_recent"`
- `limit` (optional int, default 10, max 50)

**Behavior**
- Filter goals by current effective actor.
- Return newest-first goal summaries.

**Output shape**
- `{ ok: true, goals: [GoalSummary], count: int }`

### 3.3 `extensions action=continue_branch`

**Inputs**
- `action` (required): `"continue_branch"`
- `from_run_id` (required string)
- `instructions` (required string; user intent for extension)
- `mode` (optional enum; default `"sibling-branch"`)
  - Allowed v1 values: `"sibling-branch"` only (freeze now, reserve future expansion)

**Behavior v1**
- Resolve source run by `from_run_id`.
- Create a sibling continuation context from source run's branch/run parameters.
- Apply new `instructions` as additive intent.
- Dispatch as a normal run request (no special execution path).

**Output shape**
- `{ ok: true, continuation: { source_run_id, new_branch_id, request_id } }`

## 4. Dispatch-table conventions

Follow existing `_action_*` routing conventions:

- `workflow/api/runs.py`
  - add `_action_my_recent_runs`
  - add `_action_continue_branch`
- `workflow/api/market.py` (or goals action host file)
  - add `_action_my_recent`

Action-table updates must preserve unknown-action fail-loud behavior.

## 5. Error model

Common failures should be deterministic:

- `from_run_id` not found → structured not-found error.
- `from_run_id` belongs to a different actor scope → unauthorized/not-visible error.
- `limit` out of range → validation error with accepted bounds.
- missing `instructions` for `continue_branch` → validation error.

## 6. Test matrix (minimum)

1. `my_recent_runs` returns only caller-owned runs.
2. `my_recent_runs limit` clamps/rejects as specified.
3. `my_recent` returns only caller-owned goals.
4. `continue_branch` creates continuation envelope with `source_run_id`, `new_branch_id`, `request_id`.
5. `continue_branch` rejects missing/unknown `from_run_id`.
6. cross-user visibility guard for `continue_branch`.
7. dispatch unknown action still fails loudly.

## 7. Rollout order post-#18

1. Implement `my_recent_runs`
2. Implement `my_recent`
3. Implement `continue_branch`
4. Run focused tests then full suite slices touching runs/market dispatch

## 8. Acceptance

This pre-spec is complete when:

- action names and parameters are frozen,
- output envelopes are frozen enough for tests/clients,
- implementation can proceed without re-opening product-scope debates.
