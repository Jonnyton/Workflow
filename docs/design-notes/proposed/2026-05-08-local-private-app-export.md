---
title: Local Private App Export
date: 2026-05-08
author: codex-wiki-design
status: proposed
request_id: WIKI-DESIGN
github_issue: 484
wiki_source: pages/design-proposals/design-006-local-private-app-export-desktop-binary-post-export-learning.md
scope: design-only; no runtime code in this branch
sequenced_after:
  - PR-048
  - PR-049
  - FEAT-002
builds_on:
  - PLAN.md#scoping-rules
  - PLAN.md#distribution-and-discoverability
  - PLAN.md#api-and-mcp-interface
  - docs/design-notes/2026-05-01-mcp-host-customer-matrix.md
---

# Local Private App Export

## 1. Recommendation Summary

Accept the proposal as a sequencing plan, not as an implementation request.
After PR-048, PR-049, and FEAT-002 land, Workflow should design a local-private
app export lane that packages a user's private workflow as a desktop binary
around the same portable daemon core. The exported app keeps private content on
the user's machine, can continue learning after export through explicit
local-first sync points, and can account for paid daemon calls without exposing
private payloads to the platform.

The smallest useful project change now is this design note. It defines the
post-dependency shape and the acceptance gates a later implementation branch
must satisfy. It does not add a new MCP action, billing API, export command, or
runtime code.

## 2. Product Shape

The export lane produces a self-contained desktop app for a specific private
workflow. The app is a wrapper around the existing daemon runtime plus a bundled
snapshot of the workflow's local-private state. It is not a fork of Workflow's
engine, and it is not a new canonical store.

Target user shape:

- Local-app users can export, run, inspect, and update the app on their own
  computer.
- Browser-only users may request an export, but a host or local-app device must
  perform the packaging step because the browser tier lacks filesystem and
  code-signing authority.
- MCP hosts remain control stations. The exported binary executes through the
  daemon; chat clients do not become the app runtime.

The exported app should contain:

- a pinned daemon/runtime version;
- domain assets and local workflow state needed for offline use;
- a local policy bundle for provider routing and allowed external tools;
- an update channel back to commons artifacts and approved local patches;
- a privacy-preserving call ledger for billable daemon/provider calls.

## 3. Privacy Boundary

This proposal must preserve the commons-first rule: private content stays on
host machines, and platform-stored data remains public-by-definition. The
exported binary may include private content because it is produced for and
stored on the user's machine. The platform should receive only public commons
references, dependency metadata, billing claims, and integrity proofs that do
not reveal private payloads.

Allowed platform-visible data:

- public commons artifact IDs used by the export;
- daemon/runtime version and package manifest hashes;
- provider family, model class, call time, and metering quantities needed for
  settlement;
- opaque export ID and account/entitlement reference;
- proof that a paid call occurred under an approved local policy.

Disallowed platform-visible data:

- private node content, prompts, files, outputs, or local branch state;
- private workflow names if the user has not made them public;
- raw provider transcripts;
- local filesystem paths beyond coarse capability declarations.

The design should bias toward local ledgers signed by the exported app and
uploaded as minimal settlement records. Any richer diagnostic export requires a
separate user-visible action and must be treated as public or support-shared
data, not background telemetry.

## 4. Post-Export Learning

Post-export learning is a sync discipline, not a second product line. The
exported app can learn from local use by writing local patches, evaluator
results, and user decisions into a local branch. The user can later choose which
parts become public commons material, which remain private, and which should be
discarded.

Recommended lanes:

1. Local-only learning: the app adapts from local evaluator results and user
   corrections without contacting the platform.
2. Commons pull: the app imports newer public rubrics, templates, and daemon
   improvements when the user approves an update.
3. Private-to-public contribution: the app prepares a redacted or user-approved
   contribution candidate for the commons.
4. Support/debug export: the app can emit a bounded diagnostic package only
   after explicit user approval.

