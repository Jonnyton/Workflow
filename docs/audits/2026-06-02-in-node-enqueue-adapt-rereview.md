# In-node enqueue verb — ADAPT re-review brief (Codex, round 2)

**Writer:** claude-code (claude-opus-4-8) · **Reviewer family:** Codex
(opposite-provider) · **Date:** 2026-06-02

This is the re-review gate after the **ADAPT** verdict in
`2026-05-30-in-node-enqueue-codex-review.md` (recorded via PR #1217). The verb
still ships **dark** behind `WORKFLOW_NODE_ENQUEUE_ENABLED` (default off). A
Codex **approve** here is the gate to flip that flag on in production — it does
**not** gate the merge.

## What to review

- **PR #1221**, branch `claude/enqueue-adapt`, head `658d126a`.
- It closes the three ADAPT items. The two findings Codex marked ACCEPTABLE
  (Q2 cross-process lock, Q5 depth integrity) are unchanged; the Q6 failed-
  enqueue audit-record note is left as an explicit follow-up, not done here.

## Files / symbols

- `workflow/graph_compiler.py`
  - `NodeEnqueueContext` (new) — trusted, server-set `universe_id`, `actor`,
    `parent_branch_task_id`, `origin_branch_task_id`.
  - `_node_enqueue_branch_run` (rewritten) — Fixes 1+2+3.
  - `_node_enqueue_max_queue` / `_node_enqueue_max_lineage` (new env readers).
  - context threaded through `_build_node_mcp_invoker` → `_build_source_code_node`
    → `_build_node` → `compile_branch` (parallel to `invocation_depth`).
- `workflow/branch_tasks.py` — `BranchTask.parent_branch_task_id` /
  `origin_branch_task_id` (new, migration-safe); `QueueCapExceeded` +
  `append_task_capped` (atomic count-then-append under one lock).
- `workflow/runs.py` — `execute_branch` accepts `_enqueue_universe_id`
  `_parent_branch_task_id` `_origin_branch_task_id`, builds the context, threads
  it via `_invoke_graph` → `compile_branch`.
- `fantasy_daemon/__main__.py` — dispatcher passes `claimed_task.universe_id` /
  `.branch_task_id` / `.origin_branch_task_id` at the `execute_branch` call.
- Tests: `tests/test_node_enqueue_verb.py`, `tests/test_node_enqueue_concurrency.py`.

## How each ADAPT item was addressed

1. **Universe targeting (was Q3).** The queue write targets the run's own
   trusted `context.universe_id` only. A branch-supplied `universe_id` may only
   echo it (mismatch → refused). Empty trusted universe → fail closed
   (in-node enqueue is for dispatched runs; the async/MCP path passes no
   context and therefore cannot enqueue).
2. **Queue growth (was Q1).** Global active cap
   `WORKFLOW_NODE_ENQUEUE_MAX_QUEUE` (default 500) + per-origin lineage cap
   `WORKFLOW_NODE_ENQUEUE_MAX_LINEAGE` (default 200), both enforced inside
   `append_task_capped` under a single file lock (count + append atomic — no
   TOCTOU). Lineage = `origin_branch_task_id`, propagated server-side; a root
   run's first enqueue becomes its own origin.
3. **Branch authority (was Q4).** No new policy — reuses the existing
   public/private visibility model. Before append: `get_branch_definition`
   (KeyError → "does not exist", refused before any append); private branch
   runnable only when `author == context.actor`; public by any actor. (Host
   steer: scenario-specific authority — e.g. same-goal — is composed by the
   loop author, not baked into the primitive.)

## Re-review questions (don't rubber-stamp)

1. **Each ADAPT item fully closed?** Confirm Fix 1/2/3 actually hold and there
   is no remaining path to (a) target a non-current universe, (b) grow the
   queue past the caps, or (c) enqueue a non-existent / unauthorized branch.
2. **Spoof resistance.** A node controls `inputs` and its own kwargs. Confirm
   it cannot influence `universe_id`, `actor`, `parent_branch_task_id`, or
   `origin_branch_task_id` — all must come from `NodeEnqueueContext` (trusted),
   never kwargs/inputs. Check the kwargs→task field flow specifically.
3. **Cap atomicity.** Confirm `append_task_capped` counts and appends under one
   lock so concurrent enqueues cannot overshoot a cap. Is counting
   pending+running the right active-set definition? Is the per-origin scan over
   the full queue acceptable cost at the 500/200 ceilings?
4. **Fail-closed completeness.** Confirm no trusted context (async/MCP run,
   direct `execute_branch`, or a future caller) ⇒ refuse, never a silent
   default-universe write. Is "in-node enqueue only for dispatched runs" an
   acceptable boundary, or should the interactive path get a trusted context
   too?
5. **Authority reuse correctness.** Is `get_branch_definition` +
   author/visibility the right existing check to reuse, matching what
   `run_branch` enforces? Any visibility states beyond public/private (e.g.
   unlisted/archived) that this misses?
6. **Migration safety.** Confirm old `BranchTask` rows without the new fields
   load (default ""), and the new fields can't break the dispatcher claim path.

## Required output

Append a `## Verdict (codex round 2, YYYY-MM-DD)` section to THIS file:
**approve** / **adapt** / **reject**, reasoning per question. On **approve**,
the flag flip is unblocked. On **adapt**, list the concrete required changes.

## Evidence pointers

- enqueue verb + concurrency suites: 19 passed (new tests per fix incl. real
  `append_task_capped` global + per-origin enforcement).
- broader suites: 0 new failures. The 4 `test_dispatcher_queue` reds + 1
  `test_payload_keys_are_stable` red are pre-existing on clean origin/main
  (latter fixed by PR #1220), confirmed by running them without this branch.
- ruff clean; plugin mirror parity green; import probe ok.
- Prior verdict: `docs/audits/2026-05-30-in-node-enqueue-codex-review.md`
  (PR #1217).
