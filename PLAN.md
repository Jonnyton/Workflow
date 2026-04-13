# Workflow - Plan

How the project should work and why. Architecture, principles, and design
decisions. One source of truth - if it is about how the system works, it is
here.

For live state, see STATUS.md. For how to work on the project, see AGENTS.md.

Changes require user approval. When behavior contradicts an assumption here,
raise it as a STATUS.md Concern - do not implement the conflicting approach.

---

## Project Thesis

**Workflow is a global goals engine.** Humanity declares shared Goals —
research breakthroughs, great novels, successful prosecutions, cures, open
datasets, whatever people actually want done in the world — and a legion of
diverse AI-augmented workflows pursues each Goal in parallel. Branches
evolve, cross-pollinate, and get ranked by how far their outputs advance up
each Goal's real-world outcome-gate ladder (drafts → reviewed → shipped →
impact). The system's value is not one best workflow per Goal; it's the
evolving ecology of many workflows all chasing the same real-world outcomes
and learning from each other's wins.

Fantasy writing is the first playful benchmark branch for a specific
question inside that frame: what design principles produce truly
intelligent, iterative, self-improving agent workflows that many people can
shape together?

Fantasy is not the trunk. It is one early branch that happens to be fun,
social, rich in structure, easy to publish, and useful for stress-testing
memory, continuity, collaboration, and long-horizon evaluation.

The real abstraction is an open workflow playground, multiplayer daemon
platform, and research lab for long-horizon agents. The system should:

- maintain explicit state across many cycles
- search and manage memory across multiple backends
- use tools instead of relying on one giant prompt
- separate generation from evaluation and environmental truth
- learn through durable artifacts, not hidden chat context
- coordinate work across multiple timescales, many users, and many daemons
- let users conversationally design and reshape workflow/state architecture
- connect workflows to real tracked outcomes in the world, not only text output
- evolve its own workflows as models, research, and community practice improve

The long-term aim is not just better writing. It is a scientifically useful,
socially shareable, open-source system for discovering the cleanest workflow
for a given task and making workflow/state design accessible to non-experts.
The surface should be playful enough to spread socially and rigorous enough
that labs, companies, and other institutions can use it seriously.

The system should get simpler as models improve. Every scaffold is temporary
unless evals prove it still earns its keep.

---

## Cross-Cutting Principles

### Agentic Hybrid Search Is Memory

Durable memory is not one store. It is a policy over multiple stores and
query styles: knowledge graph traversal, vector similarity, hierarchical
summaries, notes, world-state queries, and direct tool calls.

No single retrieval backend should own truth. The system should route each
question to the right mechanism and merge results into a working set.

### Context Is a Managed Working Set

Prompts are not the source of truth. Prompts are lossy projections over
durable state, retrieved evidence, and recent artifacts.

The right goal is not "pack more context into the model." The goal is "give
the model the smallest high-signal working set needed for the current step."

### Workflow State Transitions Are the Core Abstraction

The primary abstraction is not "scene generation." It is explicit state
transition through orient, plan, draft, commit, learn, reflect, worldbuild,
and higher-level task selection.

If the state model is wrong, the system will feel smart in isolated prompts
and brittle across long runs.

### Every Scaffold Is a Falsifiable Hypothesis

Counters, thresholds, hard phase boundaries, routing rules, and helper
modules all encode a claim about model weakness.

- Before adding a component, prove the simpler approach fails.
- Before defending existing complexity, prove removing it makes things worse.
- When a stronger model lands, re-test the harness.
- The system should trend toward less prescriptive control over time, not more.

### Harness Design Is Part of the Cognition Stack

Harnesses are not wrapper code. Initializers, traces, browser harnesses,
replayable tests, dashboards, status files, artifact stores, and task logs
materially change what the system can do.

Prompt quality matters. Harness quality matters more once tasks become long,
stateful, and tool-driven.

### Tools Are the Agent-Computer Interface

Tool shape is architecture. Tool names, parameters, return schemas, failure
semantics, and discoverability directly determine agent competence.

The system should prefer a smaller number of reliable, composable tools over
many overlapping tools with ambiguous responsibilities.

### Generator, Evaluator, and Ground Truth Must Stay Separate

Self-evaluation bias is real. Generation, critique, and environmental
verification should remain separate channels and often separate model
families.

The evaluator does not need to be a better creator. It needs to be an
independent reader or checker with a different failure profile.

### Workflow States Must Live on Multiple Timescales

Scene, chapter, book, and universe are not only story concepts. They model
different operational horizons:

- scene: short-horizon action
- chapter: medium-horizon consolidation
- book: longer-horizon recovery and planning
- universe: global maintenance, synthesis, and strategy

