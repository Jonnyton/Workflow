# Maintenance Pool

The `maintenance` goal is the default subscription for fresh-install daemons. It's a shared inbox for low-priority upkeep tasks that any subscribed daemon can pick up.

Phase F ships this directory empty — the pool is live, but no tasks exist yet. First-wave maintenance tasks (index rebuilds, canon audits, KG consolidations) land here as separate follow-ups.

## Post format

Drop a YAML file here named `<branch_task_id>.yaml` with shape:

```yaml
branch_task_id: bt_1712876543210_abc123
branch_def_id: fantasy_author:universe_cycle_wrapper
goal_id: maintenance
inputs:
  active_series: my-series
  chapter_target: 5
priority_weight: 0.0
posted_by: host
```

`inputs` must be a flat dict of primitives (str, int, float, bool, null). Nested dicts and `_`-prefixed keys are rejected at both the post-side MCP action and the producer-side read.

## Posting via MCP

Prefer `universe action=post_to_goal_pool goal_id=maintenance branch_def_id=... inputs_json=...` over hand-writing YAMLs — the action enforces validation and returns a push hint.

## Cross-host visibility

This directory is in the repo. A post is locally visible immediately; cross-host subscribers see it after `git push`.
