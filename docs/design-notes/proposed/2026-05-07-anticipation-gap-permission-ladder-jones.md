---
title: Anticipation Gap And Permission Ladder
date: 2026-05-07
author: codex-wiki-docs
status: proposed
request_id: WIKI-DOCS
github_issue: 582
wiki_source: pages/concepts/anticipation-gap-and-permission-ladder-jones-2026-05-07.md
scope: design-only; no runtime code in this branch
review_gate: opposite-family review required before implementation
builds_on:
  - PLAN.md#scoping-rules
  - docs/design-notes/2026-05-01-mcp-host-customer-matrix.md
  - docs/specs/2026-05-04-loop-autonomy-roadmap.md
---

# Anticipation Gap And Permission Ladder

## 1. Recommendation Summary

Treat the wiki page as a project-design concept, not a mechanical docs-only
artifact. It translates Nate B. Jones's consumer-agent framing into Workflow's
existing design vocabulary: proactive agents need an authority ladder, intent
history, and acceptance scenarios before they can reduce user management load.

Do not add a new MCP action or platform primitive from this page alone. Fold
the permission ladder into existing scope-decoration and action-confirmation
work as an action-level authority model. Capture acceptance scenarios and
intent history first as community-composable patterns over existing primitives;
only promote a platform primitive if implementation proves a structural gap
that cannot be composed from `State`, `Trigger`, `Run`, `Edge`, `Node`, and
`Scope`.

## 2. Filing Classification

The GitHub issue was filed as `docs-ops` because the wiki path is under
`pages/concepts/`. The content is architectural: it discusses permission
semantics, proactive triggers, per-user intent memory, acceptance tests, and
how PR-064 / PR-065 should refine scope decoration. For handling purposes,
this branch should be design-only and should not make runtime changes.

## 3. Design Shape

### Permission Ladder Is Authority, Not Transport Scope

Workflow's current scope-decoration direction separates who may call a tool by
operator shape, such as chatbot, directory-submission, or daemon-local. Jones's
five-step ladder is a different axis: what level of authority the user has
granted for a specific action.

Proposed authority levels:

| Level | Meaning | Workflow composition |
|---|---|---|
| read | Agent may inspect bounded context | Existing scope and read-only actions |
| suggest | Agent may surface a timely recommendation | Trigger + State + user-facing note |
| draft | Agent may prepare a change for review | Node/branch draft, wiki draft, or patch proposal |
| confirm-act | Agent may execute after explicit confirmation | Existing approval gate plus Run |
| autonomous | Agent may execute within pre-granted bounds | Daemon-local policy plus audit trail |

This should be expressed as metadata on actions, ladders, or branch gates, not
as five new tools. The chatbot should be able to explain "I can suggest this,
but I need confirmation before acting" from the same model that enforces the
boundary.

### Acceptance Scenarios Stay Community-Composable First

The "test suite for life admin" maps well to Workflow's community-build rule.
An acceptance scenario pack can be a published bundle that includes:

- expected user-visible outcome as `State`;
- trigger points where verification should run;
- one or more `Run` steps;
- edges from scenario steps to criteria;
- node records for scenario definition and result;
- scope limits for whose data, branch, or identity the scenario may touch.

This is valuable, but it does not yet prove a new platform primitive. The first
implementation should be a documented composition pattern and remixable wiki
artifact. A primitive becomes justified only if scenario execution cannot be
made reliable without engine-owned scheduling, provenance, or result semantics.

### Intent History Is Scoped User State

The Hawaii-swimsuit example in the wiki page is an intent ambiguity problem:
the same user instruction can imply different actions depending on seriousness,
past commitments, calendar density, and tolerance for intervention.

Model this initially as scoped user state, not a commons brain page. The public
commons can hold patterns for intent-history schemas, but private intent traces
must live in the user's host scope under the commons-first rule. Any future
platform support should enforce storage placement and access boundaries rather
than centralize private behavioral history.

### Proactive Triggers Need Quiet Failure Semantics

The "anticipation gap" is not closed by sending more notifications. A proactive
trigger must know when to ask, when to draft quietly, and when to stay silent.
That implies every proactive design should declare:

- what signal made the timing relevant;
- what authority level allows the next step;
- what evidence would make the agent stand down;
- how often the agent may retry or re-surface the suggestion;
- where the user can inspect or revoke the permission.

These are policy and UX requirements layered over existing primitives. They do
not require a new public MCP action in v1.

## 4. Scoping Rule Check

| Rule | Result |
|---|---|
| Minimal primitives | Pass only if ladder levels are metadata over existing actions, not new actions |
| Community-build over platform-build | Acceptance scenarios and intent-history schemas start as remixable patterns |
| Privacy via community composition | Intent history stays user-scoped; public docs describe patterns only |
| Commons-first architecture | Public concept pages are commons; private behavioral data remains host-local |
| User capability axis | Browser-only users can suggest/draft/confirm; local-app daemons can run bounded autonomous work |

## 5. Implementation Guidance

1. PR-064 / PR-065 should separate transport scope from authority level in
   naming and examples.
2. Any acceptance-scenario work should start with a wiki composition template
   and one focused proof branch before proposing platform storage changes.
3. Any intent-history work should state where private traces live and how a
   browser-only user can revoke or inspect them.
4. Proactive-trigger work must include anti-spam, stand-down, and revocation
   semantics before it reaches a public surface.
5. No implementation should proceed from this external-source synthesis until
   an opposite-family reviewer re-checks the source and Workflow context.

## 6. Open Questions

1. Should authority level live on branch gates, action descriptors, or a shared
   policy object referenced by both?
2. What is the smallest acceptance-scenario template that a chatbot can compose
   reliably without new runtime support?
3. Can intent history be represented as ordinary scoped `State`, or does it
   need retention, decay, and provenance semantics that justify engine support?
4. What rendered chatbot wording makes the permission boundary clear without
   exposing platform-internal vocabulary?

## References

- Wiki source:
  `pages/concepts/anticipation-gap-and-permission-ladder-jones-2026-05-07.md`
- Nate B. Jones, "Consumer AI Has a Problem Nobody's Naming" (referenced by
  the wiki page)
- `PLAN.md` Scoping Rules
- `docs/design-notes/2026-05-01-mcp-host-customer-matrix.md`
- `docs/specs/2026-05-04-loop-autonomy-roadmap.md`
