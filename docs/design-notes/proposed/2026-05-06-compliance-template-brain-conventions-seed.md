---
status: proposed
date: 2026-05-06
source_issue: 483
source_request_id: WIKI-DESIGN
source_wiki_path: pages/design-proposals/design-005-compliance-template-brain-conventions-seed-7-user-authored-w.md
classification: project-design
---

# Compliance Template Brain Conventions Seed

## Problem

Issue #483 asks Workflow to seed seven user-authored worked-example pages for
compliance-template brain conventions:

- HIPAA
- GDPR
- SOX
- SOC 2
- PCI
- FERPA
- attorney-client privilege

The design question is not whether Workflow should ship built-in compliance
modes. `PLAN.md` already says privacy and threat-model patterns are
community-built, not platform-built. The useful question is how to accept these
worked examples into the commons so chatbots and daemons can discover, remix,
and adapt them without turning them into platform guarantees.

The source wiki page named by the issue was not present in this checkout at
draft time, so this note scopes the repository-side convention and gates. It
does not author the seven final wiki pages.

## Context

`PLAN.md` scoping rules constrain the design:

- Minimal primitives: do not add compliance-specific tools, actions, evaluator
  kinds, or runtime flags when a composition pattern is enough.
- Community-build over platform-build: compliance templates should be wiki and
  branch material that users evolve, not frozen platform policy.
- Privacy and threat-model patterns are community-build: no pre-baked HIPAA,
  GDPR, SOC 2, or similar runtime modes.
- Commons-first architecture: publish only generic techniques and structural
  patterns. User instances, regulated data, credentials, and privileged facts
  remain host-resident.
- User capability axis: examples must work for browser-only users through
  chatbot composition and for local-app users through host-resident execution.

`docs/catalogs/privacy-principles-and-data-leak-taxonomy.md` gives the
regulated-data default: T4 data is private, training-excluded, and requires the
chatbot to ask the user to confirm authority and host-resident handling.

`docs/design-notes/2026-05-02-daemon-mini-openbrain.md` defines daemon memory
as observable wiki plus mini-brain entries. Compliance examples should teach a
daemon how to ask and route, not grant it permission to make legal conclusions.

## Decision

Accept the request as a proposed commons seed: create seven wiki worked-example
pages only after review, using one shared convention. The seed pages are
community-authored templates for composing safer workflows around regulated or
protected contexts. They are not legal advice, not compliance certification,
and not platform-enforced privacy modes.

Each page should have the same minimum shape:

1. **Scope and non-goal.** Name the category and say the page is a workflow
   composition example, not a legal determination or certification.
2. **Authority prompt.** Provide the exact chatbot question that asks the user
   to confirm authority, data boundary, and host-resident handling before any
   regulated or protected instance data is processed.
3. **Public concept layer.** Show what can safely publish to the commons:
   generic workflow structure, node intent, checklist headings, control
   vocabulary, and redacted examples.
4. **Private instance layer.** Name what must stay host-resident: real people,
   patient/student/customer/cardholder/client details, case facts, audit
   evidence, credentials, raw documents, and outputs derived from them.
5. **Worked branch sketch.** Give a small branch or node chain a chatbot can
   compose from existing primitives, with no new MCP action.
6. **Review gates.** State which human or domain-expert review is required
   before the workflow output is treated as ready.
7. **Failure behavior.** Say what the chatbot/daemon should do when authority,
   data classification, or host-resident handling is ambiguous: pause, ask, and
   keep private.
8. **Remix notes.** Explain which parts are safe to remix across domains and
   which parts must be replaced for each user's jurisdiction, institution,
   contract, or policy environment.

The seven initial pages should be treated as one seed set because the common
convention matters more than any single category. A partial set risks training
chatbots into one-off compliance folklore rather than a reusable composition
pattern.

## Per-Page Intent

| Page | Primary worked-example focus | Must stay private by default |
|---|---|---|
| HIPAA | Intake and processing pattern for health-adjacent records | PHI, diagnoses, patient identifiers, provider records |
| GDPR | Personal-data handling, export/delete request, lawful-basis checklist | Identifiable personal data, data subject requests, account history |
| SOX | Financial-control workflow with evidence collection and signoff | Company financials, control evidence, audit workpapers |
| SOC 2 | Security-control evidence packet and reviewer handoff | System diagrams, access logs, vendor evidence, exceptions |
| PCI | Card-data boundary and tokenized payment-support workflow | PAN/CVV, payment logs, processor credentials, chargeback details |
| FERPA | Education-record access and disclosure-review workflow | Student records, grades, IDs, guardian/student communications |
| Attorney privilege | Legal-workflow intake and privilege-preserving summary | Client communications, legal strategy, case facts, privileged memos |

## Rejected Alternatives

### Add Compliance Modes To Runtime

Rejected. HIPAA/GDPR/SOX/SOC2/PCI/FERPA/privilege modes would violate the
privacy-via-community-composition rule and create false assurance. The platform
should enforce boundaries such as host-resident storage and upload whitelists,
not jurisdiction-specific policy.

### Add A Compliance Evaluator Kind

Rejected for this seed. A generic review gate already composes the needed
behavior: ask authority questions, classify data, keep private, and require
human/domain review. If later evidence shows a structural evaluator primitive
is missing, that should be scoped separately and not tied to one compliance
taxonomy.

### Publish Full Worked Inputs

Rejected. Full examples are tempting but dangerous. The seed pages should use
synthetic or redacted snippets only. Instance-specific facts belong on hosts,
not in the commons.

## Acceptance Gates

Before the seven pages are published or treated as ready:

- Opposite-family review confirms the pages do not imply legal advice,
  certification, or platform compliance guarantees.
- Each page includes the shared minimum shape above.
- Each page names its public concept layer and private instance layer.
- Each page uses synthetic or redacted examples only.
- Each page includes an authority prompt and a pause-on-ambiguity behavior.
- Each page has no new MCP action, runtime flag, evaluator kind, database
  schema, or platform primitive.
- A final scan confirms no real regulated, privileged, credential, or
  personally identifying data was introduced.

## Follow-Up

- Recover or inspect the original wiki design-proposal page if it becomes
  available, then adapt this proposal to any user-authored details not visible
  in the issue body.
- If approved, author the seven wiki pages in one follow-on docs/wiki change
  using this convention.
- After publication, add them to the discoverable composition-pattern catalog
  only as commons examples, not as platform policy.
