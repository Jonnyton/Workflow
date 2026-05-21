# Composing ExperiencePool queries - aggregating experience_lesson memories without a new typed surface

[[index]]

This is the canonical wiki page documenting how chatbots compose ExperiencePool aggregation queries from existing primitives. Per the audit verdict (Q2): the platform does NOT ship a typed `experience_pool action=summarize` action. Aggregation is composable from existing primitives + this composition pattern.

## What's an ExperiencePool?

A read-only view over typed `experience_lesson` memories for a given Goal + branch family, augmented by cross-references to evidence (`EvalResult`), branch lineage, and outcome refs. The "pool" itself is not a stored object - it's the result of composing several existing queries against the data that's already there.

## The composition

To answer "what has this branch family learned?", a chatbot composes:

1. **Query the lessons** - `brain action=query memory_kind=experience_lesson` filtered by `metadata.goal_id` and/or `metadata.branch_id`.
2. **Get bound branches** - `branches action=list goal_id=<id>` to know the branch family.
3. **Get the gate ladder** - `goals action=get goal_id=<id>` for outcome context.
4. **Cross-reference evidence** - for each lesson, the `evidence_refs` URIs (e.g., `evalresult://<id>`) point at existing `EvalResult` artifacts the chatbot can fetch directly via the runs API.
5. **Synthesize** - the chatbot writes a digest grouping lessons by `lesson_kind` (failure_mode / intervention / pattern / holdout_signal / outcome_link).

Five steps; <=5 reasoning steps for a competent chatbot. No new platform primitive required.

## Worked example - "What has the Markovic branch family learned in the last 30 days?"

### Step 1 - Query the lessons

```
brain action=query
  memory_kind=experience_lesson
  filter={"metadata.goal_id": "goal:markovic-publication"}
  limit=50
```

Returns up to 50 lesson entries the daemon has captured against the Markovic Goal. Each entry has the full 11-field metadata + content narrative.

### Step 2 - Get bound branches

```
branches action=list
  goal_id=goal:markovic-publication
```

Returns the branch definitions bound to the Goal - useful context for grouping lessons by `branch_id` and for noting which branches are absent from the lesson pool (often a signal that those branches haven't been run recently).

### Step 3 - Get the gate ladder

```
goals action=get
  goal_id=goal:markovic-publication
```

Returns the Goal's outcome-gate ladder + current rung claims. Helps frame which lessons advanced the Goal up the ladder vs. lessons from runs that stayed at the same rung.

### Step 4 - Cross-reference evidence

For each lesson, the `evidence_refs` field contains URIs like `evalresult://<id>`. The chatbot fetches each:

```
runs action=get_eval_result
  eval_result_id=<id>
```

Returns the EvalResult record with artifacts (screenshots, packets, traces) the lesson cites as evidence. Lessons without verifiable evidence are downweighted in the synthesis.

### Step 5 - Synthesize the digest

The chatbot writes a narrative grouping the lessons:

```
ExperiencePool - Markovic Publication Goal (last 30 days)
========================================================

Failure modes observed (3):
- Patient placeholder inconsistency in simulator step (3 occurrences)
- Provider chain exhaustion on hello-quantum branch (1 occurrence)
- Co-author signature drift on draft refresh (1 occurrence)

Interventions that worked (2):
- Placeholder validation gate before simulator (caught 3 prior false-passes)
- Explicit co-author signature timestamp check (caught 1 drift case)

Patterns observed (1):
- Small-Goal branches (<=3 sub-rungs) merge ~4x faster than larger Goals

Held-out signals (1):
- Candidate Y outperformed baseline X by 12pp across 8 scenarios

Outcome links (0):
- (No real-world outcome lessons captured yet; arXiv submission pending)

Branches with no recent lessons (2):
- branch:markovic_fingerprint_rd_v2 (last lesson 45 days ago - stale)
- branch:markovic_qpu_explore (no lessons; branch unproven)

Recommendation: the placeholder-validation-gate intervention is the
strongest signal in this pool. Worth promoting to other simulator-
shaped Goals.
```

That's the ExperiencePool view. No new typed surface; no new MCP action; everything from existing primitives + chatbot synthesis.

## When to FORK and propose a new platform primitive

Per the audit verdict's Q2: if real usage shows this composition is unreliable (takes >5 reasoning steps consistently, or chatbots produce inconsistent digests because of step misordering), Slice 3+ may promote a typed `experience_pool action=summarize` aggregation action. **Default expectation is: not needed.**

If a chatbot finds itself struggling with this composition, file a `patch_request` describing the friction. The platform should ship the primitive ONLY if the composition is structurally impossible, not just inconvenient.

## Visibility considerations (community-composed)

Same pattern as PrivateTraceCommons (`pages/plans/composing-session-trace-summaries.md`): `experience_lesson` entries carry `visibility` tags (`host_private` / `borrowable_role_context` / `published`); the platform enforces nothing about which visibility blocks promotion. Universes wire their own enforcement gates per Goal.

Common universe patterns:

- **Personal-creator universes:** All lessons `host_private`; never promoted.
- **Shared corpus universes (Markovic, fantasy commons):** Most lessons `borrowable_role_context`; promoted to `published` when a real-world outcome link is established.
- **Project-self-voice universe (Workflow itself):** Lessons about Workflow's own development are typically `borrowable_role_context` initially, promoted after the lesson generalizes beyond the originating branch.

## Cross-Goal lesson remix

When a lesson is `published`, it's readable in commons wiki search across universes. A chatbot working in a different Goal can search for relevant lessons:

```
wiki action=search
  query="placeholder validation gate simulator"
```

...and find any published lessons from any universe. The lesson's `goal_id` + `branch_id` fields tell the chatbot which originating context it came from; the chatbot decides whether the pattern applies to the new Goal.

This is the "experience flywheel" - published lessons compound across the commons; new Goals inherit accumulated learning from prior Goals without the platform shipping a cross-Goal aggregation primitive.

## What the platform is NOT shipping (per audit verdict)

- No `experience_pool` table - use the existing `daemon_brain_entries` table
- No `experience_pool action=summarize` MCP action - use the composition pattern documented above
- No platform `merge_policy` enum - free-text per Goal (community-evolved)
- No platform `diversity_policy` enum - free-text per Goal
- No GroupEvolutionRun runtime - dormant spec only (#937)
- No parallel evidence shape - `EvalResult` reused verbatim
- No held-out evaluation primitive separate from `AcceptanceScenario` - held-out sets are scenario packs (composes with #936)
- No platform-enforced visibility coupling - universes compose gates per Goal (same pattern as PrivateTraceCommons / #935)

## Cross-links

- Audit (authority): `docs/audits/2026-05-02-experience-pool-claude-review.md`
- Slice 1 design note: `docs/design-notes/2026-05-02-experience-pool-and-group-evolution.md`
- Slice 1 minimal schema spec: `docs/specs/2026-05-02-experience-pool-minimal-schema.md`
- Sibling composition pattern: `pages/plans/composing-session-trace-summaries.md` (PrivateTraceCommons)
- Brain Module section of PLAN.md (post-PR-915 restructure)

## Open follow-up

If a universe's chatbot finds the 5-step composition unreliable, file a `patch_request` describing the friction. The platform should promote the broken step into a primitive ONLY if the composition is genuinely structurally impossible, not just inconvenient.
