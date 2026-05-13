---
title: Default Change Loop V1 Slice 0 Routing Policy Probe
date: 2026-05-13
author: codex-wiki-docs
status: proposed
request_id: WIKI-DOCS
github_issue: 838
wiki_source: pages/plans/default-change-loop-v1-slice-0-routing-policy-probe.md
scope: design-only; no runtime code in this branch
builds_on:
  - PLAN.md#scoping-rules
  - PLAN.md#work-targets-and-review-gates
  - PLAN.md#harness-and-coordination
  - docs/exec-plans/active/2026-04-30-live-community-reiteration-loop.md
---

# Default Change Loop V1 Slice 0 Routing Policy Probe

## Classification

Issue #838 is a docs/ops filing with project-design implications. The source
wiki page was not present in this checkout or in an accessible GitHub wiki at
review time, so this note preserves only the safe routing-policy probe implied
by the page path and issue metadata. It does not claim the missing page's full
intent.

## Recommendation

Treat Slice 0 as an observation probe for the default community change loop's
routing policy, not as a runtime scheduler change.

The probe should answer one question before implementation work starts:

> Given a public daemon request, does the current loop route it to the correct
> lane, writer pool, checker family, and gate contract without inventing a
> private queue?

For this request, the expected route is:

- Request class: docs/ops, with design-note treatment if the missing source
  page proves architectural.
- Writer pool: Claude or Codex only for code-changing branches.
- Checker: opposite-family review for machine-authored code changes.
- Payment: volunteer claim is allowed unless a later bounty adds settlement
  terms through the gate ladder.
- Runtime posture: no `workflow/*` code changes until the probe identifies a
  concrete failed route or missing enforcement point.

## Probe Contract

The probe should collect a small evidence record rather than mutate routing:

```yaml
request:
  github_issue: 838
  wiki_source: pages/plans/default-change-loop-v1-slice-0-routing-policy-probe.md
observed_labels:
  - daemon-request
  - payment:free-ok
  - writer-pool:claude-codex
  - checker:cross-family
  - gate-required
expected_lane: docs-ops-or-design-note
checks:
  - request kind matches issue labels and filing metadata
  - architectural shape routes to docs/design-notes/proposed before runtime code
  - code-change branches require opposite-family checker
  - bounty handling references gate ladder requirements
result: pass | fail | inconclusive
next_action: none | docs-fix | policy-test | runtime-fix
```

This record can live in the issue, an auto-fix PR body, or a future loop
observation artifact. It should not become a new canonical state store.

## Out Of Scope

- Adding a new MCP action.
- Redesigning `change_loop_v1` or any community-authored branch.
- Implementing claim-time gate enforcement ahead of the existing market/gate
  dependency.
- Changing bounty settlement semantics outside the gate ladder.
- Treating this note as proof that the missing wiki page was fully handled.

## Acceptance

Slice 0 is complete when a reviewer can inspect a request and see whether the
default loop's routing decision matched the public request contract. A pass is
documentation and evidence only. A fail should produce the smallest follow-up:
either a docs/runbook correction, a workflow policy test, or a runtime fix if
the route is proven wrong in code.

## Verification

This is a documentation-only proposal. Verification for this branch is limited
to checking that the note preserves the source metadata, stays design-only, and
does not change runtime files.
