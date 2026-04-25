# Idea Inbox

Quick capture surface for loose ideas, user nudges, possible features, and
half-formed experiments.

## Rules

- Capture first, refine later.
- Keep one idea per entry.
- If an idea becomes work, a design note, or a plan, add the destination in
  `Links` instead of deleting the capture history.
- Merge duplicates during triage in `ideas/PIPELINE.md`, not during capture.

## Inbox

- [2026-04-25] (source: navigator-audit, owner: unassigned, status: captured) CONTRIBUTORS.md authoring surface — a canonical file listing node/branch authors with GitHub handles for Co-Authored-By attribution, seeded from the designer-royalties model (`project_designer_royalties_and_bounties`). Chatbot can read it to credit contributors in commit messages and pull request bodies.
  Next: evaluate whether this is a standalone file convention or a feature that needs a daemon_server.py table + MCP surface. Ilse persona (OSS-contributor tier) is the natural first user — good user-sim mission candidate.
  Links: -

- [2026-04-25] (source: navigator-audit, owner: unassigned, status: captured) fantasy_daemon/phases/ entry-point comment — each phase file (orient.py, worldbuild.py, commit.py, etc.) lacks a one-line header comment naming which graph cycle invokes it and what the entry-point node is. Reading any phase file cold requires tracing back through book.py/chapter.py/universe.py to understand context. Simple docstring convention addition; no architecture change.
  Next: quick fix — dev can add entry-point comments to all 7 phase files in a single small task. No spec needed; just a task with Files boundary `domains/fantasy_daemon/phases/*.py`.
  Links: -

- [2026-04-20] (source: host, owner: navigator-followup, status: captured,
  priority: post-uptime, size: large)
  **Agent-teams-on-Workflow: open-source-Claude-Code-analog as a user
  project, backed by our primitives.**
  Host framing: the Claude Code system prompt leaked; a Python open-source
  analog is growing fast on GitHub and trending toward one of the fastest-
  growing repos. Opportunity — build "Claude Code agent teams" where each
  teammate is another Workflow node invoked via a daemon-request, and the
  teammates live in another branch of the workflow. **This is a USER
  project, not ours to build.** Our job is to make sure the primitives
  exist on the platform so the user's chatbot can compose this — daemon
  requests across branches, teammate roles as nodes, inter-teammate
  messaging via the paid-market / free-queue bid layer, per-teammate
  provenance + audit.
  Why this matters: validates the "daemon economy + convergent commons"
  thesis with a concrete, viral-shaped use case that isn't fantasy-
  authoring. If the OSS Claude-Code-analog audience can compose their
  agent teams on Workflow, the platform rides that wave.
  Required primitives (load-bearing, to check against existing roadmap):
  (a) node → daemon-request invocation with typed inputs/outputs,
  (b) cross-branch teammate spawning without per-teammate auth friction,
  (c) teammate identity + soul-file attachment per `project_terminology_daemon`,
  (d) per-teammate provenance in the activity log, (e) inter-teammate
  messaging — bid market OR free-queue fan-out, probably both,
  (f) graceful partial-failure when one teammate's daemon is down
  (handled by daemon-economy fallback paths).
  Open questions to answer at triage time (NOT now): does this need a
  dedicated MCP verb set for teammate orchestration, or does it compose
  from existing `submit_request` + branch primitives? Is the OSS Claude-
  Code-analog's data model mappable to our node-type taxonomy without
  forcing a schema change? How does convergent-commons apply — should
  popular teammate definitions be wiki-shared, forkable, autoresearch-
  optimizable?
  Dependencies: uptime-track (all 14 self-host rows) lands first;
  daemon-economy first-draft (Track A + bid + settlement) lands first;
  then this becomes a scoping exercise.
  Next: triage into PIPELINE.md once uptime-track closes; at triage, open
  the research note (link below) — it already maps primitives-gaps and
  proposes §4 foundation/UX/commons items, names nano-claude-code as the
  recommended reference base (Python, ~40K LoC, ~85 files, architectural
  seams map cleanly onto our primitives — claw-code now Rust-primary, less
  ideal base), and lists §8 questions to put to host.
  Links:
  - **`docs/notes/2026-04-20-agent-teams-on-workflow-research.md` —
    navigator research + thinking note. 11-seam gap analysis, viral-
    moment considerations, foundation/UX/commons work item ranking.**
  - `project_daemon_product_voice.md` — "summoning the daemon" brand fit.
  - `project_convergent_design_commons.md` — teammate-definition sharing.
  - `project_daemon_default_behavior.md` — multi-spawn policy needs
    re-read in light of "one user spawning many teammates."
  - `docs/design-notes/2026-04-18-full-platform-architecture.md` — check
    §10 track decomposition for whether this falls under Track N
    (vibe-coding authoring) or needs its own track.

- [2026-04-24] (source: user-sim/Priya-Session2, owner: navigator, status: captured,
  priority: post-uptime, size: medium)
  **"Extend run" / "continue branch" as a first-class primitive.**
  User-sim signal: Priya Session 2 ask "add BIOCLIM + RF for comparison on the same 14 species"
  has no clean Workflow verb. "New branch" implies fresh scaffolding. "New run" implies same
  algo-set. Chatbot must semantically infer "clone this branch, add algorithm nodes, re-run
  same species set." No existing primitive surfaces this as an intent. Chain-break: Interface 1
  primitive gap — chatbot improvises where it should have a clear tool.
  Scoping questions: (a) clone-branch-and-add-nodes vs. re-run-with-additional-params vs.
  new sibling branch? (b) does this need a new MCP verb (`extend_branch`/`continue_run`) or
  is it composable from `submit_request` + `clone_branch`? (c) what state carries over from
  the original run (params, results, species set)?
  Dependencies: in-flight run recovery part 2 (#6) should land first (resume semantics
  inform extension semantics).
  Next: triage after #6 lands; design note needed before spec.
  Links:
  - `docs/audits/user-chat-intelligence/2026-04-24-competitor-trials-sweep.md` Signal 2

- [2026-04-24] (source: user-sim/Priya-W&B-trial, owner: navigator, status: captured,
  priority: domain-skill, size: small)
  **`hyperparameter_importance` evaluator node for scientific/ML domain.**
  W&B Sweeps computes hyperparameter importance (which knobs matter most across a sweep)
  automatically. Workflow has no equivalent. User-sim rates it "cheap to add, high-value
  for scientific users." Domain-specific — belongs in the scientific-computing skill module,
  not the engine. CV-as-first-class-primitive is the structural moat; this is a parity win.
  Next: capture in science-domain node catalog when that module is scoped.
  Links:
  - `docs/audits/user-chat-intelligence/2026-04-24-competitor-trials-sweep.md` Signal 4
