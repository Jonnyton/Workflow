# Cross-Algorithm Parity Wiki Publication Checklist

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: ready

## Pre-publish

1. Pick comparison pair title (`A vs B methodological parity`).
2. Fill template sections from `docs/notes/2026-04-27-cross-algorithm-parity-wiki-template.md`.
3. Include at least one high-risk invalid-comparison example.
4. Include chatbot checklist block verbatim or with explicit domain edits.

## Evidence requirements

1. Reference concrete config assumptions for both algorithms.
2. State data-prep parity requirements (pseudo-absence/background, folds, thresholds).
3. Mark which metrics are directly comparable vs conditionally comparable.

## Publication

1. Create/update wiki concept page.
2. Add cross-link to parity design note.
3. Add one short "how chatbot should use this page" paragraph.

## Verification (user-sim)

Run prompt from user-sim bundle:

> "I'm comparing RF and MaxEnt for the same species set. Before you summarize results, run your parity checklist and tell me which assumptions must be aligned."

Pass if chatbot:

- surfaces assumption deltas,
- warns on pseudo-absence/background mismatch risk,
- asks for harmonization where needed before making superiority claims.

## Post-publish watch

For first 3 user-sim or real-user runs touching this comparison:

- collect one example where checklist prevented a bad inference,
- collect one confusion pattern to improve the page wording.
