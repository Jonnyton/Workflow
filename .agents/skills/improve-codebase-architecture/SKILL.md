---
name: improve-codebase-architecture
description: Audits module boundaries, coupling, and naming drift to improve testability and navigability. Use when the user asks for an architecture review, spaghetti-code audit, modularity cleanup, seam extraction, or refactor targets for a large codebase.
---

# Improve Codebase Architecture

## Overview

Audit the codebase for structural problems that make it hard to reason about,
test, or change safely. Prefer boundary fixes and clearer ownership over large
rewrites.

## Workflow

### 1. Orient on live truth

- Read `STATUS.md` first.
- Load only the relevant `PLAN.md` sections or design notes for the area.
- If a documented principle conflicts with the current code, surface the
  contradiction before proposing changes.

### 2. Build the map

Use `zoom-out` thinking first:

- main entrypoints
- inbound callers
- outbound dependencies
- state boundaries
- external side effects

Do not call a module "spaghetti" until you can name the seam that is missing.

### 3. Look for architectural smells

Prioritize:

- god modules that mix orchestration, policy, and I/O
- cross-layer imports that bypass intended boundaries
- duplicated orchestration logic spread across files
- hidden global state or ambient config
- naming drift that hides distinct concepts behind one term
- shallow wrappers that add noise but no abstraction value
- modules that are hard to test because pure logic and side effects are fused

### 4. Judge by change cost

Report the issues that most damage:

- testability
- local reasoning
- onboarding speed
- AI navigability
- safe incremental change

Small, high-leverage seam fixes beat ambitious rewrites.

### 5. Recommend boundary-first changes

Prefer:

- extract pure policy from I/O wrappers
- split orchestration from leaf operations
- create explicit interfaces at subsystem edges
- rename overloaded concepts
- collapse accidental indirection

Avoid:

- repo-wide churn without proof
- stylistic refactors disguised as architecture work
- broad renames without a canonical language decision

### 6. Deliver findings in severity order

For each finding, include:

- what behavior or maintenance problem it causes
- where the seam breaks down
- the smallest credible fix
- what should stay unchanged for now

If you implement a fix, keep the diff surgical and prove behavior did not
change except where intended.

## Output Shape

Start with findings, highest severity first. Use file references and concrete
failure modes, not vague talk about "clean architecture."

## Verification

- [ ] Findings map to named module boundaries, not vibes
- [ ] Recommended changes are incremental and testable
- [ ] Changed boundaries have tests or existing tests proving behavior
- [ ] Docs or `STATUS.md` are updated when a contradiction matters
- [ ] No unrelated cleanup leaked into the implementation