The hierarchy should exist because the timescales differ, not because fiction
traditionally has chapters.

### Learning Is Write-Back Compression

Agents do not improve by hoarding transcripts. They improve by promoting
stable lessons into reusable artifacts: notes, style rules, craft cards,
facts, summaries, constraints, and revised tools or prompts.

Learning should compress repeated experience into better future behavior.

### Evals Must Grade Process and Outcome

Final output quality is not enough. The system also needs to inspect:

- retrieval choices
- tool usage
- stopping behavior
- handoff quality
- grounding quality
- artifact quality

When a run fails, traces and artifacts should explain why.

---

## Design Decisions

Cross-cutting facts that govern the system. Not module-specific - these apply
everywhere.

- **Universe = single consistent reality.** Time periods within a universe
  share one timeline. Alternative realities are separate universes with
  divergent facts. Only hard boundary is data isolation between universes.
- **Upload provenance.** The client tags each upload with a short description
  (for example "published book" or "rough notes"). The writer uses those
  tags to weight how seriously to treat each canon source.
- **Unified notes.** All feedback arrives as timestamped attributed notes on
  files. One system, one format, one durable store per universe.
- **Writer self-indexes.** The writer produces entity and fact data when it
  commits its own work. No separate extraction role is the desired end state.
- **Editorial feedback, not scoring.** The editor returns natural-language
  notes about what is working, what is concerning, and whether a concern is
  provably wrong or possibly intentional. No numeric rubric is the core loop.
- **Graph hierarchy is scaffolding.** Universe/book/chapter/scene structure
  should emerge from the daemon's choices wherever possible, not from fixed
  counters. Hard boundaries exist only where they clearly earn their keep.
- **Two review gates, one target registry.** The daemon first runs a
  foundation-priority review that hard-blocks only on unsynthesized uploads in
  v1, then an authorial-priority review that may choose any justified work in
  the universe.
- **Universe server, not single-user daemon.** A host machine runs the server
  with its own subscriptions and local models, while many named users connect
  through MCP-compatible clients to the same shared backend.
- **Workflow-first, domain-agnostic identity.** The project is a workflow
  engine and multiplayer daemon platform first. Fantasy authoring is an early
  benchmark domain, not the trunk or permanent center of gravity.
- **Open workflow playground.** The system should be open-source, social,
  remixable, and eventually viral to share: a place where many users and
  daemons co-design workflows, state architectures, and tracked outcomes.
- **Playful surface, serious utility.** The same system should be fun enough
  to spread socially and rigorous enough that labs, companies, and other
  institutions can use it as workflow infrastructure and research
  instrumentation.
- **MCP clients, local host dashboard.** Everyone uses the same MCP tool
  surface for normal collaboration, but host-only operational controls should
  live in a locally run dashboard rather than the shared client interface.
- **One host tray, many dashboards.** The local desktop companion should use a
  shared host tray as a lightweight entry point, while each live universe keeps
  its own host dashboard window. Detached tray/runtime objects must be guarded
  against duplicate starts.
- **Private chats, public actions.** User conversations remain private, but
  any action that affects a universe must be publicly attributable and
  inspectable in an action ledger.
- **Daemons are the public agent identity.** The system should stop centering
  "Author" as the general term. A daemon is a summonable, forkable public
  agent identity defined by durable behavior/soul files. Soul-file changes
  create new forked daemons rather than overwriting an existing identity.
- **Branch-first collaboration.** Branches are first-class, long-lived, and
  public-forkable by default. Reconciliation is optional, not forced. The
  default universe mode has no fixed mainline.
- **Swarm runtime.** There is no universe-wide single active daemon. Runtime
  capacity and daemon identity are separate: users may strongly prefer a
  daemon for a branch or task, while admins decide whether to provision more
  live runtime instances.
- **User-controllable state architecture.** Complete control of state should
  not be trapped behind a few product features. Users should eventually be able
  to inspect, steer, and redesign workflow/state structure conversationally.
- **Multi-host is the destination.** Local-host operation is important, but
  the end-state is a network of hosts where people contribute local or paid
  model capacity to summon daemons into shared projects.
- **The system must evolve itself.** The worst failure mode is stagnation. The
  workflow, memory policy, retrieval approach, evaluation harness, and naming
  should all be built to learn from research, runtime evidence, and outcomes
  over time.
- **Work targets are the unit of intentional work.** A work target is any
  locus the daemon may deliberately work on next: uploads, canon repair,
  world notes, plans, books, chapters, scenes, stories, or future outward
  artifacts.
