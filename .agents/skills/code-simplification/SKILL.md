---
name: code-simplification
description: Writes the least code that works and simplifies existing code without changing behavior. Use when about to write new code (apply the minimalism ladder), when code is harder to read/maintain than it should be, or when auditing a diff or repo for over-engineering.
---

# Code Simplification

## Overview

The best code is the code never written. This skill has two lenses: **writing
lean** (the minimalism ladder, before you add code) and **simplifying existing
code** (reduce complexity without changing behavior). Simplicity is measured by
comprehension speed, not line count — but fewer moving parts is usually fewer
bugs.

## Lens 1 — The minimalism ladder (before writing new code)

Lazy means efficient, not careless. *After* you understand the problem — read
the task and trace the real flow end to end — stop at the first rung that holds:

1. **Does this need to exist at all?** Speculative need → skip it, say so. (YAGNI)
2. **Already in this codebase?** Reuse the helper/util/type/pattern that's here —
   re-implementing what's a few files over is the most common slop.
3. **Stdlib does it?** Use it.
4. **Native platform feature covers it?** (`<input type="date">` over a picker
   lib, CSS over JS, a DB constraint over app code.)
5. **An already-installed dependency solves it?** Use it. Never add a new
   dependency for what a few lines do.
6. **Can it be one line?** One line.
7. **Only then:** the minimum code that works.

**Rules:** no unrequested abstractions (no interface with one impl, factory for
one product, config for a constant), no scaffolding "for later", deletion over
addition, boring over clever, fewest files, shortest *working* diff (the smallest
change in the wrong place is a second bug). Complex request? Ship the lean version
and question the rest in the same response. Mark deliberate simplifications with a
`ponytail:` comment naming any known ceiling and upgrade path
(`# ponytail: global lock, per-account locks if throughput matters`).

**Bug fix = root cause, not symptom.** Grep every caller of the function you're
about to touch; one guard in the shared function is a smaller diff than one per
caller and doesn't leave sibling callers broken.

**Never be lazy about:** understanding the problem (the ladder shortens the
solution, never the reading), input validation at trust boundaries, error
handling that prevents data loss, security, accessibility, hardware calibration
(real clocks drift), or anything explicitly requested. Non-trivial logic leaves
ONE runnable check behind (an `assert` self-check or one small test) — trivial
one-liners need none.

## Lens 2 — Simplifying existing code (behavior-preserving)

Use after a feature works but feels heavier than needed, or when review flags
complexity. Don't simplify code you don't yet understand, performance-critical
paths where simpler is measurably slower, or throwaway code.

**Principles:** (1) **preserve behavior exactly** — same inputs/outputs/side
effects/errors, all tests pass unmodified; (2) **follow project conventions**
(read AGENTS.md / neighbors — simplification that breaks consistency is churn);
(3) **clarity over cleverness**; (4) **maintain balance** — don't over-inline,
merge unrelated logic, or strip abstractions that exist for testability; (5)
**scope to what changed** — no drive-by refactors.

**Process:** Understand before touching (Chesterton's Fence — check `git blame`
for why it exists) → identify opportunities → apply incrementally, one change at
a time, run tests after each → verify the whole is genuinely easier to read. If
the "simplified" version is harder to follow, revert. **Submit refactoring
separately from feature/bug work.** Rule of 500: refactors touching >500 lines
get automation (codemods/AST), not hand edits.

Common targets: deep nesting → guard clauses; long functions → focused splits;
nested ternaries → if/else or lookup; boolean flag params → options/objects;
generic names (`data`/`temp`/`result`) → descriptive; "what" comments → delete;
"why" comments → keep; duplicated logic → extract; dead code/unused
abstractions/redundant casts → remove.

## Lens 3 — Over-engineering audit (diff or repo)

A complexity-only sweep producing a ranked, actionable list (applies nothing).
One line per finding, biggest cut first, with a replacement:

`<tag> <what to cut>. <replacement>. [path:line]`

Tags: `delete:` (dead/speculative — replacement: nothing) · `stdlib:`
(hand-rolled what the stdlib ships — name the function) · `native:` (dep/code
doing what the platform does — name the feature) · `yagni:` (one-impl
abstraction, config nobody sets, one-caller layer) · `shrink:` (same logic,
fewer lines — show it). Hunt for: deps the platform already ships,
single-implementation interfaces, one-product factories, delegate-only wrappers,
dead flags/config. End with `net: -N lines, -M deps possible` or `Lean already.
Ship.` Correctness/security/performance are out of scope — route to a normal
review.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Fewer lines is always simpler" | A 1-line nested ternary isn't simpler than a 5-line if/else. Comprehension, not line count. |
| "This abstraction might be useful later" | Speculative abstraction is complexity without value. Add it when the second use appears. |
| "I'll refactor while adding the feature" | Separate them — mixed changes are hard to review and revert. |
| "The original author had a reason" | Maybe — check git blame (Chesterton's Fence). But complexity is often just residue of iteration under pressure. |

## Red Flags

Simplification that requires changing tests (you changed behavior) · "simplified"
code that's longer/harder · renaming to personal taste over project conventions ·
removing error handling for "cleanliness" · adding a dependency for what a few
lines do · unrequested abstractions · batching many changes into one untested
commit.

## Verification

- [ ] All existing tests pass unmodified; build clean; linter passes
- [ ] No new dependency added that the stack/stdlib already covers
- [ ] Each change is incremental and reviewable; diff has no unrelated churn
- [ ] No error handling removed; no dead code left behind
- [ ] A reviewer would call it a net improvement
