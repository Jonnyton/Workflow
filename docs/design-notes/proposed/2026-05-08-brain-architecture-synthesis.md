---
title: Brain Architecture Synthesis
date: 2026-05-08
author: codex-wiki-design
status: proposed
request_id: WIKI-DESIGN
github_issue: 485
wiki_source: pages/patch-requests/pr-048-brain-architecture-synthesis-consolidate-scattered-modules-i.md
scope: design-only; no runtime code in this branch
builds_on:
  - PLAN.md#retrieval-and-memory
  - PLAN.md#module-layout-target-shape
  - docs/design-notes/2026-05-02-daemon-mini-openbrain.md
  - docs/design-notes/2026-05-04-operating-model-and-four-agent-topology.md
  - docs/design-notes/2026-04-18-full-platform-architecture.md#32-node-autoresearch-optimization
---

# Brain Architecture Synthesis

## 1. Recommendation Summary

Create one `workflow/brain/` package as the named interface layer for
Workflow's brain substrate. The first slice should be a protocol and adapter
extraction only: no table moves, no prompt behavior change, no MCP action
renames, and no direct dependency on OB1. The package should expose one shared
core contract and three implementations:

- `DaemonBrain`: private per-soul memory and wiki, initially backed by the
  landed `workflow/daemon_brain.py`, `workflow/daemon_memory.py`, and
  `workflow/daemon_wiki.py` behavior.
- `ChatbotBrain`: private per-user memory for chatbot continuity, preference
  recall, and user-facing summaries.
- `CollectiveBrain`: shared commons memory for loop learning, public wiki
  knowledge, patch-request patterns, and cross-agent substrate lessons.

This consolidates the concept without pretending the existing substrate is
missing. The codebase already has substantial brain pieces:
`workflow/memory/`, `workflow/knowledge/`, `workflow/retrieval/`,
`workflow/learning/`, `workflow/ingestion/`, `workflow/storage/`,
`workflow/wiki/`, `workflow/daemon_brain.py`, `workflow/daemon_memory.py`,
`workflow/daemon_wiki.py`, `workflow/identity.py`, and
`workflow/subscriptions.py`. The missing piece is the public internal boundary
that says which operations all brain implementations share and where privacy
scope is enforced.

## 2. Classification

This request is a project-design filing, not a bug or runtime patch. The
smallest useful project change is this proposed design note. Runtime work
should follow only after opposite-family review accepts the package boundary.

## 3. Design Sources

The synthesis combines two external patterns with Workflow's existing design:

- OB1-like substrate: durable memory, importers, structured metadata, vector
  search, dashboards, and extension points.
- Karpathy LLM Wiki pattern: raw sources, curated wiki pages, schema/indexes,
  and repeated ingest/query/lint maintenance by an LLM.
- Workflow's current topology: wiki plus open brain as shared cognition,
  chatbots as user-facing edges, daemons as workers, and the loop as the body
  that turns learned patterns into patches.

The important translation is not "copy OB1" or "copy a wiki repo." Workflow
needs one small internal interface that lets the same improvements compound
across daemon-private, chatbot-private, and collective-public brains while
keeping their scopes separate.

## 4. Core Contract

`workflow/brain/core.py` should define the shared nouns and operation protocol.
These are internal Python contracts first, not new MCP actions.

Core nouns:

- `BrainSource`: immutable source material or event reference.
- `BrainPage`: curated human-readable wiki/page artifact.
- `BrainEntry`: atomic searchable memory item derived from source.
- `BrainIndex`: acceleration structure such as FTS, vector, graph, or summary.
- `BrainSchema`: validation and lifecycle rules for entries and pages.
- `BrainScope`: privacy and visibility boundary.
- `BrainLifecycleState`: candidate, active, promoted, rejected, superseded, or
  archived.

Core operations:

- `ingest(source) -> IngestResult`
- `query(question, scope, limits) -> QueryResult`
- `lint(scope) -> LintReport`
- `digest(window, scope) -> DigestSummary`
- `subscribe(topic, identity, scope) -> SubscriptionHandle`
- `import_source(connector, params, scope) -> ImportResult`
- `promote(entry_or_page, target_scope) -> PromotionResult`

The operation names are intentionally generic because they are substrate
operations, not user-facing action names. If any operation later becomes an
MCP primitive, it must pass the normal primitive-collision and chatbot-vocab
checks before surfacing.

## 5. Three Implementations, One Core

### DaemonBrain