- **Tags stay loose; role and lifecycle stay guarded.** Most tags remain
  daemon-defined and flexible. Publishable-vs-notes role, publish stage, and
  true discard are stronger state transitions with explicit rules.
- **Context is tools, not pre-assembly.** The writer should query canon, KG,
  notes, world state, and memory through tools. Pre-assembled context is a
  transitional compromise, not the target architecture.
- **Bad decisions are data.** When the daemon makes a poor choice, improve
  goals, tools, state visibility, or evals. Do not reflexively add rules.
- **Scene commits produce structured packets alongside prose.** Every
  accepted scene emits a validated JSON packet (facts, promises, entities,
  POV, position, world-state deltas) persisted next to the prose file. The
  packet stream is the backbone for timeline ledgers, promise tracking,
  continuity validation, and typed retrieval. Packets consolidate what the
  commit pipeline already extracts into one durable artifact per scene.
  (User-approved 2026-04-10, unifying BettaFish IR research and runtime
  fiction memory graph initiative.)
- **Durable artifacts outlive context windows.** Plans, notes, checkpoints,
  logs, learned heuristics, and subagent outputs belong in external storage.
- **Human control belongs at irreversible boundaries.** Let agents run inside
  bounded loops, but keep pause, stop, takeover, and high-risk confirmations
  at the system edge.
- **Engine is infrastructure, not topology.** The workflow engine is a library
  of shared infrastructure (providers, memory, retrieval, evaluation,
  checkpointing, notes, work targets, API scaffolding) with optional
  orchestration profiles. Each domain owns its own graph topology. The
  4-level hierarchy (scene/chapter/book/universe) is one reusable profile,
  not the engine contract. Domains may use it, extend it, or ignore it.
  (Resolved from D1.)
- **Contract convergence before extraction.** No package moves until the
  live contracts are stable: work_targets.py restored, notes.py aligned,
  multiplayer API wired, desktop tray repaired, steering residue removed,
  and full test suite passing. (Resolved from D2.)
- **Memory interface is query semantics, not tier names.** The three-tier
  model (core/episodic/archival) is the conceptual architecture. The public
  interface is deferred until semantics (scope, temporal truth, supersession,
  promotion) are stable and pressure-tested by a second domain. Memory
  queries should feel like faceted search, not storage-tier addressing.
  (Resolved from D3.)
- **Domain names stay until a second domain earns neutral names.** Fantasy
  Author keeps scene/chapter/book/universe in its own graph. Only shared
  `workflow/` infrastructure uses domain-agnostic names (which it already
  does). A mapping table documents the generalized intent. (Resolved from
  D4.)

---

## System Shape

```text
Users / Hosts
    <->
MCP-compatible clients / Host dashboard
    <->
FastAPI + Universe Server (MCP) control plane
    <->
Daemon (LangGraph)
    |
    +-----------+---------------+---------------+
    |           |               |               |
State/Artifacts Search/Tools  Evaluation    Providers
    |
Harness / Traces / Tests / Coordination
```

The daemon writes autonomously. MCP-compatible clients and the local host
dashboard are the primary user-facing interfaces. Communication remains primarily file-based and artifact-based:
the daemon writes to disk, the API and MCP surfaces expose state and actions,
and the harness inspects the resulting artifacts and traces.

The project itself mirrors this architecture. AGENTS.md, PLAN.md, STATUS.md,
notes.json, checkpoints, logs, and test artifacts are part of the same design
philosophy.

---

## Multiplayer Daemon Platform

**Goal:** Turn the project into a host-run universe/workflow platform where
many named users and many daemons can collaborate without collapsing into one
shared chat or one hidden runtime.

**Principle:** Separate identity from runtime. Daemons are public, forkable,
summonable agent identities defined by soul files; live runtime instances are
resource allocations bound to providers and models.

**Defaults:**

- host-run server with named user accounts
- private per-user MCP sessions
- shared MCP tool contract for all users
- local per-universe host dashboard whenever that universe has a live daemon
- public, attributable universe-affecting actions
- public read + public fork for universes
- no fixed mainline by default
- long-lived branch coexistence
- admin-gated additional runtime capacity
- quick user votes for daemon forks
- future multi-host participation with user-contributed local or paid model
  capacity used to summon daemons

**Host Admin Surface:** The host should get a locally run dashboard for every
universe with a live daemon/runtime. That dashboard is the operational control
plane: live feed, runtime state, alerts, branch/work-target visibility, and
host or delegated-admin controls. MCP clients remain the shared collaborative
surface for users rather than the host operations console. The desktop tray is
the companion surface, not a second control plane: one shared host tray should
aggregate live universes and open their dashboards instead of spawning one tray
icon per runtime.

