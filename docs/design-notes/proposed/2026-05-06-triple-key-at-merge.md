---
status: proposed
source_issue: 452
source_wiki_path: pages/notes/pages-notes-cowork-substrate-framing-correction-triple-key-at-merge-2026-05-06.md
request_kind: project-design
---

# Triple-Key Approval Belongs At Merge

**Date:** 2026-05-06
**Status:** Proposed correction
**Scope:** Community daemon-request gate policy

## Correction

Host approval is a merge-time gate, not a filing-time or checker-key gate.

Community probes, wiki filings, issue sync, branch drafts, investigation notes,
and checker assignment should flow freely when the requester and daemon meet
the public request contract. The host key is only required when a branch would
change canonical project state by merging, deploying, settling a bounty, or
performing another irreversible privileged action.

The merge gate is a triple-key:

1. **Writer key:** the branch author satisfies the declared writer lane.
2. **Checker key:** an eligible independent checker verifies the branch.
3. **Host key:** the host approves the final merge or equivalent privileged
   action.

## Why This Correction Matters

The community loop is designed to work when maintainers are offline. If host
approval is required before filing a request, assigning a checker, or allowing a
probe branch to investigate, the loop stops being daemon-claimable and becomes a
manually brokered queue.

At the same time, unrestricted merge is not acceptable. Merging changes project
truth, runtime behavior, public surfaces, or bounty settlement state. That is
the point where the host key belongs.

## Affected Surfaces

This correction applies to daemon-request work created from wiki pages,
including bugs, patches, features, docs/ops requests, branch refinement
requests, and project-design requests.

For the current request-sync contract:

- `daemon-request` means a paid or free daemon may claim the request if it
  satisfies the declared gate requirements.
- Code-change writer lanes remain restricted to the allowed writer families
  declared by the request or gate ladder.
- Code-change branches still require an opposite-family checker before merge.
- A missing host approval must not block issue filing, branch creation,
  investigation, draft PRs, or checker assignment.
- A missing host approval must block merge, deploy, bounty settlement, and any
  other privileged finalization step.

## Recommendation

Model host approval as a finalization requirement on gate ladders, not as a
precondition on public request intake.

The existing `branch_requirements` / `bounty_requirements` split in
`docs/conventions/gate-branch-shape.md` is close to the right shape:

- `branch_requirements` should answer whether a candidate branch can claim or
  present evidence for a rung.
- `bounty_requirements` should answer what evidence allows settlement.
- Host approval should be represented as a merge/finalization requirement,
  adjacent to those rung requirements, and consumed by release policy.

This note does not propose a new MCP action. It clarifies where existing and
future gate checks must be placed.

## Rejected Alternatives

### Host approval at filing

Rejected. Filing is observation and intake. Blocking it on host approval loses
community reports before they can be triaged, duplicated, or improved by the
loop.

### Host approval at checker-key assignment

Rejected. Checker assignment is a review-routing decision, not project-state
mutation. Blocking it prevents independent review from developing while the
host is offline.

### Same-family writer/checker with host override

Rejected for code-change branches. Host approval at merge should not replace
independent opposite-family review, because the triple-key design relies on
different failure modes catching different classes of error.

## Policy Shape

For a machine-authored code-change branch, the policy should read:

```yaml
branch_requirements:
  allowed_writer_families:
    - claude
    - codex
  forbid_same_family_checker: true
  required_evidence_refs:
    - tests
    - review
merge_requirements:
  required_keys:
    - writer
    - opposite_family_checker
    - host_approval
bounty_requirements:
  settlement_gate: merged
  required_keys:
    - host_approval
  required_evidence_refs:
    - merge_url
```

The exact storage location for `merge_requirements` is intentionally left open:
it may become a first-class rung field, a release-policy field, or a derived
view over existing branch and bounty requirements. The invariant is placement:
host approval gates finalization, not exploration.

## Consequences

- Wiki sync can continue auto-filing project-design and code-change requests
  without host action.
- Free and paid daemons can investigate and draft branches when they meet the
  declared public contract.
- Release automation must distinguish "may investigate" from "may merge".
- Checker policy remains useful while maintainers are offline.
- Host approval remains load-bearing for canonical changes and payment release.

## Implementation Guidance

Near-term docs and policy changes should use this wording:

> Probes flow freely; triple-key applies at merge.

Runtime enforcement should be added only where finalization occurs: merge
policy, release gates, deployment policy, and bounty settlement. Intake,
request labeling, queue visibility, branch creation, draft PR creation, and
checker routing should not require host approval.

## Open Questions

1. Should `merge_requirements` live directly on each gate ladder rung, or in a
   separate release-policy object that references the rung?
2. Should non-code docs/design branches require the same triple-key at merge,
   or a lighter host + checker policy?
3. How should host approval be recorded so offline daemons can see that a merge
   is blocked without repeatedly re-requesting approval?
4. Should bounty settlement require a second host approval after merge, or can
   merge approval carry settlement approval when `bounty_requirements` point at
   the merged rung?
5. What is the minimum visible evidence a public request needs to show that it
   is "probe-allowed but merge-blocked"?
