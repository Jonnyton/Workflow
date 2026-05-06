---
date: 2026-05-06
author: codex-wiki-design
status: proposed
request_id: WIKI-DESIGN
issue: 482
wiki_source: pages/design-proposals/design-004-canonical-goal-completion-probe-researcher-paper-to-publicat.md
scope: design-note only; no runtime implementation
builds_on:
  - PLAN.md#Scoping-Rules
  - PLAN.md#Evaluation
  - PLAN.md#Multi-User-Evolutionary-Design
  - docs/specs/2026-04-19-handoffs-real-world-pipeline.md
---

# Canonical Goal-Completion Probe: Researcher Paper To Publication

## Classification

This filing is **project design**. It asks Workflow to define a canonical
empirical probe for the claim that a daemon can drive a long-horizon real goal,
not just produce a plausible intermediate artifact. The smallest useful
project change is this proposed design note. Runtime code, new MCP actions, and
new evaluator kinds are intentionally out of scope.

The source wiki page named by the issue is not present in this checkout, so
this note uses the issue body as the request source.

## Recommendation Summary

Adopt "researcher paper to publication" as a canonical long-horizon
Acceptance Scenario Pack once the scenario-pack contract exists. The probe
should measure whether Workflow can preserve goal state, evidence, user
control, branch lineage, and outcome tracking across a multi-month research
drive that starts with a researcher intent and advances through public external
gates: draft, peer feedback, submission, acceptance, publication, and later
impact signals.

This should not become a special-purpose research-paper primitive. It should be
a reusable scenario definition over existing and planned primitives:
Goal/Branch, artifact lineage, custom Evaluator rubrics, handoffs, outcome
recording, and chatbot-surface verification. The probe is valuable precisely
because it is domain-specific enough to be empirically hard while remaining
platform-generic in mechanism.

## Why This Probe

PLAN.md already states that Goals should be judged by real-world outcome
ladders, and gives research papers as the example ladder: draft -> peer
feedback -> submission -> acceptance -> publication -> citations ->
breakthrough. The current Evaluation section also accepts the direction of
Workflow-native long-horizon scenario packs, combining user simulation, rubric
checks, runtime evidence, and artifact capture into `EvalResult` evidence.

The researcher-paper probe is the empirical bar for that design:

- It spans weeks or months, so it tests durable memory, resumption, and
  non-online host assumptions.
- It includes multiple human and institutional gates, so a polished draft is
  insufficient.
- It has concrete public artifacts, such as preprints, reviews, submissions,
  DOIs, and citations, so claims can graduate from self-report to external
  verification.
- It forces privacy and commons boundaries: private drafts and correspondence
  remain host-side unless the user explicitly publishes artifacts to the
  commons.
- It is not fantasy-specific, proving that Workflow's daemon engine can bind to
  a scientific production domain without changing the platform core.

## Scenario Shape

The scenario pack should define a single Goal family:
`research-paper-to-publication`.

The scenario starts when a user asks Workflow to help drive a paper from an
initial research intent, partial experiment, literature question, or rough
manuscript toward publication. It ends only when the run reaches a declared
external outcome gate or the user explicitly closes the effort.

The pack should record these artifacts as evidence, using existing or planned
generic surfaces rather than new research-only fields:

| Evidence | Purpose |
| --- | --- |
| Goal declaration | Names the intended real-world outcome and gate ladder. |
| Branch lineage | Preserves alternate methods, drafts, review-response paths, and forks. |
| User decisions | Records irreversible choices, such as submission targets and public release. |
| Method and data manifests | Let evaluators and reviewers check reproducibility claims. |
| Draft artifacts | Track manuscript, figures, tables, supplementary files, and cover letters. |
| Review artifacts | Track peer feedback, advisor feedback, reviewer comments, and responses. |
| Handoff/outcome records | Track submission, acceptance, publication, DOI, citation, and retraction signals. |
| Chatbot transcript excerpts | Prove that a browser-only user can steer the work through a real MCP client. |

The scenario should use the generic `Evaluator` surface for rubric checks. Good
starter rubrics include methods completeness, citation correctness,
cross-algorithm parity, reproducibility claim verification, review-response
coverage, and submission-package completeness. These are community-evolved
rubrics, not platform-shipped evaluator subtypes.

## Gate Ladder

The probe should score progress by highest verified gate reached, not by how
convincing the latest draft sounds.