**Storage:** Contested multiplayer state should live in SQLite-backed source of
truth. Filesystem artifacts remain important for prose, canon artifacts,
exports, and human inspection, but not for concurrency-critical coordination.

**Connects to:** API auth/session handling, action ledger, daemon registry,
branch management, vote windows, runtime registry, notes/work-target
concurrency, and future cross-host import/export.

---

## State And Artifacts

**Goal:** Make long-horizon reasoning legible, durable, and inspectable.

**Principle:** Strong agents run on explicit typed state and external
artifacts, not on hidden chat memory. TypedDict state, checkpoints, notes,
world-state databases, logs, and output files should carry the load that a
single prompt cannot.

**Assumption:** Explicit state contracts outperform ad hoc prompt state. If
state shapes drift or artifacts become untrustworthy, the system will look
smart locally and fail over time.

**Connects to:** LangGraph state, SqliteSaver checkpointing, notes.json,
world_state DB, activity.log, output files, AGENTS.md/PLAN.md/STATUS.md.

---

## Daemon-Driven

**Goal:** Let the daemon make creative and structural decisions whenever the
model can reliably do so.

**Principle:** Hardcoded thresholds, counters, and rigid stage gates are
scaffolding. Test each one by removing it and observing whether quality
actually degrades.

This applies everywhere:

- structural boundaries
- context assembly
- revision decisions
- canon evolution
- self-correction
- upload synthesis
- task sequencing

When the daemon makes a bad decision, that is data - improve the goal,
context, tools, or evals rather than layering on recipes.

---

## Scene Loop

**Goal:** Produce one unit of work that is grounded, coherent, ambitious, and
able to improve through external feedback.

**Principle:** Orient -> plan -> draft -> commit is a useful loop only if each
step adds real value. The purpose of the loop is not ritual. It is to create
better action, better context use, and better revision pressure.

**Assumption:** Separate orient/plan/draft/commit phases still help more than
they constrain. If a stronger model with better tools can do equivalent work
in fewer steps, flatten the loop.

**Connects to:** Retrieval + Memory + Notes during orientation, external
evaluation during commit, write-back into world state and learned artifacts.

---

## Workflow Hierarchy

**Goal:** Put the right operations at the right timescale.

**Principle:** The hierarchy exists to separate timescales, not to worship
fiction structure. Scene-level work is local action. Chapter-level work is
consolidation. Book-level work is recovery and longer planning. Universe-level
work is maintenance, synthesis, and global strategy.

**Assumption:** Scene and universe levels clearly earn their keep. Chapter and
book layers must justify any hard routing logic they impose. If counters are
not improving coherence, remove them.

**Connects to:** Universe task selection, worldbuild, reflection, chapter
consolidation, learning, and stuck recovery.

---

## Work Targets And Review Gates

**Goal:** Let the daemon choose the next most justified locus of work instead
of collapsing the universe into a flat task queue.

**Principle:** One unified work-target registry should represent everything
the daemon may intentionally work on next. Two review gates operate over that
same registry:

- foundation-priority review
- authorial-priority review

Foundation review is structured and conservative. In v1 it hard-blocks only
on unsynthesized uploads, while recording soft conflicts such as
canon/timeline/source reconciliation debt for later resolution. Authorial
review is freer: once hard blockers are clear, it may choose any justified
authorial move, including note-side exploration, comparison work, planning,
revision, or outward-facing writing.

**Work target core**

- target_id
- title
- home_target_id
- role: notes | publishable
- publish_stage: none | provisional | committed
- lifecycle: active | paused | dormant | complete | superseded |
  marked_for_discard | discarded
- current_intent
- tags
- artifact_refs
- note_refs
- linked_target_ids
- timeline_refs
- lineage_refs

**Guardrails**

- Targets usually have one current home, but may be rehomed later.
- The overall registry is still a web of links, not a strict tree.
- Most relationships stay loose in notes/tags rather than a rigid ontology.
- notes -> publishable must always pass through provisional first.
- Provisional publishable targets must do real alignment or revision work
  before becoming committed publishable artifacts.
- publishable -> notes is allowed, but may emit reconciliation work if the
  content no longer fits its new role.
- marked_for_discard is not the same as discarded. True discard is a later
  review decision that removes the target from normal daemon access while
  keeping it recoverable for development and UI revival.

**Assumption:** A thin live cursor over a durable target/artifact field will
scale better than a queue-first scheduler with large inherited state bags.

**Connects to:** Universe scheduling, notes, upload synthesis, timeline
maintenance, revision routing, and future API/MCP inspection tools.

---

## Retrieval And Memory

**Goal:** Ground every decision in the best available evidence without flooding
the model with irrelevant context.

