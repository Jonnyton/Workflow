# Integration Patterns — Catalog v1

**Status:** v1 catalog. Sibling to `node-type-taxonomy.md`.
**Purpose:** name + describe the common ways nodes compose into BranchDefinitions. Chatbot consults this when designing new branches; catalog browser filters by pattern.
**Audience:** chatbot (primary; uses this to pattern-match user intent onto known branch shapes); contributor (secondary; lexicon for describing branches in PR reviews).
**Licensing:** CC0-1.0.

---

## 1. Why patterns

Node-type taxonomy answers "what is this node." Integration-pattern catalog answers **"how do these nodes fit together."**

At Wikipedia-scale workflow design, similar problems keep producing similar-shaped branches. A user asking for a "research pipeline" and a user asking for an "invoice pipeline" both end up with extract → validate → route structures — **same integration pattern, different domains**. Naming these patterns lets the chatbot + the catalog's search surface match on *shape* even when subject-matter differs — the cross-domain-structural-match property per `project_convergent_design_commons.md`.

**Use this catalog when:**
- Chatbot is designing a new BranchDefinition from user intent.
- Chatbot is searching `discover_nodes` + wants to filter by branch shape, not just semantic match.
- Contributor is describing a branch's composition pattern in a PR.

---

## 2. The patterns

Every BranchDefinition maps to one primary integration pattern. Secondary patterns are possible (a branch can have a chain as its main shape + a fork-join inside one step); the `primary_pattern` field captures the top-level shape.

### 2.1 Linear chain

The simplest composition: N → N+1 → N+2 → ... → end. No branching, no loops.

**Sample from `prototype/workflow-catalog-v0/catalog/branches/`:** `research-paper-pipeline.yaml` — literature_gap_mapper → hypothesis_generator → methodology_selector → citation_formatter → END.

**When to use:** every step strictly depends on the previous one's output; no need for parallelism; no conditional routing.

**Failure modes:** one failing node halts the chain. No retry primitive built-in — retry is node-level or relies on a wrapping orchestrator.

**Typical state_schema shape:** accumulating — each step adds fields, earlier fields stay addressable by later steps.

**Node-taxonomy composition:** any types can chain. Common: extractor → validator → transformer → side-effecter.

### 2.2 Fork-join (parallel)

Split into N parallel branches after a node; converge with an aggregator.

```
         ┌─ branch_A ─┐
start ──┤             ├── aggregator ── end
         └─ branch_B ─┘
```

**When to use:** N things can be computed independently (summarize docs A + B + C in parallel); final step combines.

**Failure modes:** any leg failing fails the join unless the aggregator tolerates partial results. Budget-per-leg can vary (slow leg bottlenecks the whole run).

**Typical state_schema shape:** parallel-output fields (one per leg), then an aggregated output. Reducer on the output field (per `Annotated[list, operator.add]` hard-rule) collects parallel outputs safely.

**Node-taxonomy composition:** N identical generator/extractor nodes + one aggregator node.

### 2.3 Eval-loop (evaluator-gated iteration)

Core pattern for quality-gated work: draft → evaluate → revise-or-commit.

```
start → draft ──┐
                ▼
           evaluator ──── score >= threshold ──→ commit → end
                │
                └── score < threshold ──→ revise_decision ──→ draft
                                                      (bounded retry)
```

**Sample:** `fantasy-scene-chapter-loop.yaml` — with bounded retry count (revise_count < 3 guard). Also the fantasy-daemon scene loop in the `domains/fantasy_daemon/` existing code.

**When to use:** output quality is variable + needs a programmatic check-gate before advancing. Common in creative work (scenes, drafts, prose) + in correctness-sensitive work (code review, research validation).

**Failure modes:** unbounded retries — must have a retry-count cap + fallback-path when cap hits (commit anyway + escalate vs dead-end). The `RC-3 gate` in the fantasy-daemon's scene pipeline is the lived-experience version of this.

**Typical state_schema shape:** accumulating + retry-counter (reducer: increment).

**Node-taxonomy composition:** generator → evaluator → router (soft-gate) → generator (loop).

