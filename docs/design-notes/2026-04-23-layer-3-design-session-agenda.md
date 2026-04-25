---
title: Layer-3 substrate design session — agenda
date: 2026-04-23
author: navigator
status: DRAFT — awaits host scheduling
attendees: host, team-lead, navigator
target: half-day session, 4 decisions shipped, 1 design-note commit
pre-read: docs/design-notes/2026-04-23-layer-3-design-session-prereads.md
---

# Layer-3 substrate design session — agenda

Half-day. Four decisions. One design-note commit as output. No code
in-session; code lands after.

## Why now

Layer-3 (cross-universe typed records — bugs, goals, branches, gate
events, attestations, incident records) is wiki-plumbed today and
cracking: BUG-023 zero-body, BUG-028 slug-case duplication, concurrent-
write safety unclear, 15K read-cap, no typed lifecycle. Per synthesis
(c) this is also the load-bearing **host-independence** decision.

## Pre-read (distribute day-of)

Candidates + trade-off tables for D1-D4 live in
`docs/design-notes/2026-04-23-layer-3-design-session-prereads.md`.
Attendees read before walking in.

## Four decisions

### D1 — Storage backend

Postgres+OAuth OR harden-SQLite+wiki-federation OR Git-repo-as-Layer-3.
Postgres is favorite per synthesis. Land one backend + one-sentence
rationale.

### D2 — Records in-scope at MVP

Which record classes ship day one? Default mandatory: bugs, goals,
branches (published versions), gate events, attestations,
feature-requests. Decide: incident records in or out? Which deferred
classes named explicitly?

### D3 — Layer-1 substrate (personal memory)

Alongside-Layer-3 or deferred? Shares auth surface if D1 is
Postgres+OAuth. Foundation of Pillar 1. Open question. Decide
alongside/deferred + backend-shared/distinct.

### D4 — Durability primitive vehicle (BUG-011)

Extended LangGraph checkpointer vs Temporal vs Postgres+event-sourcing.
Shape depends on D1 — if D1 is Postgres, reuse; if SQLite-federation,
extended-checkpointer natural; Temporal is overkill for current scale.

## Session shape

| Time | Topic |
|------|-------|
| 0:00-0:30 | Framing — Layer-3 as host-independence substrate |
| 0:30-1:30 | D1 storage backend |
| 1:30-2:00 | D2 records in-scope |
| 2:00-2:45 | D3 Layer-1 substrate |
| 2:45-3:30 | D4 durability vehicle |
| 3:30-4:00 | Wrap — action items + design-note draft outline |

## Deliverable

Single design-note commit within 24h post-session:

1. Four named decisions (one paragraph each).
2. Migration plan shape (weeks estimate).
3. PLAN.md §Module Layout changes.
4. STATUS.md Work rows created.

## Parking lot (NOT decided in-session)

Schema migrations, auth-provider specific choice (Auth0/Keycloak/roll-
your-own), multi-region, detailed record schemas, Layer-4 DAO governance.

## Success criterion

Host leaves able to describe this project's Layer-3 architecture to an
OSS contributor in three sentences. If they can't, session failed.
