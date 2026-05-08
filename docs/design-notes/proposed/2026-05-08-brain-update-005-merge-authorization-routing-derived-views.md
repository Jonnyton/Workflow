---
title: BrainUpdate BU-005 Merge Authorization And Routing Anomaly Views
date: 2026-05-08
author: codex-wiki-docs
status: proposed
request_id: WIKI-DOCS
github_issue: 687
wiki_source: pages/concepts/brain-update-005-merge-authorization-state-routing-anomalies-derived-views.md
scope: design-only; no runtime code in this branch
builds_on:
  - PLAN.md#state-and-artifacts
  - PLAN.md#retrieval-and-memory
  - PLAN.md#multi-user-evolutionary-design
---

# BrainUpdate BU-005 Merge Authorization And Routing Anomaly Views

## 1. Classification

This is a project-design/docs-ops request, not a runtime bug. The issue asks
for two BrainUpdate derived views from explicit position records:
`MergeAuthorizationState` and `RoutingAnomalies`. The minimal useful change is
to capture the design contract as a proposed note so later implementation can
reuse the same vocabulary without adding hidden state or premature MCP actions.

## 2. Recommendation Summary

Add two read-model concepts to the BrainUpdate vocabulary:

- `MergeAuthorizationState`: answers whether a proposed merge has the required
  explicit reviewer, owner, bounty, and policy positions to proceed.
- `RoutingAnomalies`: answers whether daemon routing decisions disagree with
  explicit positions, declared constraints, or observed reviewer gates.

Both are derived views. Neither should become an authoritative write target.
The authoritative records remain explicit positions: who said what, about which
artifact or route, under which role, at which time, and with which evidence.

The core invariant is simple: if a view cannot be recomputed from position
records plus immutable issue/branch metadata, the view is carrying hidden
authority and should be rejected.

## 3. Source Records

A position record is the smallest durable assertion behind these views. It
should identify:

- `subject_kind`: issue, branch, pull request, wiki page, daemon request, merge
  candidate, route, bounty, or artifact.
- `subject_id`: the stable external id or repository path.
- `actor_id`: human, daemon, reviewer family, checker role, or policy system.
- `actor_role`: filer, writer, opposite-family checker, maintainer, bounty
  funder, host, or policy.
- `position_kind`: authorization, rejection, review requirement, route
  preference, route block, bounty condition, merge readiness, or anomaly
  observation.
- `position_value`: approved, rejected, required, blocked, preferred, observed,
  superseded, or withdrawn.
- `evidence`: issue comment, review, CI run, test artifact, wiki page, policy
  document, or signed acceptance key.
- `recorded_at`: freshness timestamp for conflict resolution and audit.

The exact storage shape can be chosen later, but these fields are the minimum
needed for a deterministic derived view.

## 4. Derived View: MergeAuthorizationState

`MergeAuthorizationState` summarizes whether a merge candidate may proceed.
It should be recomputed by grouping explicit positions for a candidate and
then applying the current gate ladder.

Recommended fields:

- `candidate_id`: branch, pull request, wiki change, or patch request id.
- `required_positions`: explicit approvals, checks, host decisions, or bounty
  conditions still required.
- `satisfied_positions`: required positions with fresh matching evidence.
- `blocking_positions`: rejections, missing opposite-family checks, host
  decisions, failed gates, or unresolved policy conflicts.
- `stale_positions`: previously relevant positions whose evidence has expired
  or has been contradicted by newer state.
- `merge_state`: `not_ready`, `blocked`, `ready_for_review`, `ready_to_merge`,
  or `merged`.
- `why`: compact human-readable explanation generated from the source
  positions, not free-form hidden judgment.

The view must not grant merge authority by itself. It only explains whether the
recorded positions satisfy the policy that already governs the candidate.

## 5. Derived View: RoutingAnomalies

`RoutingAnomalies` summarizes routing decisions that appear inconsistent with
explicit positions or policy.

Recommended fields:

- `route_id`: issue dispatch, daemon claim, branch assignment, checker
  assignment, bounty routing, or escalation path.
- `expected_route`: route implied by explicit positions and current policy.
- `observed_route`: route actually taken by the daemon, workflow, or human
  dispatcher.
- `anomaly_kind`: missing gate, wrong provider family, stale claim, blocked
  file overlap, bounty mismatch, wiki-path mismatch, review-ladder mismatch, or
  freshness mismatch.
- `severity`: advisory, blocks_merge, blocks_dispatch, or host_decision.
- `source_positions`: position record ids that imply the expected route.
- `evidence`: dispatch log, issue comment, status row, CI artifact, or review
  note proving the observed route.
- `resolution_state`: open, acknowledged, superseded, fixed, or waived.

The view should support daemon self-correction and reviewer triage, but it
should not automatically rewrite claims, labels, branches, or wiki pages unless
a separate approved primitive does that work.

## 6. Composition With Existing Plan

`PLAN.md` State And Artifacts already requires long-horizon reasoning to be
legible and durable through explicit typed state. These views fit that model
because they are recomputable summaries over position records.

`PLAN.md` Retrieval And Memory frames routing policy as more important than any
single backend. `RoutingAnomalies` belongs in that policy layer: it tells the
daemon when retrieval, memory, or queue evidence points to a route different
from the route that actually happened.

`PLAN.md` Multi-User Evolutionary Design makes shared branches, goals, and
review gates first-class. `MergeAuthorizationState` is the inspectable gate
state for that ecology; it keeps merge readiness from becoming an implicit
chat-memory judgment.

## 7. Non-Goals

- No new MCP action is proposed here.
- No runtime schema migration is proposed here.
- No automatic merge, dispatch, relabel, or wiki rewrite behavior is proposed
  here.
- No replacement for existing reviewer, host, or bounty authority is proposed
  here.

## 8. Open Questions

1. Should position records live in the daemon wiki, repository artifacts, the
   future shared state database, or a bridge that can project into all three?

2. What is the canonical actor vocabulary for reviewer families and checker
   roles? The view needs stable role ids, not session-specific names.

3. Which freshness rules should expire positions automatically, and which
   should remain valid until explicitly superseded?

4. Should waivers be ordinary position records, or should they have a separate
   higher-friction authority shape?

## References

- `PLAN.md` State And Artifacts
- `PLAN.md` Retrieval And Memory
- `PLAN.md` Multi-User Evolutionary Design
- Wiki source:
  `pages/concepts/brain-update-005-merge-authorization-state-routing-anomalies-derived-views.md`
