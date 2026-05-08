---
title: Brain Growth Through-Line For Next-Phase Workflow
date: 2026-05-06
author: codex-wiki-design
status: proposed
request_id: WIKI-DOCS
github_issue: 473
wiki_source: pages/concepts/pages-concepts-cowork-unfinished-central-ambition-audit-and-refactored-direction-2026-05-06.md
scope: design-only; no runtime code in this branch
builds_on:
  - docs/design-notes/2026-05-02-daemon-mini-openbrain.md
  - docs/design-notes/2026-05-04-operating-model-and-four-agent-topology.md
  - PLAN.md#retrieval-and-memory
  - PLAN.md#community-evolvable-optimization
  - PLAN.md#multi-user-evolutionary-design
---

# Brain Growth Through-Line For Next-Phase Workflow

## 1. Request Classification

Issue #473 is a project-design request, even though it arrived through the
docs-ops wiki sync lane. The filing asks to preserve and refactor an
"unfinished central ambition audit" around brain growth as the next-phase
through-line. That is architectural direction, not a bug, branch refinement, or
runtime patch.

This note is therefore intentionally design-only. It should not create a new
MCP action, database table, daemon behavior, or UI surface by itself. Runtime
work should wait until the proposal is accepted or narrowed into a specific
implementation spec with tests and opposite-family review.

## 2. Direction

The next phase should treat Workflow's central ambition as the growth of a
shared, inspectable project brain.

"Brain growth" here means the system gets better at remembering, retrieving,
evaluating, and applying what users and daemons learn across runs. It is not a
single memory feature. It is the through-line that connects daemon memory,
wiki knowledge, community patch loops, branch lineage, evaluator lessons, and
real-user outcome signals.

The useful question for next-phase work is:

> Does this change increase Workflow's ability to learn from a witnessed event
> and reuse that learning safely through a user-visible path?

If the answer is no, the work may still be useful, but it is probably
subordinate to uptime or cleanup rather than part of the central ambition.

## 3. Brain-Growth Criteria

Next-phase project work should improve at least one of these abilities.

### Capture

Workflow records the raw episode that created the learning:

- user request;
- branch, node, gate, or patch-loop state;
- tool/action inputs and outputs;
- checker feedback;
- test, runtime, or user-surface evidence;
- human or host intervention.

Without capture, the system cannot distinguish durable learning from a chat
impression.

### Compression

Workflow turns raw episodes into bounded, typed, reviewable memories:

- failure modes;
- reusable procedures;
- policy refinements;
- evaluator lessons;
- branch or node design patterns;
- contradiction records;
- open-loop reminders.

Compression must preserve source links and confidence. The project should not
promote loose summaries into trusted memory without provenance.

### Retrieval

Workflow brings the right memory back at the moment it can change behavior:

- pre-claim context feeds;
- daemon runtime memory packets;
- review gates;
- branch continuation prompts;
- wiki search and concept pages;
- public chatbot tool responses.

Retrieval should be selective. A larger prompt is not brain growth if it makes
future agents noisier or less reliable.

### Application

Workflow applies the memory through a bounded, auditable action:

- revising a patch request before dispatch;
- routing work to a better daemon or checker;
- blocking a known bad pattern;
- choosing an evaluator;
- updating a wiki page;
- proposing a branch improvement;
- escalating to a host only when the substrate cannot act.

The learning loop is incomplete until remembered knowledge changes a future
decision.

### Feedback

Workflow measures whether the applied memory helped:

- tests passed or failed;
- checker accepted or rejected;
- user confirmed or bounced;
- production traces stayed clean;
- repeated manual intervention decreased;
- outcome gates advanced.

Feedback prevents the brain from accumulating confident but untested beliefs.

## 4. Implications For Current Surfaces

### Daemon Mini-OpenBrain

`docs/design-notes/2026-05-02-daemon-mini-openbrain.md` is the closest
implementation-shaped design. It should remain the memory architecture anchor:
raw episodes, atomic mini-brain entries, curated wiki promotion, bounded
runtime packets, and observable memory events.

