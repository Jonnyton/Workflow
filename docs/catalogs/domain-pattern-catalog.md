# Domain-Pattern Catalog — v1

**Status:** v1. Third axis in the node/workflow taxonomy trio, complementing `node-type-taxonomy.md` (what a node IS) + `integration-patterns.md` (how nodes COMPOSE).
**Purpose:** catalog recurring patterns that emerge across multiple unrelated domains. These are the load-bearing cross-domain matches the chatbot surfaces via `discover_nodes` when `cross_domain=true`. Catching them explicitly makes remix natural.
**Audience:** chatbot (primary — pattern-matches user intent onto a domain-pattern + suggests existing nodes that implement it); contributor (secondary — vocabulary for describing cross-domain similarity in PR discussions).
**Licensing:** CC0-1.0.

---

## 1. Why domain patterns

`discover_nodes` (spec #25 §3.1) returns candidates ranked by semantic + structural match. Structural match catches "same shape" across domains — but only when the shape is explicit. **Domain patterns name the shapes that recur** so the chatbot can reason "this user's invoice-OCR problem is shape-compatible with a research-paper-metadata node + a recipe-ingredient-list node."

**The key insight:** at Wikipedia-scale workflow design (per `project_convergent_design_commons.md`), users don't know their problem matches other domains. The chatbot's job is to **match on pattern, surface cross-domain precedent, guide remix decisions**. The domain-pattern catalog is the vocabulary that makes that matching possible.

---

## 2. Core patterns

Each pattern has: **description**, **when to apply**, **node-types that compose it** (per node-type-taxonomy), **real-world nodes across domains** that implement the pattern.

### 2.1 Extract-structure-from-document

**Description:** Input is an unstructured or semi-structured document (text, PDF, image). Output is typed JSON with specific fields extracted. Almost always involves an extractor node per the type taxonomy; often paired with a validator.

**When to apply:** user has documents + needs to pull specific data out of them for downstream automation or analysis. Classic "make the document machine-readable" flow.

**Composing node-types:** extractor (§2.2 in node-taxonomy) + optional validator (§2.3) + optional transformer (§2.4) for output-format normalization.

**Cross-domain examples:**
| Domain | Node(s) that implement | Notes |
|---|---|---|
| Accounting | `invoice-ocr.yaml` — invoice number from OCR'd text | Extractor pattern, regex + fallback LLM. |
| Research | (hypothetical) `paper-metadata-extractor` — title, authors, abstract, DOI from PDF | Same pattern, different input domain. |
| Recipes | (hypothetical) `ingredient-list-extractor` — ingredient + quantity + unit from recipe text | Same pattern, domain-specific units. |
| Legal | (hypothetical) `contract-clause-extractor` — named clauses from contract PDF | Same pattern, pattern-matches on legal structure. |

**Chatbot-use cue:** when user says "I have [documents] and I need to get [structured field] out of them," walk §2.1 — the node pattern they need already exists in some domain.

### 2.2 Iterative-refine

**Description:** Input is a draft; output is an improved version. The refinement loop runs N times (often evaluator-gated). Each iteration is a transformer that doesn't add substance, only tightens.

**When to apply:** user has initial output but wants quality-improvement. Classic "draft → critique → revise" loop.

**Composing node-types:** generator (§2.1 for the initial draft — often upstream) + transformer (§2.4 for refinement) + evaluator (§2.9 for quality gate) + router (§2.5 for accept-vs-iterate decision). This matches the eval-loop integration pattern (integration-patterns.md §2.3).

**Cross-domain examples:**
| Domain | Node(s) |
|---|---|
| Fantasy writing | `fantasy-scene-refinement.yaml` — refine scene draft against focus areas, preserve voice |
| Research | (hypothetical) `paper-paragraph-refiner` — tighten prose, strengthen argument, match journal style |
| Code | (hypothetical) `code-review-suggester` — lint output feeds into LLM-refine suggestions |
| Journalism | (hypothetical) `article-pacing-editor` — cut slack, improve flow, match outlet voice |

**Chatbot-use cue:** when user says "this is okay but not great, can you make it better," walk §2.2 — probably an iterative-refine pattern, probably needs an evaluator node too.

### 2.3 Multi-variant-generation

**Description:** Input is a single specification; output is N alternative implementations or paths. User picks or the system chooses. A generator that branches.

**When to apply:** user wants options rather than a single answer. Classic "brainstorm" or "give me options" flow. Also: A/B testing, hypothesis enumeration, alternative recipes.

**Composing node-types:** generator (§2.1) with a branching factor parameter, often followed by an aggregator (§2.7) for comparison, or a router (§2.5) for automated selection.

**Cross-domain examples:**
| Domain | Node(s) |
|---|---|
| Research | `research-hypothesis-generator.yaml` — produces 3-5 ranked hypotheses per topic |
| Fantasy | (hypothetical) `alternate-chapter-endings` — N different narrative conclusions for user selection |
| Recipes | `recipe-scaler.yaml` (adjacent pattern — variant by scale) + (hypothetical) `ingredient-substitution-generator` — N alternatives for dietary constraints |
| Product | (hypothetical) `headline-variant-generator` — 5 variants per specification for A/B testing |

**Chatbot-use cue:** user says "give me options" / "what are the alternatives" / "explore possibilities" — §2.3 pattern, chatbot may want to surface existing generator + ask user how many variants.

### 2.4 Publish-to-external

**Description:** Finalized output → external system. Irreversible (or at best async-reversible). The canonical real-world-handoff. Explicit consent required each invocation per privacy-catalog §7.7.

**When to apply:** workflow has produced something ready for outside consumption. End-of-pipeline.

**Composing node-types:** side-effecter (§2.8) + often a validator (§2.3) upstream for format-compliance + optional consent-gate router (§2.5).

**Cross-domain examples:**
| Domain | Node(s) |
|---|---|
| Email | `email-sender.yaml` — send email via owner's provider |
| Research | `research-paper-peer-review-prep.yaml` (orchestrator level; includes arXiv/journal push at the end) |
| Accounting | `invoice-payables.yaml` (orchestrator level; pushes to Voyager/QuickBooks) |
| Code | (hypothetical) `github-release-publisher` — push release notes + artifacts |
| Writing | (hypothetical) `blog-post-publisher` — push to WordPress/Ghost/Substack |

**Chatbot-use cue:** user workflow terminates in "send to [external system]" — §2.4 pattern, chatbot must surface **explicit consent step** before invocation (cross-ref privacy catalog §7.7 real-world-handoff).

### 2.5 Query-and-synthesize

**Description:** Input is a natural-language question. Output is an answered response synthesized from a corpus or external source. Search + synthesis, usually.

**When to apply:** user asks "what's known about X" / "summarize the recent work on Y" / "find me examples of Z."

**Composing node-types:** retriever (§2.6) + aggregator (§2.7) + optional evaluator (§2.9) for confidence-scoring.

**Cross-domain examples:**
| Domain | Node(s) |
|---|---|
| Research | (hypothetical) `literature-review-synthesizer` — pulls prior work + synthesizes findings |
| Legal | (hypothetical) `case-law-summarizer` — retrieves precedent + synthesizes applicable rulings |
| Product | (hypothetical) `customer-feedback-synthesizer` — retrieves support tickets + synthesizes trends |
| Generic | `semantic-document-retriever.yaml` — the retrieval half (synthesis pairs separately) + `multi-source-synthesizer.yaml` — the synthesis half |

**Chatbot-use cue:** user asks an open question that needs sources — §2.5 pattern, chatbot may need both a retriever + a synthesizer and can compose them into a single run.

### 2.6 Gate-on-judgment

**Description:** A decision node that halts or routes a workflow based on a quality or policy judgment. Often LLM-judged, sometimes rule-based. Distinct from iterative-refine because it's a one-shot verdict, not a loop.

**When to apply:** workflow needs approval / compliance check / safety gate before proceeding. "Should this proceed?" questions.

**Composing node-types:** evaluator (§2.9) + router (§2.5). Often with escalation path to human review (connects to moderation spec #36).

**Cross-domain examples:**
| Domain | Node(s) |
|---|---|
| Code | `code-lint-validator.yaml` — passes/fails on lint + routes accordingly |
| Moderation | (see `moderation_rubric.md` — the whole rubric is a gate-on-judgment system) |
| Fantasy writing | `scene-quality-evaluator.yaml` — accept / second-draft / revert verdict + routes |
| Accounting | (in `invoice-payables.yaml`) — auto-post-threshold gate routes above-threshold to human review |

**Chatbot-use cue:** user says "only proceed if [criterion]" — §2.6 pattern. Always confirm the escalation path for gates-that-fail.

### 2.7 Fan-out-orchestrate

**Description:** Top-level orchestrator runs N sub-workflows in parallel over a collection of inputs, then aggregates. Your task description's "fan-out" shape (Scenario C4).

**When to apply:** user has a batch of inputs + wants each processed independently, then consolidated. "Do this for each of these X things."

**Composing node-types:** orchestrator (§2.10) + N × (any type, usually generator or transformer) + aggregator (§2.7).

**Cross-domain examples:**
| Domain | Node(s) |
|---|---|
| Accounting | `invoice-batch-processor.yaml` BranchDefinition — N invoices processed independently, results aggregated |
| Research | (hypothetical) `multi-dataset-analysis-orchestrator` — same analysis across multiple datasets |
| Writing | `chapter-scene-orchestrator.yaml` — though this is sequential not parallel; fan-out-orchestrate would be the book-level equivalent running multiple chapter loops |
| Media | (hypothetical) `batch-image-processor` — same transform across N images |

**Chatbot-use cue:** user has a plural input ("all of these documents," "each of these items") — §2.7 pattern. Chatbot can propose a fan-out orchestrator vs sequential loop based on whether items are independent.

### 2.8 Dry-run / simulate

**Description:** Runs a workflow conceptually without real external effects. Useful for validation, cost estimation, exploration. Every side-effecter has a dry-run twin or flag.

**When to apply:** user wants to preview what a workflow would do before invoking the real thing. High-stakes flows (real-world handoffs) especially need this.

**Composing node-types:** mirror of the real workflow but with side-effecters replaced by dry-run stubs. Often a single flag on the orchestrator (`dry_run: true` threads through and each side-effecter checks the flag).

**Cross-domain examples:**
| Domain | Implementation |
|---|---|
| Accounting | Invoice pipeline in dry-run returns the CSV + routing decisions without posting to Voyager. |
| Research | Peer-review-prep orchestrator in dry-run produces the revised draft + submission package, but does NOT call arXiv/journal connector. |
| Email | Email-sender in dry-run logs the "would send" payload without calling the provider API. |
| Cost | Paid-request submission in dry-run returns the estimated cost without reserving funds. |

**Chatbot-use cue:** user says "what would this do" / "show me the result without actually doing it" / "preview first" — §2.8 pattern. Chatbot should ALWAYS offer dry-run for any workflow containing publish-to-external (§2.4).

---

## 3. How to apply this catalog

### 3.1 Chatbot reasoning at design time

When a user describes their workflow need:
1. Identify which §2 patterns match the description.
2. Query `discover_nodes` with the pattern name as a tag or filter.
3. Surface existing implementations across domains — even far-field ones; convergent patterns often produce unexpectedly-useful cross-domain matches.
4. Propose: "this is pattern X; here are 3 existing implementations you could remix from; or we can design from scratch."

### 3.2 Contributor use at authoring time

When authoring a new node or branch:
1. Tag the artifact with `primary_pattern: <name>` in YAML frontmatter.
2. Reference sibling artifacts that implement the same pattern.
3. If your artifact creates a new pattern not here, propose a §2.X addition via PR.

### 3.3 Discovery integration

`discover_nodes` (per #25 §3.1) learns from the `primary_pattern` column if we add it to the schema. Extension to consider:

```sql
ALTER TABLE public.nodes
  ADD COLUMN primary_pattern text
    CHECK (primary_pattern IN (
      'extract-structure-from-document', 'iterative-refine',
      'multi-variant-generation', 'publish-to-external',
      'query-and-synthesize', 'gate-on-judgment',
      'fan-out-orchestrate', 'dry-run-simulate'
    ));
CREATE INDEX nodes_primary_pattern ON public.nodes (primary_pattern);
```

Matches `integration-patterns.md §4` which added `branches.primary_pattern`. Node-level + branch-level pattern tagging gives the chatbot a complete shape-picture of any candidate.

---

## 4. Relation to the other two catalogs

Three orthogonal axes describing any workflow artifact:

| Catalog | Question | Example values |
|---|---|---|
| **node-type-taxonomy** | What does this node DO? | generator / extractor / validator / evaluator / ... |
| **integration-patterns** | How do nodes COMPOSE in a branch? | chain / fork-join / eval-loop / router-split / ... |
| **domain-patterns** (this doc) | What recurring PROBLEM-SHAPE does this workflow solve? | extract-structure-from-doc / iterative-refine / publish-to-external / ... |

A node or branch can be described along all three axes. Example: `invoice-payables.yaml` is **orchestrator** (node-type) implementing **fan-out-orchestrate + publish-to-external** (domain-patterns) in a **router-split** (integration-pattern) branch.

---

## 5. OPEN flags

| # | Question |
|---|---|
| Q1 | Multi-pattern artifacts. Some workflows implement 2+ domain patterns in sequence. Tag as `primary_pattern` + `secondary_patterns[]`? |
| Q2 | Pattern extensibility. Community-proposed new patterns via PR, or fixed v1 list? Recommend PR-extensible (unlike integration-patterns which should stay compact; domain-patterns legitimately grows with the commons). |
| Q3 | Pattern-ranking in `discover_nodes`. When user intent matches multiple patterns, which ranks higher in candidates? Recommend: rank by semantic+structural match score; pattern is a filter not a ranking signal. |
| Q4 | Cross-pattern mapping. Some domain patterns "live inside" others (dry-run wraps any other pattern). Express as tag or composition? v1 as tag; v2 if composition UX warrants. |

---

## 6. References

- Node-type taxonomy — `docs/catalogs/node-type-taxonomy.md` (sibling axis).
- Integration patterns — `docs/catalogs/integration-patterns.md` (sibling axis).
- Privacy catalog — `docs/catalogs/privacy-principles-and-data-leak-taxonomy.md` §7.7 for publish-to-external consent requirements.
- Schema spec #25 §3.1 `discover_nodes` RPC — this catalog feeds the matching logic.
- Convergent-commons memory — `project_convergent_design_commons.md` — the Wikipedia-scale framing this catalog serves.