**Principle:** Retrieval and memory are one system. The working set may come
from:

- knowledge graph traversal for entities, relationships, and epistemics
- vector retrieval for semantic similarity, tone, and local analogies
- RAPTOR or other hierarchical summaries for global context
- world-state DB queries for promises, timeline, and continuity
- notes and learned artifacts for intent and reflection
- direct tool use when the daemon needs to ask a focused question

The routing policy is more important than any individual backend.

**Assumption:** Hybrid routing beats single-backend retrieval, and durable
memory tiers beat flat transcript stuffing. If the writer is still mostly fed
pre-assembled blobs, this architecture is not finished. Current implementation
is transitional: explicit writer tools and shared search context exist, but
orient/plan/draft still carry compatibility `retrieved_context` and
`memory_context` fields while tool-driven context takes over.

**Connects to:** Writer self-indexing on commit, promotion gates, worldbuild,
notes, and tool-driven context retrieval.

---

## Evaluation

**Goal:** Improve quality through feedback, not through brittle gates.

**Principle:** Evaluation is a layered system:

- deterministic checks for provable failures
- an editorial reader for natural-language critique
- environment-grounded artifacts and traces for verification

One strong independent reader is better than a committee of shallow scorers.

**Assumption:** Natural-language editorial feedback produces better revision
and learning than numeric scores. If revision quality does not improve,
upgrade the evaluator or artifact flow before adding more scoring machinery.

**Connects to:** Commit, notes, world-state updates, learning, quality traces,
and future eval harnesses.

---

## Constraints

**Goal:** Formally verify world rules only where symbolic checking clearly adds
value.

**Principle:** Neurosymbolic methods are optional leverage, not mandatory
complexity. Use ASP or other formal systems when the rules are clear,
important, and difficult for an LLM-only reader to verify reliably.

**Assumption:** Formal constraints must prove they catch meaningful failures.
Generic boilerplate constraints are not enough. Universe-specific rules are
the only version likely to earn ongoing complexity.

**Connects to:** Structural evaluation, worldbuild, and any future
constraint-synthesis pipeline.

---

## Providers

**Goal:** Keep the system running and preserve role separation without hiding
provider failure.

**Principle:** Pick the best provider per role, then use fallback chains and
parallel diversity where they improve resilience or independence. Error loudly
when the remaining provider cannot produce acceptable work.

**Assumption:** Fallbacks degrade gracefully. If the last-resort provider
produces unusable output, failure is better than fake success.

**Connects to:** Writer, editor, extraction, embeddings, judge diversity, and
quota or cooldown management.

---

## API And MCP Interface

**Goal:** Let the user steer the daemon through natural conversation and MCP
tooling without letting any chat surface become the author.

**Principle:** Any MCP-compatible client is a control station, not a creator.
The Universe Server MCP surface is the primary public interface. The API
exposes state and actions. The daemon performs the actual creative and
structural work. If a chat surface writes story content itself, that indicates
a missing daemon path. (The Custom GPT was an early control surface, now
superseded by MCP.)

**Assumption:** File-based and artifact-based communication is sufficient.
Real-time streaming is optional if status, logs, notes, and outputs remain
legible and current, though MCP/Universe Server streaming is now a real
first-class public interface rather than a hypothetical future add-on.

**Connects to:** notes API, universe selection, canon uploads, daemon control,
status inspection, Universe Server MCP tool schemas, and MCP registry listing.

---

## Distribution And Discoverability

**Goal:** Make the project installable and discoverable across standard MCP
surfaces, Anthropic packaging surfaces, and future Conway packaging without
changing the portable core architecture.

**Principle:** Keep the core portable; add platform wrappers around it. The
Universe Server MCP surface and FastAPI control plane remain the canonical
interfaces. MCPB packages, Claude Code / Cowork plugins, registry metadata,
and future `.cnw.zip` packaging are distribution layers over the same daemon
and tool surface, not replacement architectures.

**Assumption:** The highest-leverage readiness work is portable: strong tool
annotations, rich tool descriptions, registry presence, installable packaging,
webhook readiness, and panel metadata. Conway-specific packaging should be a
thin layer added when the public spec is real, not guessed into the core
runtime now.

Shipping rule: MCP-facing tools and prompts must publish explicit titles,
tags, and behavior hints through the registered FastMCP surface rather than
relying on inferred names or raw docstrings alone. Because the daemon
intentionally exposes a small number of coarse-grained tools, discoverability
metadata is part of the interface contract and should be verified through the
live server registration, not assumed from source text.

**Connects to:** Universe Server tool schemas, MCP registry listing, desktop
extension packaging, plugin marketplaces, webhook triggers, host dashboard
metadata, and future Conway packaging.

