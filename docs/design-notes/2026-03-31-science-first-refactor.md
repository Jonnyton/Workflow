# Science-First Architecture Refactor — Research Synthesis

**Date:** 2026-03-31
**Purpose:** Document the research-backed choice for every major subsystem

---

## Addendum: Hybrid Retrieval Convergence (Cross-Session Input)

A parallel session researched the 2026–2030 industry convergence on hybrid
retrieval. Key findings integrated into Section 7.1:

1. **Three-layer cake is the emerging standard:** Knowledge graph (bottom) +
   vector embeddings (middle) + agentic router (top). No single method wins
   alone — each fails in a predictable, complementary way.

2. **Agentic retrieval router:** LLM decomposes compound queries into
   sub-queries routed to the right system. LlamaIndex 2026 benchmarks: +2
   correctness, +1.6 relevance vs traditional RAG. Tradeoff is latency.

3. **Epistemic access tiers on graph edges:** Critical for fiction with
   knowledge layering. Graph edges carry `access_tier` and `pov_characters`
   metadata so retrieval structurally enforces who-knows-what. A flat vector
   store can't do this.

4. **Vectorless reasoning (PageIndex pattern):** For structured content like
   canon docs with nested Parts I–VIII, skip embeddings entirely — use the LLM
   to reason over document structure. RAPTOR already provides this capability.

5. **Contextual memory > static RAG:** Systems should track the current writing
   position in the timeline and automatically scope what knowledge is
   "available" to the current POV. Our WorldState + epistemic filter achieves
   this.

---

## Decision Summary

For each subsystem, we evaluated 3-5 alternatives and selected the approach with
the strongest scientific grounding, cleanest implementation, and full
local-fallback capability.

---

## 1. Knowledge Graph & Retrieval — HippoRAG + nano-graphrag

### Alternatives Evaluated

| Approach | Tokens/Query | Accuracy | Cost | Local? |
|----------|-------------|----------|------|--------|
| Microsoft GraphRAG | 40,000 | 70%+ | Very High | Yes* |
| LightRAG | 10,000 | 68%+ | Low | Yes |
| RAPTOR | 5,000 | 72%+ | Medium | Yes |
| **HippoRAG** | **1,000** | **71%+** | **Very Low** | **Yes** |
| nano-graphrag | Same as GraphRAG | Same | High | Yes |

### Choice: HippoRAG core + RAPTOR tree for hierarchical queries

**Why:** HippoRAG (NeurIPS 2024) uses Personalized PageRank on a knowledge graph
to find semantically central entities — 6-13x faster than iterative retrieval,
comparable accuracy, 1/40th the tokens of full GraphRAG. For fiction, where
character relationships ARE the retrieval signal, PageRank on a relationship
graph is the theoretically cleanest approach.

