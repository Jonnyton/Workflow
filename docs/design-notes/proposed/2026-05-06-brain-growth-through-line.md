---
status: proposed
source_issue: 473
source_wiki_path: pages/concepts/pages-concepts-cowork-unfinished-central-ambition-audit-and-refactored-direction-2026-05-06.md
request_id: WIKI-DOCS
---

# Brain Growth as the Next-Phase Through-Line

## Status

Proposed repository preservation of the wiki concept filed by Issue #473.
This is not accepted `PLAN.md` truth and makes no runtime change.

The source issue only exposes the wiki path and title. This note therefore
records the smallest safe project-design claim implied by that title and by
already-present Workflow design docs. It does not claim to reproduce unseen
wiki text.

## Classification

Project design / docs-ops.

The filing is a wiki `concept` page about central ambition and refactored
direction. Per the daemon request contract, the safe repository change is a
proposed design note under `docs/design-notes/proposed/`, not a runtime edit.

## Existing Anchors

`PLAN.md` already defines the central ambition as a global goals engine where
many workflows pursue real-world outcomes, preserve durable learning, and
evolve through community use.

`docs/design-notes/2026-05-02-daemon-mini-openbrain.md` already defines the
daemon-scoped memory architecture: soul file, curated daemon wiki, atomic
mini-brain entries, bounded prompt injection, and observable memory events.

`docs/design-notes/2026-05-04-operating-model-and-four-agent-topology.md`
already frames the wiki plus open brain as the shared learning surface, the
loop as the action body, the dispatcher as routing tissue, and chatbot users as
the sensory edge that files useful change requests.

Together, those docs imply the next-phase through-line: grow the system's
brain, then let action loops use that better brain.

## Direction

Brain growth should be the organizing lens for the next phase of work.

That does not mean adding an abstract "AGI brain" subsystem. It means making
Workflow better at remembering, reviewing, promoting, and using lessons from
real user and daemon activity:

- raw episodes are preserved as source-backed evidence;
- atomic mini-brain entries capture reusable lessons without bloating prompts;
- curated wiki pages promote stable lessons into readable policy and self-model
  surfaces;
- memory retrieval is bounded, observable, and source-cited;
- outcome gates evaluate whether retrieved memory improved the work;
- users and daemons can inspect and correct the learning surface.

The product direction should be judged by whether each shipped primitive helps
the shared brain learn from use. A patch loop, bounty inbox, wiki action,
memory capture, evaluator, connector affordance, or host dashboard earns its
keep when it improves the cycle:

1. notice a real problem or opportunity;
2. file it as a typed artifact;
3. route it to eligible work;
4. execute under explicit gates;
5. record the result and evidence;
6. promote durable lessons into the brain;
7. retrieve those lessons in later similar work.

## What This Refactors Away From

The next phase should not optimize for isolated surfaces that do not compound.

Rejected directions:

- More one-off chatbot affordances without durable memory. They may improve a
  single session but do not make future sessions smarter.
- More autonomous loop machinery that cannot explain what it learned or why it
  used a memory. It increases action without improving judgment.
- A single global memory pool. Existing design requires daemon-scoped identity,
  visibility, provenance, and promotion controls.
- Prompt-preloading large wiki or brain dumps. Existing design requires bounded
  retrieval and explicit low-confidence skips.

## Proposed Work Ordering

Use brain-growth impact as a tie-breaker beneath the Forever Rule uptime
priority:

1. Keep 24/7 user and daemon surfaces working.
2. Prefer fixes that increase the reliability of the notice -> file -> route ->
   execute -> evaluate -> remember -> promote cycle.
3. Prefer memory and wiki work that is source-backed, observable, and
   user-correctable.
4. Defer broad product surfaces that do not feed durable learning.

This does not replace `STATUS.md` priority ordering. It gives future docs and
implementation lanes a coherence check: "What does this teach the brain, and
how will later work retrieve it?"

## Open Questions

1. What is the first measurable brain-growth metric for uptime work: promotion
   lag, low-confidence skip rate, repeated-failure reduction, or memory-hit
   outcome lift?
2. Which wiki pages are the curated public face of the shared brain versus
   daemon-private brain review queues?
3. How should community-authored wiki concepts be promoted into accepted design
   truth without bypassing opposite-provider review?
4. Which user-facing connector action should expose brain review first:
   search, list, promote, reject, or status?
5. How much post-fix clean-use evidence is enough before a memory lesson
   becomes accepted policy rather than a candidate?

## Gate

Before this proposal affects runtime design, an opposite-family checker should
compare it against the source wiki page, `PLAN.md`, and the two existing brain
architecture notes listed above. If the wiki page contains stronger or
different claims than the issue metadata exposed here, this note should be
amended rather than treated as complete.
