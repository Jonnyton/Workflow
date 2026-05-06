---
title: PR-040 privacy-mode selection - community composition, not a platform primitive
date: 2026-05-06
status: proposed
type: design-note
source:
  - Issue #442
  - pages/patch-requests/pr-040-workflow-privacy-mode-primitive-design-time-selection-of-sha.md
classification: project-design
---

# PR-040 privacy-mode selection

## Decision

Do not add a new Workflow privacy-mode primitive for design-time selection of
shape visibility, data residency, or compliance templates.

PR-040 is a valid user need, but current project doctrine classifies this as a
community-composed privacy pattern, not platform code. `PLAN.md` says privacy
and threat-model patterns are community-build: chatbots compose them from
existing primitives, community rubrics, and remixable templates. Platform code
owns enforcement boundaries only.

## Smallest Useful Change

Capture PR-040 as a composition guide target:

- shape visibility: use the full-platform architecture's field-scoped
  visibility model for concept-vs-instance separation.
- data residency: keep private data host-resident; publish only public,
  reusable concepts to the commons.
- compliance template: use wiki/community templates that prompt for authority,
  regulated-data category, allowed providers, upload whitelist boundaries, and
  post-export review.

The chatbot should present those choices during workflow design and materialize
them as branch/node instructions or community wiki templates. It should not call
a new `privacy_mode` action, set a platform-side `is_private` record, or store
private platform metadata.

## Platform Boundary

The one platform-owned boundary already identified by the existing privacy
design notes remains valid: provider allowlist enforcement at the router. If a
workflow declares that content must stay local, the router must be able to
refuse non-allowed providers before payload dispatch.

That boundary is not a privacy-mode product preset. It is an enforcement
primitive that prevents silent provider-chain leakage.

## Rejected Runtime Work

- no new MCP action such as `privacy_mode`
- no platform-side compliance-template registry
- no platform `is_private` flag for commons records
- no pre-baked HIPAA, SOC 2, GDPR, or similar policy presets
- no server-side redaction taxonomy shipped as product policy

## Follow-Up

If PR-040 is accepted for community content, the appropriate next artifact is a
wiki composition page or catalog entry, not runtime implementation. A later
runtime task is justified only if the router/provider allowlist enforcement gap
is being implemented directly.