| Gate | Minimal evidence |
| --- | --- |
| G0 Goal bound | Goal, user intent, privacy posture, and branch seed are recorded. |
| G1 Research plan stable | Methods/data plan and risk register pass review by a human or custom rubric. |
| G2 Draft complete | Manuscript package exists with figures/tables/supplemental checklist. |
| G3 Feedback received | Peer/advisor/community feedback is captured and linked to response tasks. |
| G4 Submission ready | Target venue requirements are satisfied and irreversible submission is user-approved. |
| G5 Submitted | Handoff or user-attested submission evidence is recorded. |
| G6 Accepted or published | External acceptance, DOI, arXiv/preprint, journal page, or equivalent is recorded. |
| G7 Post-publication impact | Citation, replication, award, downstream adoption, or correction signal is recorded. |

G5 and above must distinguish user-attested, externally visible, and
automatically verified evidence. Self-report is acceptable early, but
leaderboards and public claims should prefer externally verifiable outcomes.

## Non-Goals

- Do not add a `publish_research_paper` MCP action.
- Do not add research-paper-specific platform tables before the Goal/Branch and
  outcome surfaces require them.
- Do not add named evaluator kinds for prose or research methods checks; use
  custom evaluators and community rubric recipes.
- Do not make the platform store private manuscript content in public
  platform data. The commons contains only deliberately published artifacts,
  recipes, rubrics, and outcome records safe for public discovery.
- Do not claim success from a local script or direct MCP call alone. The
  acceptance proof must include a rendered chatbot conversation through a real
  MCP client once the scenario is executable.

## Fit With Scoping Rules

**Minimal primitives:** the probe identifies a scenario, not a new primitive.
If implementation later discovers a structural gap, the gap should be named
independently and reduced to the smallest generic primitive.

**Community-build over platform-build:** domain rubrics, checklists, and venue
recipes should evolve in the wiki/commons. Platform code should focus on
scenario-pack execution, evidence capture, outcome recording, discovery, and
remix.

**Privacy via community composition:** sensitive drafts, reviewer comments, and
private data stay host-side unless the user explicitly publishes them.
Scenario instructions should teach the chatbot to compose privacy posture from
existing boundaries.

**Commons-first architecture:** the public platform stores shared recipes,
rubrics, published artifacts, attribution, and outcome metadata. Private branch
content remains host-resident.

**User capability axis:** the probe must be runnable by a browser-only user
through Claude.ai or ChatGPT once public MCP acceptance is available, with
local-app hosts adding capacity for private files, long-running jobs, and local
tools.

## Implementation Sketch

1. Define the generic Acceptance Scenario Pack contract for long-horizon
   Workflow-native probes.
2. Encode this researcher-paper pack as a scenario fixture/spec, not runtime
   special-case logic.
3. Seed community rubric/checklist pages for the research-paper ladder:
   methods reproducibility, venue fit, submission package, review response, and
   publication outcome verification.
4. Run the scenario first as a dry-run simulation with synthetic artifacts,
   then as a real chatbot-surface acceptance test, and only later as a
   multi-month live drive.
5. Fold lessons back into generic Goal/Branch, outcome, handoff, and evaluator
   surfaces rather than into research-only shortcuts.

## Acceptance Criteria For This Proposal

- The probe is accepted as a canonical scenario-pack candidate, not as an
  implementation request.
- Any later implementation names the generic primitive gap it needs before
  writing platform code.
- The first executable version produces durable evidence for each gate it
  claims.
- Public success claims include date, environment, scenario version, chatbot
  client, artifact IDs, and whether each outcome is self-reported or externally
  verified.
- The scenario can fail honestly: a polished draft with no submission evidence
  must not be reported as publication success.

## Open Questions

1. What exactly does the filing's "6+5 framing" name in the host's current
   vocabulary? This note treats it as the empirical bar for multi-month
   goal-completion, but the term should be linked to its canonical source
   before acceptance.
2. Should G6 split acceptance and publication into separate gates for fields
   where acceptance and publication are months apart?
3. Which external identifiers should count as public verification for the first
   version: DOI, arXiv ID, journal URL, ORCID work entry, institutional
   repository URL, or a manually reviewed citation?
4. How should the scenario handle failed or rejected submissions: as negative
   outcomes, partial progress, or branch material for remix?
5. What is the minimum synthetic fixture that exercises the full ladder without
   pretending to prove a real publication?

## References

- PLAN.md, "Scoping Rules".
- PLAN.md, "Evaluation".
- PLAN.md, "Multi-User Evolutionary Design".
- `docs/specs/2026-04-19-handoffs-real-world-pipeline.md`.
- `docs/design-notes/2026-04-27-methods-prose-evaluator.md`.