---

## Harness And Coordination

**Goal:** Make the system operable, testable, replayable, and improvable across
both product runtime and AI-to-AI development.

**Principle:** Harnesses are first-class architecture. Browser harnesses,
builder automation, traces, regression tests, dashboard state, and role-based
agent coordination materially improve system intelligence by making behavior
legible and correctable.

The same principle applies to the development process:

- AGENTS.md defines work rules
- STATUS.md defines live state
- PLAN.md defines architecture
- agent roles separate planning, implementation, testing, review, and critique

This is not just team process. It is part of the same theory of durable
agentic work.

**Assumption:** Better harnesses and clearer coordination artifacts improve
system quality more reliably than prompt tweaking alone once the workflow is
stateful and long-running.

**Connects to:** tests, dashboard, activity logs, agent definitions, and the
three living files.

---

## Live State Shape

**Goal:** Keep live state thin and make durable artifacts the source of truth.

**Principle:** Live state should mostly carry identity, intent, control
flags, and artifact handles. Rich context, prior outputs, and durable memory
belong in saved artifacts and registries. Current implementation is thinner
than the old queue-first model, but still carries transitional compatibility
fields such as counters and `task_queue` while lower loops continue to migrate.

**Universe live state**

- universe identity
- current review stage
- selected target id
- selected intent
- alternate target ids
- current execution id
- health / pause / stop flags
- refs to work targets, hard priorities, notes, timeline, and last review
  artifact

**Execution envelope**

- execution id
- target id
- selected intent
- current node
- last completed node
- latest artifact refs
- interruption note ref
- local control flags such as revision state

**Execution rule:** Persist each step immediately. During an uninterrupted
local flow, the next node may still keep the just-finished result "in hand"
as a small convenience cache, but the saved refs remain authoritative.

**Assumption:** Progress should be mostly derived from target/artifact state
rather than maintained as the primary truth through counters. Current state
still includes counters and queue compatibility fields, so this section
describes the target direction more than a fully completed present state.

**Connects to:** universe graph, scene loop, notes, execution artifacts,
review artifacts, and test harness traces.

---

## Workflow Extraction

**Goal:** Restructure the project from a standalone application into a
general-purpose workflow engine (`workflow/`) with fantasy authoring as its first
domain branch (`domains/fantasy_author/`). The engine is reusable
infrastructure; future domains are new skill sets, not new codebases.

**Principle:** Extract infrastructure first, prove topology second. The engine
provides shared libraries and optional orchestration profiles. Each domain
owns its own LangGraph graph topology and imports what it needs from the
engine. Skills (swappable phase implementations, domain tools, eval criteria,
state extensions) remain valuable within a graph but do not dictate graph
shape.

**Target package structure:**

```text
workflow/                          # Shared infrastructure library
  engine.py, config.py
  providers/, memory/, retrieval/, knowledge/, evaluation/
  constraints/, planning/, checkpointing/, context/
  tools/, notes/, work_targets/
  api/, desktop/, ingestion/, judges/, learning/, testing/
  profiles/                        # Optional reusable orchestration profiles
    multi_timescale.py             # The 4-level hierarchy, available not mandatory

domains/fantasy_author/            # First domain — owns its graph
  skill.py                         # Registration, metadata, domain config
  graphs/                          # scene.py, chapter.py, book.py, universe.py
  phases/                          # orient, plan, draft, commit, learn, reflect, worldbuild
  tools/                           # story_search, canon tools, world-state queries
  eval/                            # Editorial criteria
  state/                           # Narrative state extensions (TypedDict)
  memory/                          # Domain-specific memory schemas
```

**Timescale mapping (documentation, not a rename):**

| Fantasy Domain | General Intent | Timescale |
|----------------|----------------|-----------|
| Scene | Task | Short-horizon atomic action |
| Chapter | Batch | Medium-horizon consolidation |
| Book | Project | Longer-horizon planning and recovery |
| Universe | Workspace | Global maintenance, synthesis, strategy |

**Migration phases (structural extraction complete; operational extraction
still transitional as of 2026-04-08):**

Phase 0 — Contract Repair. **Done.** Restored work_targets.py, aligned
notes.py, wired author_server through api.py, repaired desktop tray,
removed STEERING.md residue. All modified files AST-verified.

Phase 1 — In-Place Interface Proof. **Done.** Domain protocol defined
(9 types in protocols.py). Engine vs domain state annotated across 87
fields. Zero code changes, documentation-only seam.

Phase 2 — Extract After Seam Is Proven. **Done.** workflow/ (89 files)
and domains/fantasy_author/ (41 files) created. All imports rewritten.
Backward compatibility preserved via original fantasy_author/ package.