`DaemonBrain` owns soul-scoped memory. It should start as an adapter around the
landed daemon mini-brain and wiki system:

- `workflow/daemon_brain.py`: SQLite entries, FTS, optional vector indexing,
  review, promotion, supersession, quality evals, and observability status.
- `workflow/daemon_memory.py`: bounded prompt packet composition and memory
  pressure handling.
- `workflow/daemon_wiki.py`: LLM-wiki scaffold, curated pages, and read
  context.

The adapter should not move data in v1. Its job is to prove the protocol
against real code and make daemon memory one implementation of the shared
brain contract.

### ChatbotBrain

`ChatbotBrain` owns user-scoped continuity. It should enforce user identity and
privacy boundaries before storage or retrieval. Its first useful responsibilities
are preference recall, request history summaries, transparent privacy reasoning,
and "what changed since last time" digests for chatbot surfaces.

This implementation must not read daemon-private entries by default. Promotion
from chatbot-private memory to the collective brain is explicit, cited, and
user-mediated.

### CollectiveBrain

`CollectiveBrain` owns the public commons: wiki pages, patch-request lessons,
loop failure patterns, accepted design notes, and substrate-level knowledge
that all agents may read. It should compose existing wiki, retrieval, knowledge,
learning, ingestion, and storage modules behind the same core contract.

This is where Karpathy-style wiki maintenance matters most: raw evidence stays
auditable, curated pages stay readable, indexes accelerate lookup, and linting
keeps stale or contradictory claims from silently becoming "truth."

## 6. Package Shape

Recommended first package layout:

```text
workflow/brain/
  __init__.py
  core.py              # Protocols, dataclasses, enums, result shapes
  scopes.py            # BrainScope helpers and visibility checks
  daemon.py            # Adapter over existing daemon brain/wiki modules
  chatbot.py           # Stub adapter with explicit NotImplemented boundaries
  collective.py        # Stub adapter over wiki/retrieval/knowledge modules
```

Follow-up modules should be added only when a real implementation needs them.
Avoid a large framework package that merely renames existing subsystems.

## 7. Invariants

- Scope is enforced at the implementation boundary, not left to callers.
- Raw sources are immutable or content-addressed; derived entries cite them.
- Curated wiki/page artifacts are promoted from evidence, not raw capture dumps.
- Indexes are accelerators, never the source of truth.
- Prompt packets stay bounded; no full-brain prompt preload.
- Low-confidence retrieval injects nothing rather than polluting context.
- Cross-brain promotion is explicit, cited, and observable.
- Private daemon or chatbot memories do not leak into the collective brain by
  default.
- OB1 is a design influence, not a runtime dependency.

## 8. Migration Sequence

1. Add `workflow/brain/core.py` and `workflow/brain/daemon.py` only. Wire no
   production caller. Tests instantiate the adapter against temporary daemon
   brain/wiki fixtures and prove parity with the existing daemon behavior.
2. Move new daemon-brain call sites to the adapter when they are touched for
   real product work. Do not churn stable call sites just to complete a rename.
3. Add `ChatbotBrain` once user-scoped memory has a concrete caller, such as
   preference recall or wake-up summaries.
4. Add `CollectiveBrain` once loop learning or wiki linting needs a shared
   query/lint/digest interface across wiki, retrieval, and knowledge modules.
5. Only after all three implementations are real, consider moving existing
   daemon files under `workflow/brain/`. Until then, adapters are cheaper and
   safer than filesystem churn.

## 9. Non-Goals

- No runtime code changes in this design branch.
- No database migration in the first implementation slice.
- No MCP action rename or new user-facing primitive in the first slice.
- No one global memory pool.
- No direct OB1, Supabase, or OpenRouter dependency.
- No broad refactor of `workflow/memory/`, `workflow/knowledge/`,
  `workflow/retrieval/`, or `workflow/ingestion/` without a concrete caller.

## 10. Review Gate

Because this is architecture-level consolidation, implementation should wait
for opposite-family review. The review should answer:

- Does `workflow/brain/` fit PLAN.md's target module layout better than leaving
  daemon/chatbot/collective memory as unrelated modules?
- Are the three implementations the right domain split?
- Is the v1 adapter-only sequence small enough to avoid destabilizing uptime
  surfaces?
- Are any operation names likely to collide with existing or planned MCP
  primitives if later surfaced?

Acceptance should authorize only the v1 adapter/protocol slice. Broader file
moves need a separate patch request or follow-up design note.
