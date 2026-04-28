---
status: active
---

# Scene Commit Packet Spec

**Status:** Phase 1a — schema defined, not yet emitted  
**Module:** `fantasy_author/packets.py`  
**Date:** 2026-04-09

## Purpose

A ScenePacket is the structured output of a single scene commit cycle.
It captures everything the commit pipeline extracted — facts, promises,
editorial verdict, participants, world-state deltas — in a
machine-readable form that downstream consumers can query without
re-parsing prose.

This is the first layer of IR-first authoring (BettaFish Pattern A).

## Schema

### Identity

| Field | Type | Source |
|-------|------|--------|
| `scene_id` | `str` | `draft_output.scene_id` |
| `universe_id` | `str` | `state.universe_id` |

### Position

| Field | Type | Source |
|-------|------|--------|
| `book_number` | `int` | `state.book_number` |
| `chapter_number` | `int` | `state.chapter_number` |
| `scene_number` | `int` | `state.scene_number` |

### POV and Setting

| Field | Type | Source |
|-------|------|--------|
| `pov_character` | `str | None` | `orient_result.pov_character` |
| `location` | `str | None` | Extracted from facts (location entity) |
| `time_marker` | `str | None` | Extracted from facts (temporal refs) |

### Participants

| Field | Type | Source |
|-------|------|--------|
| `participants` | `list[str]` | Characters upserted during commit |

### Facts

| Field | Type | Source |
|-------|------|--------|
| `facts_introduced` | `list[FactRef]` | `extracted_facts` (new fact_ids) |
| `facts_changed` | `list[FactRef]` | Facts that supersede existing ones |

Each `FactRef` carries: `fact_id`, `text`, `source_type`, `confidence`, `importance`.

### Promises

| Field | Type | Source |
|-------|------|--------|
| `promises_opened` | `list[PromiseRef]` | `extracted_promises` (new) |
| `promises_advanced` | `list[PromiseRef]` | Promises with new evidence |
| `promises_resolved` | `list[PromiseRef]` | Promises marked resolved |

Each `PromiseRef` carries: `promise_type`, `trigger_text`, `context`, `scene_id`, `chapter_number`, `importance`.

### Deltas

| Field | Type | Source |
|-------|------|--------|
| `relationship_deltas` | `list[RelationshipDelta]` | KG edge changes |
| `world_state_deltas` | `list[WorldStateDelta]` | DB field changes |

### Editorial

| Field | Type | Source |
|-------|------|--------|
| `editorial` | `EditorialVerdict | None` | Commit verdict + structural evaluation |

`EditorialVerdict` carries: `verdict`, `structural_pass`, `structural_score`, `hard_failure`, `concerns`, `protect`.

### Metrics

| Field | Type | Source |
|-------|------|--------|
| `word_count` | `int` | `draft_output.word_count` |
| `is_revision` | `bool` | Whether this was a second-draft pass |

### Provenance

| Field | Type | Source |
|-------|------|--------|
| `draft_provider` | `str` | Provider used for drafting |
| `extraction_provider` | `str` | Provider used for fact extraction |

### Signals

| Field | Type | Source |
|-------|------|--------|
| `worldbuild_signals` | `list[dict]` | Signals generated for universe-level nodes |

## Constraints

- Only fields the current commit pipeline can reliably populate.
- No aspirational fields — if commit.py does not extract it today, it is not in the packet.
- Facts and promises reference back to the extraction pipeline's output types.
- The packet is serializable to JSON via `ScenePacket.to_dict()`.

## Storage

Packets are intended to be stored alongside prose output:

```
output/<universe>/scenes/<scene_id>/
  prose.md
  packet.json          # ScenePacket.to_dict()
  validation.json      # Future: validation results
```

## Next Steps

- **Phase 1b:** Emit packets from `commit.py` on accept verdict.
- **Phase 1c:** Add packet query surface to orient for prior-scene context.
