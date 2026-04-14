# Maintenance Pool

The `maintenance` goal pool contains daemon-agnostic housekeeping tasks that
any subscribed daemon can pick up when its own queue is idle.

Every daemon subscribes to `maintenance` by default on first boot (Phase F
invariant 10). This turns idle CPU into useful background work across all
universes that share this repo clone.

Phase F ships this directory empty — the pool is live, no tasks yet. First-wave
maintenance tasks (index rebuilds, KG consolidations, canon audits) land here as
separate follow-ups.

---

## What Goes Here

Maintenance tasks are **opportunistic** — they improve shared state but are
not urgent. Examples:

- **Index rebuilds** — regenerate vector embeddings after bulk canon changes.
- **KG consolidation** — merge near-duplicate entity records.
- **Canon audits** — flag unresolved promises, continuity gaps, orphaned targets.
- **Summary refresh** — regenerate hierarchical summaries after new chapters.

---

## Post Format

Each file `<branch_task_id>.yaml`:

```yaml
branch_task_id: bt_1712876543210_abc123    # must match filename stem
branch_def_id: fantasy_author/universe-cycle  # must resolve at subscriber
goal_id: maintenance
inputs:                                    # flat dict of primitives only
  active_series: my-series
  chapter_target: 5
priority_weight: 0.0                       # non-host posters clamped to 0
posted_by: host
```

`inputs` must be a **flat dict of primitives** (`str`, `int`, `float`, `bool`,
`null`). Nested dicts/lists and `_`-prefixed keys are rejected at both post and
producer-read time.

---

## Posting via MCP

```
action: post_to_goal_pool
goal_id: maintenance
branch_def_id: fantasy_author/universe-cycle
inputs_json: '{"active_series": "my-series"}'
```

Returns a git push hint for cross-host visibility.

---

## Cross-Host Visibility

This directory is tracked in the repo. A post is locally visible immediately.
Cross-host subscribers see it after `git push`:

```bash
git add goal_pool/maintenance/<task-id>.yaml
git commit -m "maintenance: describe the task"
git push
```

---

## Race Semantics (v1)

Multiple daemons may pick the same pool task concurrently. Phase F accepts
double-execution as acceptable for low-volume pools. Design tasks to be
**idempotent** — running the same consolidation or rebuild twice is harmless.

Phase G will introduce advisory claim semantics for pools where
double-execution is costly.
