---
title: Layer-3 substrate design session — pre-reads
date: 2026-04-23
author: navigator
status: active
status_detail: DRAFT — companion to agenda doc
companion: docs/design-notes/2026-04-23-layer-3-design-session-agenda.md
---

# Layer-3 design session — pre-reads

Companion to the agenda. Read before the session so in-session time is
spent deciding, not briefing.

## Context (2 paragraphs)

**What Layer-3 is.** Per strategic-synthesis Pillar 3: cross-universe
structured records — bugs, feature requests, goals, published branches,
gate events, attestations. NOT narrative. Typed records with
server-owned IDs and explicit lifecycle. Database-shaped, not
wiki-shaped.

**Why it's load-bearing now.** Three converging signals: (1) the
wiki-as-Layer-3 plumbing has started failing (BUG-023 zero-body, BUG-028
slug-case duplication, no delete-page surface, 15K read-cap on plan
pages); (2) multi-user concurrent writes are coming (strategic synthesis
targets thousands of DAU, current wiki concurrent-write story is
unwritten); (3) host-independence requires a substrate where non-host
users can claim+update records autonomously. All three point at the
same decision. Getting Layer-3 right IS getting host-independence right.

## D1 — Storage backend

| Option | Pros | Cons |
|---|---|---|
| **Postgres + OAuth + server-owned IDs** | Boring; well-understood; clean concurrent-write; migrates to multi-region cleanly; decades of ops wisdom; OAuth composes with existing `UNIVERSE_SERVER_AUTH=true`. | New ops surface (another container); schema migrations to design; auth-layer decision attached. |
| **Harden current SQLite + wiki-federation** | Reuses existing substrate; lower ops burden; aligns with SqliteSaver-only hard rule. | Concurrent-write story weak; federation story unwritten; slug-case bugs suggest wiki-as-storage framing already breaking. |
| **Git-repo-as-Layer-3** | Free federation (GitHub); free auth; free audit log; free sync; aligns with Layer-4 pattern. | Real-time queries hard; indexing is a chore; commit latency; contributor-churn footprint. |

Navigator's lean: Postgres. Reasoning: concurrent-write + clean
migration path + OAuth reuse. SQLite-federation lacks the concurrent
story; Git-repo-as-Layer-3 is an interesting idea but latency-unfriendly
for interactive tools.

## D2 — Records in-scope at MVP

**Mandatory (already exercised in wiki today — direct migrations):**

- Bugs (28 filed so far)
- Goals (first-class on the Goals layer)
- Branches (published-version records; content-addressed)
- Gate events (per strategic-synthesis Pillar 2)
- Attestations (tied to gate events)
- Filed feature-requests (parallel to bugs)

**Proposed-new (not in wiki today):**

- Incident records: typed class for P0-shape incidents. Fields:
  incident_id, started_at, component, severity, paged_humans,
  mitigation_status, postmortem_link, closed_at. Navigator-finding per
  synthesis (c) — today's incident state is splattered across
  `docs/audits/` + activity.log + STATUS.md Concerns, a Layer-2
  accident for a Layer-3 need.

**Deferred candidates:**

- User profiles (Layer-1 territory?)
- Subscriptions (Layer-3 if cross-user, Layer-1 if per-user)
- Moderation events (Layer-3 once moderation is first-class)

## D3 — Layer-1 substrate (personal memory)

Strategic-synthesis names Layer-1 as "personal context, per-user,
private" — Open Brain shape: DB + vector + MCP. Every chatbot session
for a user reads from the same persistent context.

**Today's state.** Project memory lives in `.claude/agent-memory/<agent>/`
on host disk — NOT host-independent, NOT per-user-of-the-platform.
It's effectively agent-per-session memory with no cross-session story
for end-users.

**Arguments for Layer-1 alongside Layer-3:**

- Shared auth surface if D1 is Postgres+OAuth — marginal extra cost.
- Chatbot-builder-behaviors already assumes per-user persistent memory
  across sessions.
- Personal memory is the foundation of Pillar 1 (Goals coordination
  feels different when chatbots have per-user context).

**Arguments for deferred:**

- Smaller scope; ship Layer-3 first; add Layer-1 when real users exist.
- Per-user memory privacy model needs its own design pass.

Navigator's lean: decide alongside-ness in-session, but the privacy
story for Layer-1 is a standalone design note even if the backend is
decided now.

## D4 — Durability primitive vehicle (BUG-011)

Durability isn't a nice-to-have. Per synthesis: "A run from today may
be cited by a gate event two years from now." Content-addressed
`branch_version_id` is load-bearing for attribution survival across
long time horizons.

| Option | Shape | Cost |
|---|---|---|
| **Extended LangGraph checkpointer** | Stay with SqliteSaver; tighten contract; expose resume_run verb. | Low. Works today. Doesn't scale to thousands of concurrent runs. |
| **Temporal** | Industry-standard durable-execution framework. OpenAI-Codex-shape. | High ops cost. Steep learning curve. Solves the problem fully. |
| **Postgres + event-sourcing** | If D1 is Postgres, reuse for run-event stream. Runs are tables; resume is event-replay. | Medium. Scales with D1. Tightly coupled. |

Shape depends on D1 directly. If D1 = Postgres: Postgres+event-sourcing
is the natural pick. If D1 = SQLite-federation: extended-checkpointer is
the natural pick. Temporal is "real production" but heavy for current
scale.

## Corroborating evidence (BUG-028 + BUG-023 + synthesis (c))

Two recent bugs directly corroborate that the wiki-as-Layer-3 framing is
failing:

- **BUG-023 zero-byte body** — a P0-critical disk-full incident bug with
  no content until navigator re-authored on 2026-04-23. Wiki storage
  produced silent data loss.
- **BUG-028 slug-case mismatch** — `file_bug` (uppercase) and `write`
  (lowercase) can never target the same path; two-paths-for-the-same-
  record is a wiki-shape problem that typed-records-with-server-IDs
  eliminates by construction.

Synthesis (c) formalizes the broader argument: Layer-3 IS the
host-independence decision. Postgres+OAuth makes non-host claim/update
autonomous by default. Every other backend choice has to engineer
host-independence as an add-on.

## Questions navigator can't answer offline

1. Does host want OAuth at Layer-3 or a simpler token model at MVP?
2. Is incident-record class genuinely new-scope, or should it piggyback
   on the bugs class with a `kind=incident` discriminator?
3. Layer-1 per-user privacy model: does the platform own encryption, or
   does it trust the OAuth provider's scope boundaries?

These are the decisions that need host voice in-session.