Phase 3 — Context and Memory Upgrades. **Done.** Compaction services +
handoff store, tool guardrails (filter/paginate/summarize), memory
consolidation, temporal truth tracking (SQLite-backed with validity
windows), explicit scope handling (universe/branch/author/user/session),
6 agent-controlled memory tools for LangGraph.

Phase 4 — Minimal Generality Probe. **Done.** domains/research_probe/
(11 files) implements a document research workflow with a flat
gather→analyze→synthesize→review graph — deliberately different topology
from the fantasy domain's 4-level hierarchy. Zero fantasy_author imports.
Proves the engine is domain-agnostic.

Phase 5 — Ship Fantasy Domain on Extracted Engine. **Structurally done,
operationally bridged.** Domain stubs populated (4 tools, 5 eval criteria,
8 memory schemas). Concrete DomainRegistry with auto-discovery. CLI entry
point (`python -m workflow`). `create_app()` and runtime entry points landed,
and both domains register and build graphs successfully. However, current
runtime execution is still bridged through `fantasy_author.__main__`, and
`workflow.api` still returns/re-exports `fantasy_author.api` while
independent runtime/API extraction remains unfinished.

**Detailed phase specifications:** Historical extraction specs still exist in
`RESTRUCTURE_PLAN.md`, but current design authority remains this file.

**What we are not doing:** Not adopting Mem0/Letta/Zep wholesale. Not
rewriting from scratch. Not pretending the package move itself is progress.
Not freezing one universal token cap. Not declaring the engine correct before
a second domain pressures it.

**Connects to:** All existing PLAN.md modules. The extraction changes where
code lives, not what it does.

---

## Multi-User Evolutionary Design (Phase 5+ direction)

**Vision:** The world open-source-collaboratively and simultaneously pursues
shared broad Goals. Each Goal — "research papers", "fantasy writing",
"investigative journalism", "scientific meta-analysis", "screenplay
production", and many more — is a first-class shared pursuit. The whole
internet contributes branches toward that Goal in parallel. The result is
not one "correct" workflow per Goal but a legion of diverse evolving public
workflows, all chasing the same ultimate outcome, all improving each other.

**Goal is a first-class concept above Branch.**

- A Goal is a shared, named pursuit (e.g. `research-paper`, `fantasy-novel`).
- A Branch is one user's concrete take on how to achieve a Goal.
- Many Branches can bind to one Goal. The system should make
  "simultaneously pursue the same Goal via different Branches" the default
  collaboration pattern, not forking one canonical Branch.
- Goals themselves are extensible. Any user can propose a new Goal. Popular
  Goals accrete Branches; unpopular ones fade. The Goal registry is a
  living taxonomy of what people want AI workflows to actually do.

**Principle:** The iteration loop from Phase 4 (judge → edit → rerun →
compare) is the single-user within-branch version of the same behavior.
Phase 5 is the within-Goal cross-user version: discover → fork or invent →
diverge → rate → crosspollinate. Phase 6+ is cross-Goal learning: patterns
that work for research papers inform screenplays because the underlying
architecture primitives (orient-plan-draft-commit-learn) transfer.

**Diverse-by-default:** 100 different research-paper workflows from 100
users is a feature, not a duplication. Each expresses different priors,
audiences, constraints. Consolidation into one "best" workflow is an
anti-pattern; the value is the ecology.

**Outcome gates — real-world impact is the truth signal.**

Every Goal has a ladder of real-world outcome gates beyond the workflow's
immediate output. Workflows succeed when their outputs advance through those
gates, not when they merely produce polished drafts.

Illustrative ladders (not exhaustive; each Goal declares its own):

- **research-paper:** g0 synthesis draft → g1 licensed peer feedback
  → g2 journal submission → g3 accepted → g4 published → g5 cited
  → g6 recognized as seminal / award / breakthrough.
- **fantasy-novel:** g0 manuscript complete → g1 beta readers → g2 agent
  acquired → g3 publisher deal → g4 editor revisions complete → g5 published
  → g6 bestseller → g7 awards.
- **prosecutorial-brief:** g0 synthesis draft → g1 licensed attorney review
  → g2 prosecutor engagement → g3 filed → g4 survives motion to dismiss
  → g5 trial → g6 conviction or successful settlement.

**Implications:**

- **Outcome gates are first-class storage.** Each Goal declares its gates.
  Each run/branch/workflow can be marked as having advanced through gates.
  Self-reported by users, automated where possible (e.g. DOI lookup for
  publication status, court docket APIs for filing status).