### 2.4 Router-split (conditional dispatch)

Branch diverges into different downstream nodes based on a routing decision.

```
                      ┌── path_A ── end_A
start → router ──────┤
                      └── path_B ── end_B
```

**Sample:** `invoice-batch-processor.yaml` — validator output routes to accounting-ingest (pass) or human-review (fail).

**When to use:** different kinds of input need different kinds of treatment. Common: classify → treat by class.

**Failure modes:** router misclassification → wrong downstream; each branch needs its own end-state. Tests should cover each route path separately.

**Typical state_schema shape:** carries a `routed_to` enum field; downstream nodes check the enum.

**Node-taxonomy composition:** router (§2.5 in node-taxonomy) + N downstream nodes (any types).

### 2.5 Fan-out retriever

Single query → retrieve N candidates → process each.

```
start → retriever ──→ for each candidate ──→ processor → aggregator → end
```

**When to use:** "search, then process the top N results." Literature review pipelines, multi-document summarization, option-enumeration.

**Failure modes:** retriever returns zero candidates → downstream stalls. Guard: `if len(candidates) == 0: fall_back_to_default`.

**Typical state_schema shape:** array of candidates + per-candidate processed output + final aggregate.

**Node-taxonomy composition:** retriever (§2.6) + N × (transformer or generator) + aggregator.

### 2.6 Saga — compensable side-effects

For workflows that do real-world things (call external APIs, send emails, commit files): each irreversible action has a compensating action if downstream fails.

```
start → action_1 → action_2 → action_3 → end
                                ▲
                                │ fail
                                ▼
                          compensate_2 → compensate_1 → end_failed
```

**When to use:** branch does multiple external-effect actions (per node-taxonomy §2.8 + effect_class='external-effect'); partial-failure matters.

**Failure modes:** compensations themselves can fail — must be idempotent + best-effort. Worst case: human intervention.

**Typical state_schema shape:** per-action completion markers + per-action compensation status.

**Node-taxonomy composition:** N side-effecters + N compensators (themselves side-effecters) + an orchestrator.

**Implementation note:** sagas are genuinely hard — if you find yourself designing one, flag it for extra review. Consider whether the action can be made reversible at the source instead.

### 2.7 Streaming / event-driven

Branch consumes events as they arrive; processes each; does NOT wait for batch completion.

```
event_source ──→ processor ──→ writer
   │                             │
   │                             ▼
   └── continuous stream ──→ [runs indefinitely]
```

**When to use:** workflow is inherently ongoing (monitoring a chat, tracking an RSS feed, real-time moderation queue). No natural end-state.

**Failure modes:** backpressure (events arrive faster than processing); crash-recovery (must resume at the correct event position). Not MVP — most MVP workflows are batch.

**Typical state_schema shape:** event-log cursor + per-event processed-flag.

**Node-taxonomy composition:** continuous-invoked generators + writers. Often composed with a saga for compensating mis-processing.

### 2.8 Orchestrator (hierarchical)

One top-level branch delegates to sub-branches per phase. The sub-branches themselves may use any of §2.1–2.7.

```
top_branch:
  phase_A → [sub_branch_A — its own shape] → phase_B → [sub_branch_B] → end
```

**Sample (architectural):** fantasy-daemon's universe → book → chapter → scene hierarchy is a real-world orchestrator. Each level delegates to a sub-branch with its own internal shape (scene loop is §2.3, chapter loop is a chain, etc.).

**When to use:** long-horizon work where phases have distinct shapes; composition clarity.

**Failure modes:** abstraction cost — debugging a 3-level-deep orchestrator is harder than debugging a flat branch. Design-smell: if you're 4 levels deep, flatten.

**Typical state_schema shape:** scope-nested state (per `project_memory_scope_mental_model.md` tiered scoping).

**Node-taxonomy composition:** orchestrator (§2.10) at each level + sub-branches.

---

## 3. Decision tree — pick your pattern

When the chatbot is designing a new branch, walk this:

```
Does the workflow have branching based on content or intermediate results?
 ├─ No → continue
 │      Is there a quality-check with possible retry?
 │       ├─ Yes → §2.3 eval-loop
 │       └─ No → §2.1 linear chain
 │
 └─ Yes → continue
        Does the branch split by a classification decision?
         ├─ Yes → §2.4 router-split
         │
         └─ No, it splits to work in parallel on N things:
                Are the N things independent + known up front?
                 ├─ Yes → §2.2 fork-join
                 └─ No, discovered from a search/retrieval step → §2.5 fan-out retriever

Does the branch perform real-world effects with possible partial failure?
 ├─ Yes → layer §2.6 saga on top of whatever core pattern
 └─ No → core pattern suffices

Does the branch run continuously on arriving events vs a batch request?
 ├─ Yes → §2.7 streaming (post-MVP typically)

Is there enough complexity to warrant phase-level composition?
 ├─ Yes → §2.8 orchestrator (top-level) with any of §2.1-2.7 at each level
```

---

## 4. Integration with schema

Extend `branches` table (or `branch_definitions`, naming per schema spec #25 TBD — the `nodes` sibling table for composite definitions):

```sql
ALTER TABLE public.branches
  ADD COLUMN primary_pattern text NOT NULL DEFAULT 'chain'
    CHECK (primary_pattern IN (
      'chain', 'fork_join', 'eval_loop', 'router_split',
      'fan_out_retriever', 'saga', 'streaming', 'orchestrator'
    )),
  ADD COLUMN secondary_patterns text[] NOT NULL DEFAULT '{}';

CREATE INDEX branches_primary_pattern ON public.branches (primary_pattern);
```

Branch-level `discover_branches` (dual of `discover_nodes` for composite definitions) surfaces `primary_pattern` in the candidate response. Chatbot uses this + node-type filters to match user intent onto known branch shapes.

---

## 5. Example classifications (v0 sample branches applied)

From `prototype/workflow-catalog-v0/catalog/branches/`:

| Branch | Primary pattern | Secondary | Why |
|---|---|---|---|
| `research-paper-pipeline` | chain | — | Strict sequential: gap-map → hypothesize → method → citations. No branching. |
| `fantasy-scene-chapter-loop` | eval_loop | — | Draft → evaluator → revise-or-advance with bounded retry. |
| `invoice-batch-processor` | router_split | chain | Chain of extract + validate ends in a route-by-validator-result split. Router is the distinctive top-level shape. |

---

## 6. OPEN flags

| # | Question |
|---|---|
| Q1 | **Multi-pattern branches.** What if a branch is genuinely hybrid (chain with an embedded fork-join)? v1: single `primary_pattern` + `secondary_patterns[]` captures it. v2: consider decomposing into orchestrator with sub-branches each having one primary pattern. |
| Q2 | **Chatbot-suggested pattern match.** Should `discover_branches` emit a "patterns that fit your intent" hint alongside the matched candidates? Recommend yes, post-MVP. |
| Q3 | **Pattern linting.** Should a validator catch clear pattern-violations (e.g. "you declared eval_loop but have no retry-counter field")? Nice to have; flag for v2 tooling. |
| Q4 | **Streaming as MVP scope?** §2.7 is flagged post-MVP. Confirm or re-scope if host wants streaming workflows at launch. |
| Q5 | **Saga primitive support.** Real saga primitives in LangGraph are non-trivial — need compensation-handler declarations in node schema. Post-MVP add. |

---

## 7. References

- Node-taxonomy catalog — `docs/catalogs/node-type-taxonomy.md` (§2 types consumed by patterns here).
- Privacy catalog — `docs/catalogs/privacy-principles-and-data-leak-taxonomy.md` §7 (system-point taxonomy includes daemon execution + connector-push which most patterns touch).
- Spec #25 `nodes` + `branches` schema — the basis for the `primary_pattern` ALTER.
- Sample branches — `prototype/workflow-catalog-v0/catalog/branches/` for worked examples.
- Memory `project_convergent_design_commons.md` — cross-domain structural-match framing.
