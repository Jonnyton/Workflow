# Cowork Substrate Primitive Audit Intake

**Status:** Proposed intake note
**Date:** 2026-05-06
**Request:** Issue #439 / WIKI-DESIGN
**Source wiki path:** `pages/notes/pages-notes-cowork-substrate-primitive-audit-2026-05-05.md`

## Classification

This is a **project design** request. It is not a bug report and does not ask
for runtime implementation.

The smallest useful project change is to preserve an intake decision for the
Cowork audit and define the gate it must clear before any substrate or MCP
tool-surface work is dispatched.

## Source State

The auto-filed issue points at a wiki page, but the page content is not present
in this repository checkout. A direct GitHub issue lookup on 2026-05-06 showed
no issue comments and only the synced wiki pointer. The GitHub wiki repository
was not available through the repository remote.

Because the audit body is unavailable, this note does not infer Cowork's
recommendations. It records the project-side intake policy only.

## Existing Design Constraints

Any Cowork substrate primitive recommendation must be checked against the
canonical scoping rules in `PLAN.md`:

- Minimal primitives: do not add a platform primitive for a convenience that a
  chatbot can compose from existing primitives.
- Community-build over platform-build: prefer a commons/wiki composition path
  unless a structural platform gap remains.
- Commons-first architecture: platform-stored data is public commons; private
  content remains host-resident.
- User capability axis: the primitive must name browser-only and local-app
  behavior across MCP hosts.

It must also fit the existing primitive budgets:

- User-facing MCP primitive set: `workspace`, `workflow`, `run`, `evaluate`,
  `commons`, plus local-app-only `host` and `upload`.
- Engine substrate primitive set: graph compile/execute, typed state/reducer,
  persistent checkpoint, provider routing, retrieval, evaluator, catalog, and
  dispatcher.

## Intake Decision

Do not create a new Cowork-specific substrate primitive from this filing alone.
Treat any Cowork-only behavior as either:

1. A provider capability profile within existing host/provider routing.
2. A harness/coordination convention documented in `AGENTS.md` if every
   provider needs it.
3. A provider-specific note only if it is purely about Cowork harness behavior.
4. A candidate ninth substrate primitive only after the recovered audit proves
   composition from the existing eight substrate primitives fails.

Any proposed MCP action from the recovered audit must run the cohit-prevention
check from `AGENTS.md` before drafting or implementation:

```bash
python scripts/check_primitive_exists.py action <verb>
```

## Review Gate Before Implementation

Implementation is blocked until the source audit content is recovered or
re-filed with enough detail to evaluate. The reviewer should then:

- Map every recommendation to an existing user-facing primitive and substrate
  primitive.
- Mark recommendations as composition, existing-primitive extension, or true
  primitive gap.
- Require opposite-family review before any code change, per the issue's daemon
  request contract.
- Update `PLAN.md` only with explicit host approval if the audit changes
  canonical primitive budgets.

Until then, this request should remain design-only.
