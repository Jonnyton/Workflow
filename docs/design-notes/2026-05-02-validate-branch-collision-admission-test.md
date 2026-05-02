---
title: Validate Branch Collision-Class Admission Test
date: 2026-05-02
status: proposed
source_request: WIKI-DESIGN / GitHub Issue #188
wiki_source: pages/plans/design-validate-branch-collision-admission-test.md
---

# Validate Branch Collision-Class Admission Test

## Classification

This is a project-design request. It does not ask for a new MCP primitive:
`validate_branch` already exists on `origin/main` and is wired through
`workflow/api/branches.py`.

The smallest useful project change is to pin the admission contract for a
future regression probe: which collision class it covers, what evidence makes
the probe catalog-worthy, and where implementation may happen without
redesigning community-authored branches.

## Collision Class

The target failure class is a branch-authoring collision where a branch-local
node id shadows an existing reusable node id and the system accepts the branch
without making the author choose between reuse and intentional override.

Current authoring paths already reject the high-risk form during write:
`add_node`, `build_branch`, and `patch_branch` require an explicit `node_ref`
or `intent="copy"` when the requested `node_id` collides with a standalone
registered node. That protects new writes. The remaining design question is
whether `validate_branch` should also surface the same class for imported,
legacy, or externally mutated branch definitions that bypassed those write
funnels.

## Admission Test

A `validate_branch` collision probe earns implementation and catalog admission
only if it satisfies all of these:

1. It has one red fixture: a persisted branch definition whose `node_defs`
   include a bare colliding `node_id` that differs from the reusable canonical
   node body and lacks explicit reuse provenance.
2. It has one green fixture for explicit reuse: the same `node_id` is accepted
   when the branch carries a canonical copied body or equivalent future
   provenance.
3. It has one green fixture for unrelated names: a normal valid branch with no
   collision remains valid and runnable.
4. The result is parseable without human judgment. `validate_branch` should
   return a structured collision warning or validation error that names the
   colliding `node_id`, the collided source (`standalone` in v1), and the
   author action (`use node_ref`, use explicit copy/override, or rename).
5. The probe does not add a new public MCP action and does not change branch
   execution semantics.

Until a live red/green baseline exists, this stays a design note rather than an
entry in `docs/ops/acceptance-probe-catalog.md`. The catalog requires a live
run plus at least one green baseline and one red/pre-fix baseline.

## Implementation Boundary

If promoted to code, keep the patch narrow:

- Runtime candidate: `workflow/api/branches.py::_ext_branch_validate`.
- Model helper candidate: `workflow/branches.py::BranchDefinition.validate`,
  only if the collision check can be expressed without importing API storage
  helpers or standalone-node registry code into the data model.
- Tests: extend `tests/test_node_ref_reuse.py` or add a focused
  `tests/test_validate_branch_collision.py`.
- No new primitive. The cohit-prevention check for
  `action validate_branch` currently reports a collision because the primitive
  already exists.

The preferred first implementation is a non-fatal structured warning, not a
hard invalidation, unless a current runtime path proves that legacy colliding
branches execute incorrectly. A warning preserves older branch data while still
giving chatbots a clear remediation path before run handoff.

## Gate Requirements

For a code-change PR based on this design:

- Writer family: Claude or Codex.
- Checker family: opposite family.
- Evidence: focused pytest covering red + green fixtures, `python -m ruff
  check` on touched Python files, and plugin mirror rebuild if canonical
  `workflow/*` runtime files change.
- Bounty: no special settlement rule; if a bounty is attached later, use the
  gate ladder's `bounty_requirements`.

## Non-Goals

- Do not redesign community-authored branches.
- Do not add another branch-validation MCP action.
- Do not catalog the probe before it has live or fixture-backed red/green
  evidence that matches the acceptance-probe catalog rules.
