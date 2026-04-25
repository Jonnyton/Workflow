---
name: domain-model
description: Challenges plans and code against the project's concepts, invariants, and boundaries. Use when stress-testing a feature, spec, refactor, or workflow against existing domain language and design intent.
---

# Domain Model

## Overview

Challenge a proposal against the real domain model instead of accepting fuzzy
words at face value. The goal is sharper boundaries, sharper language, and
fewer design mistakes disguised as naming issues.

## Workflow

### 1. Load the existing model

Before asking questions:

- read `STATUS.md`
- load the relevant `PLAN.md` sections
- read the relevant vetted spec or design note
- inspect the current code paths for the concept being discussed

If the answer is already in code or docs, do not ask the user first.

### 2. Extract the domain structure

Identify:

- core nouns and actors
- ownership boundaries
- state transitions
- invariants
- external effects and integrations

### 3. Stress-test the proposal

Use concrete scenarios to expose ambiguity:

- edge cases
- partial failure paths
- cross-boundary handoffs
- resume/retry behavior
- authorization or ownership questions

### 4. Resolve remaining uncertainty

If something still cannot be answered from the repo, choose a conservative
default when the choice is reversible. Ask targeted questions only when no safe
default exists. Each question should resolve a real branch in the decision tree.

### 5. Surface contradictions immediately

If the user, code, and docs disagree, name it directly:

- what the code does now
- what the docs claim
- what the user seems to intend

Do not silently pick one.

### 6. Route follow-up correctly

- If the problem is terminology, use `ubiquitous-language`.
- If the problem is module boundaries, use `improve-codebase-architecture`.
- If the problem is missing durable rationale, use `documentation-and-adrs`.

## Output Shape

Summarize:

- stable concepts
- unresolved ambiguities
- violated invariants or boundary mismatches
- smallest next decision needed

## Verification

- [ ] Questions were exhausted against code and docs before asking the user
- [ ] Contradictions were surfaced explicitly
- [ ] Scenarios tested real boundary conditions, not toy examples
- [ ] Follow-up work is routed to the right specialist skill
