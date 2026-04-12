# Runtime Fiction Memory Graph Spec

## Goal

Improve long-run fiction coherence by introducing typed scene packets, entity
records, temporal/promissory/epistemic ledgers, and generated human-readable
indexes.

## Non-Goals

- Rewrite the entire runtime in one pass.
- Replace all markdown canon docs with opaque storage.
- Backfill every historical universe before the new path is proven.

## Acceptance Criteria

1. Newly committed scenes can emit a machine-readable packet without breaking
   prose output.
2. At least one durable ledger exists for temporal or promise tracking.
3. Retrieval can consume targeted state slices instead of only broad note
   blobs.
4. Human-readable generated indexes expose the new memory layer clearly enough
   for inspection and debugging.

## Constraints

- Technical: must coexist with current runtime while the migration is in
  progress.
- Product: should improve long-running fantasy coherence, not just create more
  storage.
- Operational: failures in extraction or ledger updates must be explicit.

## Verification

- Tests for packet emission and ledger updates
- Live proof on at least one clean universe
- Manual inspection of generated indexes and retrieval slices
