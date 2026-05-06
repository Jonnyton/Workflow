---
title: Brain architecture synthesis
status: proposed
date: 2026-05-06
request_id: WIKI-DESIGN
github_issue: 485
wiki_path: pages/patch-requests/pr-048-brain-architecture-synthesis-consolidate-scattered-modules-i.md
classification: project-design
---

# Brain Architecture Synthesis

## Context

Issue #485 asks whether Workflow should consolidate scattered brain-adjacent
modules into one `workflow/brain/` package with three implementations sharing
one core, synthesizing the OB1/Open Brain substrate direction with the
Karpathy LLM Wiki pattern.

The referenced wiki page is not present in this checkout, so this proposal is
grounded in the issue body, `PLAN.md`, and current local code. The local code
already has a useful split:

- `workflow/daemon_brain.py`: daemon-scoped atomic memory entries, FTS search,
  optional vector hits, promotion states, and observable memory events.
- `workflow/daemon_wiki.py`: host-local daemon wiki using the LLM-wiki pattern:
  raw immutable signals, maintained markdown synthesis pages, schema rules,
  claim proofs, soul versions, and review pages.
- `workflow/daemon_memory.py`: bounded prompt packet governor that composes
  soul capsule, curated wiki pages, and top-k mini-brain hits.
- `workflow/memory/`, `workflow/retrieval/`, and `workflow/knowledge/`: older
  workflow/runtime memory, scoped retrieval, and knowledge graph surfaces.

`PLAN.md` already says flat root modules that cross about 500 LOC or overlap a
sibling responsibility should become subpackages. The current brain-adjacent
modules meet both conditions. The consolidation is architecturally valid, but
it should be a staged package migration, not a runtime rewrite.

## Decision

Adopt `workflow/brain/` as the target package for durable, inspectable
machine memory. The package should own one shared core and three concrete
implementations:

1. **Daemon brain**: private, soul-bearing daemon memory.
   Migrates the current `daemon_brain.py`, `daemon_wiki.py`, and
   `daemon_memory.py` behavior behind compatibility wrappers. It stays
   host-local by default and remains keyed by `daemon_id`.
2. **Workflow brain**: per-workflow and per-branch execution memory.
   Gradually folds the relevant parts of `workflow/memory/`,
   `workflow/retrieval/`, and `workflow/knowledge/` into the shared core while
   preserving existing `MemoryScope` isolation.
3. **Commons brain**: public or semi-public project/wiki synthesis memory.
   Covers community patch requests, design notes, wiki pages, review verdicts,
   and convergence artifacts. It must respect moderation and publication rules
   rather than inheriting daemon-private visibility.

The shared core should define the nouns and invariants all three
implementations use:

- `BrainEntry`: atomic standalone memory item with content fingerprint,
  source identity, reliability, temporal bounds, language type, confidence,
  importance, sensitivity tier, visibility, promotion state, and supersession.
- `BrainSource`: raw episode, wiki page, design note, node/gate event, review
  verdict, host note, or imported artifact.
- `BrainEvent`: query, retrieve, inject, write candidate, accept, reject,
  promote, supersede, compact, low-confidence skip, and eval.
- `BrainScope`: isolation key. At minimum daemon, universe, goal, branch, user,
  node, and commons visibility are explicit fields rather than implied by file
  paths.
- `BrainPacket`: bounded prompt context with trace IDs and selected/rejected
  entry evidence.
- `BrainStore` protocol: capture, search, list, review, promote, supersede,
  status, and build packet. This is not an MCP tool surface; it is an internal
  engine interface.

The package should keep the OB1-style substrate lesson and the LLM-wiki lesson
separate:

- OB1-style substrate: typed atomic entries, dedupe, search, metadata,
  promotion workflow, and observability.
- LLM-wiki pattern: immutable raw inputs, maintained markdown synthesis,
  cross-linked pages, and schema instructions that teach future agents how to
  maintain the wiki.

Neither replaces the other. The atomic store is the searchable substrate; the
wiki is the curated human-readable face; the packet builder is the bounded
runtime read policy.

## Target Layout