**RAPTOR complement:** For hierarchical questions ("what are the themes across
books 1-3?"), RAPTOR's tree-structured summarization (NAACL 2024) outperforms
GraphRAG at 72%+ accuracy. Use RAPTOR for global synthesis, HippoRAG for
entity/relationship queries.

**Graph construction:** Leiden community detection (guaranteed well-connected
communities, 20x faster than Louvain). Entity extraction via LLM with
fiction-specific prompts for narrative relations (conflict, mentorship, betrayal,
knowledge boundary).

**Papers:**
- HippoRAG: arxiv.org/abs/2405.14831 (NeurIPS 2024)
- RAPTOR: arxiv.org/abs/2401.18059
- Leiden: doi.org/10.1038/s41598-019-41695-z

### What this replaces

Old plan had GraphRAG as a Phase 7 afterthought (`memory/graph_rag.py`). New
plan makes the knowledge graph **foundational** — built during Phase 1 alongside
the graph skeleton, because every node needs relationship-aware retrieval.

---

## 2. Constraint Synthesis — ASP Solver + HTN Planning + DOME Outline

### Alternatives Evaluated

| Approach | Mechanism | Grounding | Complexity |
|----------|-----------|-----------|------------|
| LLM-only (current) | Prompt chains | Weak | Low |
| **ASP (Clingo)** | **Constraint logic** | **Strong** | **Medium** |
| Full CSP (OR-Tools) | Backtracking solver | Strong | High |
| Ontology (OWL/RDF) | Semantic reasoning | Medium | High |
| **HTN Planning** | **Hierarchical tasks** | **Strong** | **Medium** |
| **DOME** | **Dynamic outline + KG** | **Strong (NAACL 2025)** | **Medium-High** |

### Choice: Three-layer neurosymbolic stack

**Layer 1 — ASP for world consistency** (Clingo solver). Encode world rules as
Answer Set Programs. The solver finds all valid world states and flags
contradictions. This replaces the ad-hoc "Creative Constitution" with formal
constraint logic.

Paper: "Guiding and Diversifying LLM-Based Story Generation via Answer Set
Programming" (arxiv.org/abs/2406.00554) — proven to improve both diversity AND
consistency vs pure LLM generation.

**Layer 2 — HTN for plot planning.** Hierarchical Task Networks decompose
"write epic fantasy" into acts → chapters → scenes with explicit preconditions
and effects. This replaces the Snowflake fractal expansion with a formally
grounded planner.

Paper: "Can LLMs Generate Good Stories? Insights from Narrative Planning"
(arxiv.org/abs/2506.10161) — validates that symbolic planning + neural
generation outperforms pure LLM for long-form coherence.

**Layer 3 — DOME for outline expansion.** Dynamic Hierarchical Outline with
Memory Enhancement (NAACL 2025) bridges sparse-to-rich input normalization.
Given even 2 sentences, it generates multi-level outlines with temporal KG
feedback for consistency.

Paper: arxiv.org/abs/2412.13575

### What this replaces

Old plan had an LLM-only Constraint Synthesis Engine (Section 9.5) with
Creative Constitution as 12 prompt rules, Snowflake expansion, and a genericity
detector. New plan replaces prompt-based constraint checking with formal ASP
solving, replaces Snowflake with HTN, and adds DOME's proven outline expansion.

The Creative Constitution's 12 rules become ASP constraints — provable, not
probabilistic.

---

## 3. Evaluation Ensemble — Structural Anchors + Debate + Swap-Verify

### Alternatives Evaluated

| Approach | Bias Reduction | Cost | Fiction Fit |
|----------|---------------|------|------------|
| Single LLM judge | Baseline | 1x | Poor |
| Swap-and-verify | 10-15% | 2x | Good |
| Independent ensemble | 15-20% | 3x | Good |
| **Multi-agent debate** | **25-30%** | **6-10x** | **Very High** |
| **Structural anchors** | **Deterministic** | **0.5x** | **High** |
| Reflexion loops | 15-25% per iter | 2-3x | Moderate |
| Constitutional AI | 20-30% | 1x+train | Medium-High |

### Choice: Three-tier evaluation

**Tier 1 — Deterministic structural analysis (run first, no LLM).** Readability
(TAACO coherence indices), pacing (scene length distribution,
dialogue-to-narration ratio), character tracking (coreference consistency),
Chekhov's Gun detection (introduced-but-unresolved elements), timeline
validation.

Paper: SCORE framework achieves 89.7% emotional consistency detection, 23.6%
higher coherence vs GPT-4 baseline (arxiv.org/abs/2503.23512).

**Tier 2 — Multi-family pairwise judges with swap-and-verify.** 2-3 models from
different families (Claude via `claude -p`, GPT-5.4 via `codex exec`, Llama via
Ollama). Pairwise comparison with position swapping. Elo-based ranking with
conservative tie handling.

Paper: "Language Model Council" (NAACL 2025) — cross-family ensembles reduce
correlated errors by 15-20%. Swap-and-verify: Wang et al. (IJCNLP 2024).

**Tier 3 — Multi-agent debate (on disagreement only).** When Tier 2 consensus
<70% on any critical dimension, judges enter structured debate sharing evidence
and counterarguments. Convergence check after each round.

Paper: ChatEval (ICLR 2024) — debate-based evaluation shows 8-15% better
alignment with human preferences on subjective tasks.

### What this replaces

Old plan had a simpler three-channel evaluation (structural, quality floor,
ensemble) without the debate escalation path or deterministic structural anchors
as a distinct tier. The new approach uses LLMs only where deterministic checks
can't reach, reducing cost while improving accuracy.

---

## 4. Memory Architecture — Letta-Inspired Hierarchical Memory

### Alternatives Evaluated

| Approach | Mechanism | Long-Running? | Local? |
|----------|-----------|--------------|--------|
| Simple vector store | Embedding search | Limited | Yes |
| LangGraph Store API | Namespaced docs | Yes | Yes |
| **Letta/MemGPT** | **OS-like virtual memory** | **Proven** | **Yes** |
| Reflexion memory | Verbal reflections | Yes | Yes |

### Choice: Letta-inspired three-tier memory

**Core memory** (immediate context window): current chapter state, active
character states, scene-level promises. Managed by LangGraph Store API with
namespaces.

**Episodic memory** (recent events): scene-by-scene summaries,
recently-extracted facts, style observations from last N chapters. Stored in
SQLite with vector index for similarity search.

**Archival memory** (entire universe): full knowledge graph (HippoRAG), world
rules (ASP constraints), character arcs across books, all promoted facts.
Stored in SQLite + LanceDB with Leiden community structure.

**Transition mechanism:** Facts flow core → episodic → archival through
promotion gates. Episodic→semantic distillation happens during chapter
consolidation (specific event → general pattern).

Paper: MemGPT (arxiv.org/abs/2310.08560) — unlimited context within fixed
windows through hierarchical memory management.

### What this replaces

Old plan had "three-tier memory" but it was retrieval-focused (LanceDB + BM25 +
graph). New plan adds the Letta insight: memory tiers aren't just storage
backends, they're cognitive layers with distinct access patterns and promotion
logic.

---

## 5. State Tracking — Explicit World State Model

### Key finding

"Can LLMs Generate Good Stories?" (2025) and StateAct (2024) both conclude:
**explicit state tracking is essential for coherent long-form generation.** LLMs
learn implicit state tracking but it's fragile and unreliable for long
sequences.

### Choice: Explicit StateTracker as a first-class node

Every scene update writes to a structured world state:
- Character locations, knowledge, emotional state, goals
- Timeline position
- Active promises and Chekhov's guns
- Magic system state (resources spent, effects active)

The StateTracker is a LangGraph node that runs after every scene commit,
updating the world state deterministically. The orient node reads this state
to project forward.

This replaces implicit state-in-context with explicit state-in-database.

Papers:
- StateAct: arxiv.org/abs/2410.02810
- LLM-State: arxiv.org/abs/2311.17406
- How Do LMs Track State?: arxiv.org/abs/2503.02854

---

## 6. LangGraph Architecture — 4-Level Nesting

### Key finding

5-level nesting (Universe → Series → Book → Chapter → Scene) is technically
possible but poorly supported for visualization and debugging. Production
systems use 2-4 levels.

### Choice: Collapse to 4 levels

```
Universe (top-level daemon)
  → Book (combines series-level and book-level logic)
    → Chapter (scene sequencing, consolidation)
      → Scene (orient → plan → draft → evaluate → commit)
```

Series-level logic (multi-book arcs) becomes conditional edges and state within
the Book graph rather than a separate nesting level. This keeps the clean
hierarchy while staying within proven nesting depth.

---

## 7. Streaming & Dashboard — Custom Events + Updates

### Choice: `stream_mode=["updates", "custom"]`

- `updates` for state deltas (what changed)
- `custom` for application events (scene started, word count, quality score)
- Desktop app subscribes to SSE stream

This is the standard production pattern per LangGraph docs.

---

## 8. Checkpointing — SqliteSaver + Retention Policy

### Choice: SqliteSaver for local-first, with explicit checkpoint pruning

PostgresSaver is production-standard but adds external dependency. Since Fantasy
Author runs as a desktop app (not a server), SqliteSaver with WAL mode is the
cleanest choice. Add explicit retention policy (keep last N checkpoints per
thread + all named checkpoints).

Schema evolution: Design state with Optional fields from day one. Add custom
migration logic before `.setup()` for version bumps.

---

## Build Order Impact

The knowledge graph is no longer a late-phase feature. New build order:

1. **Graph Skeleton + State Types** — LangGraph topology, TypedDict state, 4-level nesting
2. **Knowledge Graph Foundation** — Entity extraction, Leiden communities, HippoRAG retrieval
3. **Provider Layer + Real Nodes** — `claude -p`, `codex exec`, fallback chains, basic generation
4. **Structural Evaluation** — Deterministic checks (TAACO, pacing, Chekhov's Gun, timeline)
5. **World State Tracker** — Explicit state model, consistency checking
6. **ASP Constraint Engine** — Clingo integration, world rules as logic programs
7. **HTN Planner + DOME Outline** — Premise normalization, hierarchical outline expansion
8. **LLM Evaluation Ensemble** — Multi-family judges, swap-verify, debate escalation
9. **Learning System** — Reflexion memory, style rule promotion, calibration
10. **Desktop App + Progressive Ingestion** — Daemon, tray, streaming, massive source handling
