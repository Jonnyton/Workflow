---
title: Privacy Mode Design-Time Selection
date: 2026-05-08
author: codex-wiki-design
status: proposed
request_id: WIKI-PATCH
github_issue: 442
wiki_source: pages/patch-requests/pr-040-workflow-privacy-mode-primitive-design-time-selection-of-sha.md
scope: design-only; no runtime code in this branch
classification: project-design
builds_on:
  - PLAN.md#scoping-rules
  - docs/catalogs/privacy-principles-and-data-leak-taxonomy.md
  - docs/design-notes/2026-04-27-host-resident-private-data-design.md
  - docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md
---

# Privacy Mode Design-Time Selection

## 1. Recommendation Summary

Do not add a new user-facing `privacy_mode` primitive. The requested shape,
"design-time selection of shape-visibility + data-residency + compliance
template," is best handled as a chatbot-composed design recipe over existing
Workflow concepts:

- **Shape visibility:** per-field concept/instance visibility, using the
  privacy taxonomy and `artifact_field_visibility` reasoning model.
- **Data residency:** commons-published data vs owner-host-resident data vs
  delegated-host-resident data, using the host-resident private-data design.
- **Compliance template:** a community-authored checklist that the chatbot
  applies while designing the workflow, not a platform certification or
  legal-policy primitive.

The platform should only own enforcement primitives that cannot be safely
composed: host-resident storage boundaries, provider routing constraints,
upload/file-path allowlists, access grants, and audit evidence. Policy bundles
such as "HIPAA mode," "SOC2 mode," "finance mode," or "legal mode" should
remain remixable commons templates.

## 2. Classification

This filing is **project design**, not a bug and not an implementation patch.
It asks for a new primitive shape. Under `PLAN.md` scoping rules, privacy and
threat-model patterns are community-build unless a concrete enforcement
boundary is missing.

The smallest useful project change is this design note plus the supersession
banner on the older 2026-04-18 privacy-mode note. Runtime code would be
premature because the request does not identify a missing enforcement boundary
or a failing user path.

## 3. Design-Time Contract

When a user asks for a private, sensitive, regulated, or compliance-aware
workflow, the chatbot should ask or infer only enough to produce a typed design
record with these fields:

```yaml
privacy_design:
  visibility_shape:
    concept_layer: public | private
    instance_layer: host_private | delegated_host_private | public
    field_overrides:
      - field: string
        visibility: public | private
        reason: taxonomy-reference-or-user-direction
  data_residency:
    residency: commons | owner_host | delegated_host
    host_of_record: local-host-id-or-delegated-host-id
    offline_behavior: wait_for_host | use_read_replica | publish_to_commons
  compliance_template:
    template_id: community-template-id
    user_authority_confirmed: true | false
    required_prompts:
      - prompt-id
    required_audit_evidence:
      - evidence-id
```

This record is a design artifact. It is not itself an enforcement boundary.
The chatbot uses it to choose existing Workflow operations and to decide what
must be written to the commons, what must stay host-resident, and what user
confirmation is required before proceeding.

## 4. Composition Pattern

### Step 1: Classify fields, not whole workflows

Use `docs/catalogs/privacy-principles-and-data-leak-taxonomy.md` to classify
each authored field. Publish generic concepts and structural patterns when
safe. Keep instance values, credentials, regulated details, PII, and
unlicensed content private by default.

Whole-workflow labels such as "private mode" are acceptable as UX language,
but they must compile down to field-level visibility decisions plus a
residency choice. A broad label must not hide which exact fields are public or
private.

### Step 2: Pick data residency

Residency choices are:

| Choice | Meaning | Typical use |
|---|---|---|
| `commons` | Data is public-by-definition and remixable. | Generic workflow concepts, public templates, non-sensitive examples. |
| `owner_host` | Private data lives on the user's host. | Local-app users with their own daemon/tray. |
| `delegated_host` | Private data lives on a trusted host chosen by the user. | Browser-only users or users buying/receiving hosting help. |

The platform commons must not receive private instance data. If no host is
online for a private workflow, the correct behavior is a graceful unavailable
state, not platform-side caching.

### Step 3: Apply a compliance template as a checklist

A compliance template is a commons artifact with:

- a jurisdiction or regime label, such as `hipaa-adjacent`, `gdpr-adjacent`,
  `pci-adjacent`, `privileged-legal`, or `internal-finance`;
- required user confirmations, especially authority to handle the data;
- required visibility defaults;
- required residency defaults;
- audit evidence the workflow should preserve;
- explicit non-certification language.

Templates should help the chatbot ask better questions and leave better audit
trails. They must not claim Workflow has made the user compliant.

## 5. Required Enforcement Boundaries

The recipe can compose privacy policy, but it still depends on platform-owned
enforcement boundaries:

- **Host-resident storage:** private instance data stays out of the platform
  commons.
- **Provider routing:** private or regulated data must not silently fall back
  to non-approved model providers.
- **File-path admission:** local files enter Workflow only through explicit
  allowlists and user-directed paths.
- **Access grants:** private universes remain unreadable without host-side
  authorization.
- **Audit evidence:** user confirmations, residency decisions, and visibility
  decisions are durable enough to inspect later.

If a future bug shows any of these boundaries missing or leaky, that bug should
be dispatched as a targeted enforcement primitive. That is different from
shipping a broad `privacy_mode` action.

## 6. Non-Goals

- No new MCP tool or action named `privacy_mode`, `select_privacy_mode`, or
  similar.
- No platform-shipped HIPAA/SOC2/GDPR certification claim.
- No platform-side private-data cache.
- No whole-workflow private flag as the only source of truth for mixed
  concept/instance workflows.
- No runtime code in this branch.

## 7. Acceptance Guidance For Future Implementation

A future implementation is ready only when it names a concrete enforcement gap.
Examples:

- provider routing ignores a host-resident private workflow's allowed-provider
  policy;
- a commons export includes fields marked private;
- a delegated-host workflow lacks a host-of-record audit trail;
- a file-ingest path bypasses upload allowlists.

Those are implementation tasks. This Issue #442 request, as filed, is a
composition and design-time UX request, so the correct output is a proposed
design note and no runtime change.

