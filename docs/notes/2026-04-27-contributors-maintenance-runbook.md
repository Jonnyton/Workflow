# CONTRIBUTORS Maintenance Runbook

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: active runbook draft

## Purpose

Keep `CONTRIBUTORS.md` clean, merge-safe, and attribution-accurate under multi-provider edits.

## Edit rules

1. One actor per row.
2. Keep table sorted by `Actor ID` (case-insensitive).
3. Do not delete historical actor ids that already appeared in shipped attribution.
4. Prefer appending new rows, then sort once, over in-place row churn.

## Conflict resolution

When merge conflict occurs:

1. Keep union of rows from both sides.
2. Deduplicate by exact `Actor ID`.
3. If duplicate actor ids disagree:
   - keep latest known valid GitHub handle
   - keep most user-preferred display name if explicitly stated
4. Re-sort table and re-run quick scan for malformed handles.

## Hygiene checks

Before landing changes touching `CONTRIBUTORS.md`:

1. Every handle is username only (no `@`, no URL).
2. No blank `Actor ID` or handle cells.
3. No duplicate actor ids.
4. Header format remains unchanged.

## Attribution behavior reminder

If actor mapping is missing, commit flow must not block; skip unresolved ids silently per Hard Rule #10.

## Suggested periodic audit cadence

- Weekly: duplicate + malformed row scan.
- Monthly: prune obviously abandoned typo rows only when they were never used in shipped attribution.