The next design step is not "add more memory everywhere." It is to choose one
high-leverage learning path and prove the full capture-to-feedback loop.

### Operating Model

`docs/design-notes/2026-05-04-operating-model-and-four-agent-topology.md`
frames Workflow as a distributed learning system across users, chatbots,
daemons, and operators. This proposal narrows that frame into an engineering
criterion: each next-phase central-ambition change should name which
brain-growth stage it improves and how that improvement is verified.

### Community Loop

The community patch loop is the highest-value first application because it is
already producing repeated, typed learning events: failed dispatches, checker
objections, stale claims, substrate blockers, and manual interventions.

The strongest next slice would be a manual-intervention ledger that can promote
repeated checker or operator feedback into typed failure-mode memory, then feed
that memory into future pre-dispatch review.

### Wiki Commons

The wiki should be the human-readable face of accepted or proposed learning,
not the only memory backend. Concept pages, BUG pages, and design notes should
point back to source episodes or trace IDs when they claim a durable lesson.

### Branch And Goal Evolution

Branch lineage and Goal-level outcome gates are brain tissue too. A branch that
advances through a real-world gate teaches the system which node patterns,
evaluation policies, and collaboration paths worked. Those lessons should be
extractable without collapsing diverse branches into one canonical workflow.

## 5. Recommended Next Slice

Do not start with a broad "brain platform" implementation. Start with one
closed loop:

1. Record every manual checker/operator intervention on community patch-loop
   requests in a typed ledger.
2. Classify each intervention as a substrate blocker, prompt/content failure,
   review-gate failure, coordination failure, or host-only decision.
3. Promote repeated classes into candidate mini-brain entries with source
   links and confidence.
4. Inject accepted entries into the next pre-dispatch or pre-claim review for
   matching requests.
5. Measure whether the same intervention class recurs less often after the
   memory is applied.

This slice composes with the forever uptime rule: it reduces dependence on
manual operator availability while keeping every change observable and
reviewable.

## 6. Non-Goals

- Do not add a generic autonomous self-improvement loop.
- Do not expose new public MCP tools from this proposal alone.
- Do not replace `PLAN.md` memory architecture without host approval.
- Do not promote private user content into shared memory unless the privacy
  layer explicitly permits it.
- Do not treat a concept page as accepted design truth until it is reviewed and
  folded into `PLAN.md` or a specific accepted spec.

## 7. Acceptance Gate For Future Implementation

Any implementation derived from this note should prove:

- one raw episode is captured with enough source evidence to audit it;
- one typed memory is generated or updated from that episode;
- retrieval selects that memory only for a relevant future task;
- the selected memory changes a concrete decision or review outcome;
- verification records whether the changed decision helped;
- privacy, provenance, and user-visible inspection rules are preserved.

If a proposed implementation cannot satisfy that chain, it is probably memory
storage, not brain growth.

## 8. Open Questions

1. Which first ledger should own manual interventions: the community loop's
   existing GitHub issue comments, a repo-local JSONL artifact, or a daemon
   wiki page promoted from raw events?

2. What recurrence threshold should promote a failure class from observation
   into accepted memory? Recommendation: start with manual review after two
   independently witnessed repeats, then automate only after the classifier has
   clean review history.

3. How should users inspect and correct shared memories that were derived from
   their work? Recommendation: expose source-linked wiki summaries first; defer
   direct memory editing until the mini-brain surface has auth and visibility
   gates.

4. Which outcome metric should be primary for the first slice? Recommendation:
   reduction in repeated manual intervention for the same typed class, not raw
   patch throughput.

## References

- `docs/design-notes/2026-05-02-daemon-mini-openbrain.md`
- `docs/design-notes/2026-05-04-operating-model-and-four-agent-topology.md`
- `PLAN.md` Retrieval And Memory
- `PLAN.md` Community Evolvable Optimization
- `PLAN.md` Multi-User Evolutionary Design
- `ideas/INBOX.md` loop self-stewardship capture, 2026-05-05
