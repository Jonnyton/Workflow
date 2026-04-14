# Goal Pool Conventions

Phase F public-facing reference. Who can post, where it lands, how subscribers see it, how cross-host visibility works.

## Directory layout

```
<repo_root>/
  goal_pool/
    <goal_slug>/
      <branch_task_id>.yaml
      <branch_task_id>.yaml
      ...
    <another_goal>/
      ...
```

One directory per Goal. `<goal_slug>` is lowercase-hyphenated (e.g. `research-paper`, `maintenance`, `fantasy-novel`). Posts are YAML files whose stem IS the `branch_task_id` — the producer enforces stem/ID consistency.

## Repo root resolution

`workflow.producers.goal_pool.repo_root_path(universe_path)` resolves in this order:

1. `WORKFLOW_REPO_ROOT` env var — explicit host control, wins over everything.
2. Walk parents of `<universe_path>` looking for `.git`. Matches the "local-first, git-native" PLAN.md model.
3. `RuntimeError` with actionable hint if neither resolves. The pool producer treats this as "pool not available, empty result"; the `post_to_goal_pool` MCP action returns `{status: rejected, error: repo_root_not_resolvable, hint: ...}`.

Fallbacks intentionally do NOT include "cwd" or "parent of universe" — the env var covers exotic layouts; git-detect covers clones; nothing else is reliable.

## Post YAML shape

```yaml
branch_task_id: bt_1712876543210_abc123    # required; must match filename stem
branch_def_id: fantasy_author:universe_cycle_wrapper   # required; must resolve at subscriber
goal_id: maintenance                       # optional; directory wins on mismatch
inputs:                                    # required; flat dict of primitives
  active_series: my-series
  chapter_target: 5
priority_weight: 0.0                       # optional; clamped to 0 for non-host posters
posted_by: alice                           # optional attribution; stamped by server
```

### Flat-dict invariant (hard rule)

`inputs` MUST be a flat dict with primitive values only: `str`, `int`, `float`, `bool`, `None`. The following are rejected at BOTH post and read:

- Nested dicts or lists as values (e.g. `inputs: {outer: {inner: x}}`)
- Keys starting with `_` (e.g. `_universe_path`, `_db_path`)
- Keys in `{_universe_path, _db_path, _kg_path, work_target_ref}`

Rationale: these keys would smuggle universe-specific state across the isolation boundary (R4). A flat-only invariant is trivially correct; recursive strip is error-prone.

If a poster needs structured inputs, serialize them into a single string field and let the downstream Branch parse it.

## Posting

### Via MCP (preferred)

```
universe action=post_to_goal_pool
  goal_id=maintenance
  branch_def_id=fantasy_author:universe_cycle_wrapper
  inputs_json={"active_series": "x"}
```

Returns the absolute YAML path AND a `next_step` hint with the git commands needed for cross-host visibility.

### By hand

Drop the YAML into `<repo_root>/goal_pool/<goal>/<id>.yaml`. Post is live locally immediately; cross-host subscribers see it after `git push`.

## Subscribing

```
universe action=subscribe_goal goal_id=research-paper
universe action=unsubscribe_goal goal_id=research-paper
universe action=list_subscriptions
```

Each universe maintains its own `<universe>/subscriptions.json`. Fresh installs subscribe to `maintenance` by default. The list_subscriptions response includes a `config_vs_subscriptions_drift` flag to catch "I subscribed but pool isn't enabled" UX confusion.

## Non-host priority clamp

Phase E invariant 9 extends to pool posts. Non-host posters have `priority_weight` clamped to 0 at submission. Negative values rejected for all actors.

## Double-execution (accepted v1)

Two subscribers racing on the same pool YAML enqueue it in both queues and may both execute (R13). Accepted as a correctness cost, not a bug, for v1. Phase G's bid market reshapes this with claim semantics.
