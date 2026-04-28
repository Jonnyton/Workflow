---
status: active
---

# Runtime Memory Graph Minimal Schema v1

**Date:** 2026-04-27
**Author:** codex-gpt5-desktop
**Status:** pre-implementation schema freeze for thin-slice delivery

## 1. Scope

Define the smallest typed schema needed for:

- scene packet ingestion
- ledger updates
- retrieval with provenance

No full ontology expansion in v1.

## 2. Core entity types

1. `world_truth`
2. `event`
3. `epistemic_claim`
4. `narrative_debt`

## 3. Required fields (all entity types)

- `id` (stable string)
- `type` (enum of the 4 types)
- `summary` (short text)
- `source_ref` (scene id / artifact pointer)
- `provenance_kind` (e.g., extracted, asserted, inferred)
- `confidence` (0.0-1.0)
- `updated_at` (ISO timestamp)

## 4. Type-specific minimums

### `world_truth`
- `subject`
- `predicate`
- `object`
- `status` (`active`|`superseded`)

### `event`
- `scene_id`
- `participants` (list)
- `location_id` (optional)
- `time_marker` (optional)

### `epistemic_claim`
- `holder` (who knows/suspects/believes)
- `claim_ref` (points to truth/event)
- `belief_state` (`knows`|`suspects`|`false_belief`)

### `narrative_debt`
- `debt_kind` (`promise`|`mystery`|`foreshadow`|`tension`)
- `opened_in_scene`
- `resolution_state` (`open`|`advanced`|`resolved`)

## 5. Scene packet minimum

For each committed scene, packet must include:

- `scene_id`
- `events[]`
- `facts_introduced[]`
- `facts_changed[]`
- `debts_opened[]`
- `debts_advanced[]`
- `debts_resolved[]`

## 6. Retrieval envelope minimum

Query responses must include:

- typed records
- per-record provenance (`source_ref`, `provenance_kind`)
- temporal context (`updated_at`, optional scene ordering)

## 7. Non-goals (v1)

- complete relationship graph modeling
- automatic contradiction resolution
- multi-book chronology normalization

## 8. Acceptance

Schema is accepted when one end-to-end packet can be ingested, reflected in ledgers, and retrieved with provenance without fallback to untyped blobs.