```text
workflow/brain/
  __init__.py
  core.py              # dataclasses, enums, protocols, validation helpers
  ids.py               # fingerprints, trace IDs, source hashes
  packets.py           # bounded packet assembly primitives
  events.py            # observable memory event recording contract
  sqlite_store.py      # shared SQLite/FTS implementation pieces
  vector_index.py      # adapter over existing LanceDB/vector path
  wiki.py              # markdown wiki adapter and safe path rules
  daemon.py            # daemon-private implementation
  workflow.py          # universe/goal/branch/user/node implementation
  commons.py           # public/wiki/project implementation
```

Compatibility wrappers can keep existing imports stable during migration:

- `workflow.daemon_brain` imports from `workflow.brain.daemon`.
- `workflow.daemon_wiki` imports from `workflow.brain.wiki` plus daemon
  defaults.
- `workflow.daemon_memory` imports from `workflow.brain.daemon` packet policy.

The wrappers should be retired only after API callers, tests, and plugin
runtime mirrors have moved.

## Migration Plan

1. **Design only, now.** Land this proposal under `docs/design-notes/proposed/`
   without runtime changes.
2. **Introduce core types without behavior changes.** Add `workflow/brain/core.py`
   and tests that map current daemon entry/event dictionaries to typed core
   objects and back.
3. **Move daemon internals behind wrappers.** Move code in file-sized slices:
   store/schema first, search/list next, packet builder next, wiki promotion
   last. Preserve public function names until all callers are migrated.
4. **Fold workflow memory by adapter, not bulk move.** Add a `WorkflowBrain`
   adapter that delegates to current `MemoryManager`, `ScopedMemoryRouter`,
   retrieval router, vector store, and knowledge graph. Only then migrate
   internals as tests prove equivalent behavior.
5. **Add commons brain after moderation boundaries are explicit.** The commons
   implementation must not reuse daemon-private defaults. It needs public
   visibility rules, source attribution, stale-claim handling, and review
   gates before capture/promote actions are available.
6. **Update PLAN.md only after acceptance.** If this proposal is accepted,
   update the module layout target shape to list `workflow/brain/` and its
   relationship to `workflow/memory/`, `workflow/retrieval/`, and
   `workflow/knowledge/`.

## Non-Goals

- No new MCP actions in this proposal.
- No immediate move of runtime code.
- No new hosted dependency, service, or external database.
- No cross-daemon search by default.
- No publication of host-private daemon wiki content.
- No replacement of the public project wiki with daemon-private memory.

## Acceptance Gates For Implementation

Any future implementation must pass these gates before runtime migration is
considered complete:

- Existing daemon brain, daemon wiki, daemon memory, memory scope, retrieval,
  and knowledge graph tests remain green.
- Plugin mirror is rebuilt if canonical `workflow/*` runtime files move.
- A compatibility test proves existing imports from `workflow.daemon_brain`,
  `workflow.daemon_wiki`, and `workflow.daemon_memory` still work during the
  migration window.
- Scope tests prove daemon-private, workflow-private, user-private, and commons
  visibility do not leak across implementations.
- Packet tests prove selected and rejected memory entries are traceable by ID.
- Eval tests prove memory can be compared against a baseline and logged as
  improved, unchanged, or regressed.
- For public MCP behavior, final acceptance still requires rendered chatbot
  verification through the live connector; direct internal tests are
  supporting evidence only.

## Open Questions

- Should `workflow/memory/` remain as a lower-level runtime package after
  `WorkflowBrain` exists, or should it eventually become
  `workflow/brain/workflow_memory/`?
- Is commons memory public by default, publish-by-promotion, or split into
  private moderation queue plus public synthesis pages?
- What is the minimum typed `BrainScope` that can cover current
  `MemoryScope` without forcing the Stage 2c flag early?
- Which existing API cluster should expose future brain status, if any:
  daemon operations, runtime operations, commons, or a mounted brain API after
  primitive consolidation?

## Recommendation

Accept `workflow/brain/` as the target package, but defer code movement until a
dedicated migration lane can claim the runtime files and opposite-family review
capacity is available. The smallest useful next build step is core types plus
compatibility tests, not a broad module move.

