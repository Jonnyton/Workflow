# `good-first-issue` convention

This repo labels issues with `good-first-issue` when they're a genuine on-ramp for new contributors — NOT when they're doc typos (the Hacktoberfest anti-pattern).

## What qualifies

A `good-first-issue` has all of:

1. **Bounded code change** — changes touch ≤2 files + ≤100 lines. Not a multi-module refactor; not a "fix a comma" either.
2. **Clear acceptance criteria** — the issue describes what the final behavior must be, with a test or reproduction case the contributor can point at to say "done."
3. **Reference pointers** — the issue links to ≥1 relevant file + function, so the contributor doesn't have to hunt for where to start.
4. **Realistic for a first contribution** — no tribal-knowledge gotchas. If the fix requires reading 3 internal design notes first, that's a `needs-intro` issue, not a `good-first-issue`.

## What does NOT qualify

- Documentation typos (file a PR directly — don't issue-farm).
- "Rename variable X" without a behavioral reason.
- Anything that starts with "refactor" — refactors are rarely good first issues.
- Issues where the root cause isn't understood yet — those are `needs-investigation`, not first issues.

## Target inventory

Sweet spot: **3-8 open `good-first-issue` items at any time.** Fewer than 3 → contributors read "no room for me." More than 8 → they read "unmaintained backlog."

Admin-pool members periodically (monthly) audit the label — stale items get un-labeled, fresh ones get added. Adding a new `good-first-issue` is as valuable as closing one; this is the tier-3 on-ramp surface.

## Related labels

- `needs-intro` — real issue but requires architectural context first. Link to the relevant design note in the issue body.
- `needs-investigation` — the bug is real but root cause isn't pinned. Don't hand these to first-timers.
- `help-wanted` — harder issues maintainers welcome outside help on. Assumes some familiarity with the codebase.
- `tier-3` — contributor-facing workstream, tied to the contribution paths in `CONTRIBUTING.md`.

## Writing a `good-first-issue` (template)

```markdown
## What

Brief description of the intended change.

## Why

Why this matters (user-facing behavior, design-note reference, etc.).

## Where

- File: `path/to/file.py:LINE` — entry point.
- Test: `tests/test_path.py::test_case` — existing coverage or where to add new.
- Design context (if needed): link to `docs/design-notes/...`.

## Acceptance

- [ ] Behavior matches <concrete description>.
- [ ] Tests pass (`pytest <relevant test path>`).
- [ ] `ruff check` clean on touched files.

## Maintainer availability

Assigned to <admin-pool member>. First-response SLA per `CONTRIBUTING.md` (48h weekday median).
```

This template is what `nav-bot` (or a human maintainer) uses when filing issues. Keeps the quality bar consistent.
