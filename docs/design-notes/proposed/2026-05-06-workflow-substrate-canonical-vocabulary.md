---
title: Workflow substrate canonical vocabulary - six concepts, five MCP handles, brain-evolved conventions
date: 2026-05-06
author: codex-wiki-design
status: proposed
source:
  - GitHub issue #449 WIKI-DESIGN
  - pages/concepts/pages-concepts-workflow-substrate-canonical-vocabulary-6-primitives-5-mcp-handles.md
classification: project-design
scope: documentation-only design proposal; no runtime implementation
companion:
  - docs/design-notes/2026-04-26-minimal-primitive-set-proposal.md
  - docs/design-notes/2026-04-26-engine-primitive-substrate.md
  - docs/design-notes/2026-05-02-daemon-mini-openbrain.md
  - docs/design-notes/2026-05-04-operating-model-and-four-agent-topology.md
  - PLAN.md
---

# Workflow substrate canonical vocabulary

## 1. Request classification

Issue #449 is a **project-design** request. It asks for canonical vocabulary, not code. The smallest safe change is therefore this proposed design note under `docs/design-notes/proposed/`, preserving the wiki concept while testing it against the existing PLAN.md scoping rules.

No runtime MCP action, API route, storage schema, or daemon behavior should change from this note alone.

## 2. Recommendation

Adopt the issue's frame as a vocabulary layer with one constraint:

1. **Six substrate concepts** are valid as the way Workflow talks about itself.
2. **Five MCP handles** remain the user-facing tool surface.
3. **Brain/convention evolution is not a sixth MCP handle.** It is a substrate capability composed through `commons`, daemon memory, and wiki review.

This reconciles the issue title with the active minimal-primitive direction. The extra concept is useful for architecture and contributor language, but adding a sixth public tool would violate the minimal-primitives rule unless later evidence proves `commons` cannot carry the interaction safely.

## 3. Canonical vocabulary

| Concept | User meaning | Engine meaning | Public MCP handle |
|---|---|---|---|
| **Workspace** | Where my work lives and what state it is in. | Universe/session scope, status, tier configuration, daemon control boundary. | `workspace` |
| **Workflow** | The reusable process I am designing, patching, forking, or extending. | Branch definitions, graph declarations, node registrations, versions, edges. | `workflow` |
| **Run** | Work being executed, observed, resumed, cancelled, or fetched. | Dispatch request, queue item, events, checkpoints, output retrieval. | `run` |
| **Evaluate** | Score, compare, gate, or judge work with typed evidence. | Evaluator interface, gate claims, result records, rubric execution. | `evaluate` |
| **Commons** | Shared public knowledge, goals, branches, wiki pages, bug reports, attribution, and remix material. | Catalog, wiki, goal pool, attribution, discovery, public collaboration records. | `commons` |
| **Brain** | The system's learned conventions, blocked patterns, operating memory, and reviewable lessons. | Daemon mini-brain entries, curated wiki pages, convention proposals, promotion/review flow. | No separate handle; composed through `commons` and daemon internals. |

The sixth concept is deliberately not another MCP handle. A chatbot should say "search the commons for the convention" or "file a convention proposal in the commons," not reach for a separate `brain` tool unless a later design proves a real irreducible gap.

## 4. Why six concepts but five handles

PLAN.md's scoping rules require every new tool to pass irreducibility and community-composition tests. `Brain` fails the public-tool irreducibility test today:

- searchable durable knowledge is already `commons`;
- daemon-local memory capture/search/review is already scoped by the mini OpenBrain proposal;
- project-level conventions belong in AGENTS.md, PLAN.md, STATUS.md, docs, wiki, and reviewed design notes;
- user-facing conversation does not improve if "brain" competes with "commons" as another place to read or write shared knowledge.

But `Brain` passes the vocabulary usefulness test. It names the learning loop that evolves conventions: raw observation -> candidate memory -> reviewed convention -> public commons or project rule. Without the word, contributors conflate durable conventions with transient chat memory or ad hoc wiki edits.

## 5. Brain-evolves-conventions contract

Conventions evolve through a reviewable path, not through hidden prompt drift:

1. **Capture:** a daemon, chatbot, contributor, or user records a repeated pattern, failure, or successful composition as a candidate lesson.
2. **Search before acting:** future agents retrieve relevant brain/wiki hits before repeating similar work.
3. **Review:** a human or opposite-family checker decides whether the lesson is real, stale, local to one harness, or project-wide.
4. **Promote:** accepted project-wide conventions move to AGENTS.md; architectural decisions move to PLAN.md; live coordination moves to STATUS.md; reusable user guidance moves to the wiki/commons.
5. **Retire:** contradicted or obsolete lessons are marked stale or removed from active retrieval so they stop steering work.

This keeps the brain observable and accountable. It should never become an unreviewed policy engine that silently overrides PLAN.md or AGENTS.md.

## 6. MCP handle shape

This note preserves the five public handles from the active primitive-set proposal:

```text
workspace  -> inspect, list, create, configure, control host-local daemon surfaces
workflow   -> build, patch, fork, version, register or inspect nodes/branches
run        -> submit, observe, list, cancel, resume, fetch outputs
evaluate   -> score, compare, gate, judge, record typed evidence
commons    -> search/read/write wiki, goals, public branches, attribution, reports, convention proposals
```

`Brain` composes through:

- `commons` for shared, reviewable knowledge and convention proposals;
- daemon mini-brain internals for bounded local memory capture/search/review;
- AGENTS.md/PLAN.md/STATUS.md when the convention graduates into project truth.

## 7. Non-goals

- Do not add a public `brain` MCP tool from this proposal.
- Do not rename existing runtime modules.
- Do not collapse the engine substrate's eight internal primitives into this six-word vocabulary. The six concepts are public architecture language; the eight substrate primitives remain implementation design.
- Do not auto-promote daemon memory into AGENTS.md, PLAN.md, or STATUS.md without review.

## 8. Open questions for lead/host review

1. Should `Brain` be capitalized as a canonical architecture concept, or should the project reserve lowercase "brain" for daemon-local memory only?
2. Should convention proposals live under `commons.wiki.*` initially, or should `commons` get a typed `conventions.*` action after the minimal-handle migration?
3. What is the first acceptance probe for "brain-evolves-conventions" working end-to-end: blocked-pattern recall, convention proposal review, or promotion into AGENTS.md?

## 9. Verification performed

- Read STATUS.md and relevant PLAN.md sections on 2026-05-06 in `/home/runner/work/Workflow/Workflow`.
- Compared against `docs/design-notes/2026-04-26-minimal-primitive-set-proposal.md`, `docs/design-notes/2026-04-26-engine-primitive-substrate.md`, and `docs/design-notes/2026-05-02-daemon-mini-openbrain.md`.
- Ran `scripts/check_primitive_exists.py` for `workspace`, `workflow`, `run`, `evaluate`, `commons`, and `brain` before drafting; all returned clean against `origin/main`.
