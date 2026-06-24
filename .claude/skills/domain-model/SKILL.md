---
name: domain-model
description: Stress-tests plans and code against the project's concepts, invariants, and boundaries, and hardens terminology. Use when challenging a feature/spec/refactor against design intent, or when terms drift, aliases accumulate, or concepts are overloaded.
---

# Domain Model

## Overview

Challenge a proposal against the real domain model instead of accepting fuzzy
words at face value, and keep one concept to one name. The goal is sharper
boundaries, sharper language, and fewer design mistakes disguised as naming
issues.

## 1. Load the existing model

Before asking the user anything: read `STATUS.md`, load relevant `PLAN.md`
sections, read the relevant vetted spec/design note, and inspect the current code
paths for the concept. If the answer is already in code or docs, don't ask first.

## 2. Extract the domain structure

Identify core nouns/actors, ownership boundaries, state transitions, invariants,
and external effects/integrations.

## 3. Stress-test the proposal

Use concrete scenarios to expose ambiguity: edge cases, partial-failure paths,
cross-boundary handoffs, resume/retry behavior, authorization/ownership. Test real
boundary conditions, not toy examples. Resolve remaining uncertainty with a
conservative default when reversible; ask targeted questions only when no safe
default exists.

## 4. Harden terminology (ubiquitous language)

Remove naming drift so humans and agents stop using one word for multiple
concepts or multiple words for one:

- **Gather terms** from user language, code identifiers, `PLAN.md`/specs/design
  notes, and issue/status wording.
- **Find drift** — one term for multiple concepts, multiple terms for one, legacy
  aliases leaking into active code, marketing words conflicting with
  implementation words.
- **Pick canonical language** — for each conflict define the canonical term, a
  short definition, what it is *not*, and acceptable aliases. Durable definitions
  land in `PLAN.md` (architectural/stable terms) or a design note — not a parallel
  glossary, not permanent `STATUS.md` entries.
- **Propagate with scope discipline** — rename only in justified scope; large
  sweeps need approval; boundary-first over cosmetic churn.

## 5. Surface contradictions immediately

If user, code, and docs disagree, name it: what the code does now, what the docs
claim, what the user intends. Don't silently pick one. Route boundary problems to
`improve-codebase-architecture` and missing durable rationale to
`documentation-and-adrs`.

## Output Shape

Stable concepts · unresolved ambiguities · violated invariants / boundary
mismatches · canonical-term table (term, meaning, rejected alternatives) · the
smallest next decision needed.

## Verification

- [ ] Questions exhausted against code and docs before asking the user
- [ ] Scenarios tested real boundary conditions; contradictions surfaced explicitly
- [ ] Each canonical term maps to one concept; durable updates landed in PLAN.md/design notes
- [ ] Renames stayed within approved scope; code and docs not left contradicting
