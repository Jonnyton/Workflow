# Runtime Fiction Memory Graph — Restart Cards

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: session-handoff ready

## Card 1 — Minimal schema checkpoint

- Reconfirm current typed entities to keep in v1:
  - world truth
  - event
  - epistemic claim
  - narrative debt
- Freeze field minimums before code edits.

## Card 2 — Scene packet ingestion thin slice

- Define one ingest path from scene packet into typed entities.
- Require provenance pointer per extracted fact.

## Card 3 — Index generation thin slice

- Generate one index artifact from typed memory graph.
- Verify deterministic ordering and stable IDs.

## Card 4 — Retrieval smoke

- Query by entity and by event.
- Ensure retrieval returns provenance and temporal bounds.

## Card 5 — Guardrails

- No speculative facts without provenance.
- No silent fallback to untyped blobs when typed write fails.

## Exit criteria

- A single end-to-end flow from scene packet -> typed graph -> queryable retrieval with provenance.