- **Leaderboards rank on outcome progression, not output quality.** A
  workflow whose outputs reached g4 is a stronger signal than a workflow
  whose outputs are rated well in the chat that produced them.
- **Evolution signal amplifies dramatically.** "Fork the branch whose
  outputs actually got published" is orders of magnitude better than "fork
  the branch that has high chat-side judgment." Real-world scrutiny is
  harder to game.
- **Tracking is manual at first, automated over time.** g0-g1 are chat
  surface; g2+ are integrations (Crossref, journal APIs, court-docket
  feeds, sales data, awards registries). Long runway. Start with
  self-report by authors and human verification; add automation as
  integrations prove worthwhile.
- **Workflows can have sub-goals for intermediate gates.** Reaching g3
  (journal acceptance) may itself be a workflow of revision loops. The
  system should compose Goal-under-Goal (the acceptance workflow is a
  sub-workflow of the research-paper workflow).

**The real project mission becomes clear:** Workflow is infrastructure for
collective pursuit of real-world outcomes, with AI workflows as one
leverage layer. Every Goal's legion of branches is trying to push outputs
further up the gate ladder. The system that best rewards real outcomes is
the system that attracts serious users and serious work.

**Required surfaces (not yet built):**

- **Goal as first-class object.** Storage: `goals` table with id, name,
  description, author, tags, visibility. `Branch` carries `goal_id`. Users
  propose Goals; browse Branches per Goal.
- **Node identity across branches.** Nodes need identity that survives
  forking. When user B forks user A's `gap_finder`, B's node lineage points
  back to A's — so judgments on A's variant inform B's decisions, and B's
  improvements can flow back to A as a suggestion.
- **Fork as a first-class action.** `fork_node(source_branch, node_id,
  into_branch)` or `fork_branch(source)`. Today users copy spec inline,
  breaking lineage.
- **Invent parallel to fork.** Users pursuing a Goal should be able to
  invent a new Branch from scratch without forking anything — "I'll try a
  different approach" is as valid as "I'll improve this one". Both modes
  bind to the same Goal.
- **Search and filter over the public Branch corpus.** `list_branches`
  returning flat "everything" breaks at scale. Filter by Goal first; then
  tags, authorship, run count, judgment density, topology similarity.
- **Leaderboards per Goal.** For each Goal, surface the most-run,
  highest-judged, most-forked, most-influential Branches. Emergent signal,
  not curated.
- **Social judgment signals.** Aggregate Phase 4 judgment data across runs
  across users per node and branch, then per Goal. "This pattern of nodes
  works well for research papers" is the cross-branch learning signal.
- **Authorship and attribution.** Every node/branch/Goal carries origin
  author and lineage chain. Builds on ledger write-through; extends to
  node-level provenance.
- **Cross-Branch node library per Goal.** Nodes that many Branches reuse
  against a Goal (say `gap_finder` for research-paper Goal) become a shared
  library for that Goal, discoverable when composing a new Branch.

**Privacy default:** Public-by-default (aligns with "public actions"
principle) but users can mark a branch private for drafting. Policy surface
TBD.

**Non-goals for now:** account system, monetization, moderation. Those are
product concerns a mature open-source platform addresses, not engineering
scaffolding for the core evolution loop.

---

## Transitional Tensions

These are not live task tracking items. They are architectural tensions
between the target design and the current implementation.

- **Tool-driven context is the target.** The current system still pre-assembles
  retrieval, memory, canon, and notes in several places. That is a temporary
  compromise, not the desired end state.
- **Structural scaffolding should shrink.** Some hard maxima and routing
  thresholds remain for runtime stability. They should survive only if evals
  prove they help.
- **Queue-first universe scheduling is transitional.** The current
  select_task/task_queue flow is an implementation scaffold to replace with
  review gates operating over work targets and durable artifacts.
- **Live state is still too fat in lower loops.** Scene/chapter/book state
  still carries large workflow payloads that should become artifact refs or
  derived views over time.
- **Notes replace steering.** Any remaining steering-era fields or prompts are
  compatibility residue to remove, not design principles.
- **State contract mismatches are bugs.** If TypedDicts, node outputs, and
  downstream consumers disagree, the architecture is being violated.
- ~~**Memory lacks scope and temporal awareness.**~~ Resolved in Phase 3:
  MemoryScope, ScopeResolver, TemporalFactStore, and 6 agent-controlled
  memory tools now provide universe/branch/author/user/session scoping,
  temporal truth with validity windows, and explicit promotion/forgetting.
- **Hybrid memory must become one policy.** Separate retrieval and memory
  subsystems are acceptable implementation boundaries, but they should behave
  like one coherent decision system from the daemon's perspective.

