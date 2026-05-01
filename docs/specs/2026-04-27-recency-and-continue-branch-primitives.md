---
status: superseded
superseded_by: docs/design-notes/2026-04-25-extend-run-continue-branch.md
superseded_on: 2026-05-01
---

# Recency + Continue-Branch Primitives (Superseded Spec)

**Date:** 2026-04-27
**Author:** codex-gpt5-desktop
**Status:** Superseded 2026-05-01. F2 was accepted by host on
2026-04-28 as: drop Recency as a platform primitive and fold
`continue_branch` into the existing `run_branch` surface as
`resume_from=<run_id>`.

## 1. Superseding Decision

Do not implement these retired action contracts:

- `extensions action=my_recent_runs`
- `goals action=my_recent`
- `extensions action=continue_branch from_run_id=<run_id>`

The accepted post-`#18` implementation target is a single optional parameter
on the existing run action:

```
extensions action=run_branch branch_def_id=<target_branch> resume_from=<run_id>
```

The matching live work row is in `STATUS.md`:
`run_branch resume_from=<run_id>` param (F2 ACCEPTED 2026-04-28).

## 2. Current Contract

### 2.1 Input

Extend the existing `run_branch` action without adding a new action-table verb.

- `action` (required): `"run_branch"`
- existing branch selector and run inputs: unchanged
- `resume_from` (optional string): prior run id whose context should be used
  as the source for continuation

When `resume_from` is absent, `run_branch` behavior must remain unchanged.

### 2.2 Behavior

When `resume_from` is present:

- Resolve the source run by id.
- Enforce the same actor/visibility scope used by existing run reads.
- Reuse source-run context needed for continuation, including prior inputs and
  checkpoint/artifact references where the current run model supports them.
- Dispatch through the normal `run_branch` path; no standalone
  `continue_branch` execution path is introduced.
- Treat the branch named on the `run_branch` request as the target branch. The
  source run supplies continuation context, not a sibling-branch creation rule.

### 2.3 Output

Keep the existing `run_branch` success envelope. If the current envelope can
accept extra metadata without breaking callers, include:

- `resume_from` or `source_run_id`
- new run/request id already emitted by `run_branch`
- target branch id already emitted by `run_branch`

Do not create the historical `{ continuation: ... }` envelope from the retired
standalone action.

### 2.4 Error Model

Failures should be deterministic and fail loudly:

- `resume_from` id not found -> structured not-found error.
- source run belongs to a different actor scope -> unauthorized/not-visible
  error.
- source run state cannot be resumed from the target branch -> validation
  error naming the state/branch mismatch.
- malformed `resume_from` -> validation error.

## 3. Retired Recency Shape

The Recency part of this old spec failed the commons-first/minimal-primitive
retest in `docs/audits/2026-04-28-commons-first-tool-surface-audit.md`.
Chatbots can compose the user intent in 1-2 existing calls:

1. Query recent runs owned by the actor, newest first.
2. Optionally fetch the associated goal/branch context.

That is a documentation/wiki composition pattern, not a platform action.

## 4. Historical Context

This file is kept to preserve the decision trail for the 2026-04-27 backlog
promotion. It should not be used as an implementation source except to explain
why the old `my_recent*` and standalone `continue_branch` contracts were
retired.