The later implementation plan should avoid a hidden "training upload" path.
Learning that affects the platform commons must pass through the same user
approval, remix, attribution, and moderation paths as other public material.

## 5. Billing Shape

Billing should meter daemon/provider calls, not private content. A later
implementation can account for billable calls with local signed receipts that
commit to the minimum settlement facts:

```yaml
receipt_version: 1
export_id: opaque-export-id
call_id: opaque-call-id
provider_family: claude-or-openai-or-local
model_class: coarse-class
started_at: 2026-05-08T00:00:00Z
meter:
  input_tokens: 1234
  output_tokens: 456
  billable_units: 1690
policy_hash: sha256-local-policy
payload_hash: sha256-private-payload-not-uploaded
signature: local-app-signature
```

The `payload_hash` supports dispute and dedupe flows without revealing the
payload. It is not useful unless both sides later agree to inspect the private
payload or a redacted diagnostic package. The platform should not require raw
payload upload for ordinary settlement.

Do not make API-key billing lanes the default writer/checker path for community
work. This proposal is for user-owned exported apps and explicit paid daemon
calls. It must not weaken the existing community-loop rule that subscription
or approved provider lanes are the normal default.

## 6. Sequencing Gates

This proposal should remain design-only until PR-048, PR-049, and FEAT-002 are
landed and their post-merge behavior is verified. The first implementation
branch should begin by replacing these placeholders with concrete landed links
and evidence.

Before runtime work starts, require:

- dependency freshness check for PR-048, PR-049, and FEAT-002;
- explicit target OS and packaging format decision for v1;
- threat model for private payloads, local ledgers, update channels, and
  support exports;
- host matrix entry for which MCP clients can request, launch, or inspect an
  exported app;
- proof plan for offline launch, online update, paid-call receipt upload, and
  no-private-payload upload.

Acceptance gates for the future implementation:

- desktop app launches offline from a clean user machine;
- local private content is absent from platform/network traces during ordinary
  use;
- paid call receipt upload works with only minimal settlement facts;
- user can inspect pending post-export learning before publishing anything to
  the commons;
- package update does not overwrite local private state;
- §14-style concurrency/load proof covers export creation, update checks, and
  receipt upload if the path becomes an uptime-track feature.

## 7. Minimal-Primitive Decision

Do not add a user-facing `export_app` MCP action in v1 just because the product
has an export lane. The primitive question is whether existing workflow,
branch, package, and provider-call concepts can compose the export. If they
can, expose export as a guided composition or desktop/tray UX. Add a platform
primitive only if later implementation discovers a structural gap that a
competent chatbot cannot compose in fewer than a few reliable steps.

Likewise, avoid a general `daemon_call_billing` primitive until settlement
needs prove it. The likely first platform surface is a narrow receipt-ingest
endpoint or existing paid-market ledger extension, not a new public MCP tool.

## 8. Open Questions

1. Which dependency landed artifacts exactly correspond to PR-048, PR-049, and
   FEAT-002? This note intentionally records the sequencing labels from the
   issue body, but a future implementation branch must replace them with PR
   links, commits, or wiki IDs before coding.

2. What is the first desktop target: macOS signed app, Windows installer,
   Linux AppImage, or a developer-only bundle? Recommendation: pick one v1
   target and require the manifest format to be portable to the next target.

3. Are paid calls settled through the paid-market ledger, account billing, or a
   new export-specific ledger? Recommendation: extend an existing ledger if it
   can represent opaque local receipts without payload storage.

4. What user-facing control approves private-to-public learning? Recommendation:
   reuse the commons contribution/review path rather than creating a hidden
   export-learning queue.

## References

- `PLAN.md` Scoping Rules
- `PLAN.md` Distribution And Discoverability
- `PLAN.md` API And MCP Interface
- `docs/design-notes/2026-05-01-mcp-host-customer-matrix.md`
