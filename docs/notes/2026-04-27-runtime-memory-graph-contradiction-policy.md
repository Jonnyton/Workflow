# Runtime Memory Graph Contradiction Policy (v1)

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: implementation policy

## Problem

Prose-extracted structured state can disagree with existing typed records. v1 needs deterministic behavior.

## Policy

1. Never silently overwrite conflicting typed records.
2. Mark conflicts explicitly as contradiction records.
3. Keep both claims with provenance until resolved.

## Conflict detection trigger

When incoming packet proposes a `world_truth` triple whose `subject+predicate` matches an active truth with different `object`.

## v1 conflict handling

- existing record -> `status: active` (unchanged)
- incoming record -> `status: proposed_conflict`
- create `narrative_debt` of kind `tension` with `resolution_state: open`
- include both in retrieval envelope with contradiction flag

## Resolution path (manual/agentic)

Later pass may resolve by:

1. superseding old truth, or
2. keeping both as context-dependent truths, or
3. rejecting incoming extraction.

## Guardrails

- No auto-resolution in v1.
- No dropping provenance under any branch.
- Retrieval must expose contradiction status to planners/drafters.
