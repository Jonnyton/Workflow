# Workflow

A goal-agnostic daemon engine. You summon it, bind it to a domain, and
let it drive. Fantasy authoring is one domain. There will be others.

---

## Forever Rule (2026-04-18): Complete-System 24/7 Uptime Is Top Priority

One unified priority, not a ranked list. Every surface of the system
works 24/7 with zero hosts online:

- Tier-1 chatbot users create / browse / collaborate on nodes via
  Claude.ai.
- Tier-3 OSS contributors `git clone` and run cleanly.
- Tier-2 daemon hosts one-click install the tray (<5min friction).
- Node discovery, remix, converge, and live collaboration surfaces.
- Paid-market inbox + bid matching.
- Moderation + abuse response.

Target architecture:
`docs/design-notes/2026-04-18-full-platform-architecture.md`.

Work ordering: pick the task that unblocks the largest currently-broken
uptime surface. Treat any surface outage as equal severity — tiered
severity invites starvation. Any uptime-track feature ships with §14
concurrency/load-test proof or it is not done.

Subordinated work (bug sprints, rename phases, unrelated design notes)
continues but never blocks uptime work.

Everything else — bug sprints, rename phases, design notes for
unrelated concerns — is subordinated until the uptime vector is making
steady forward progress. Subordinated does not mean cancelled; it means
it doesn't top the queue.

---

## Three Living Files

All three are living documents. All three are updated immediately when
anything changes — not batched, not deferred. After every user message,
check: does this change any of the three? Multiple sessions from different
providers may be reading these concurrently. They are the shared state.

| File | What belongs here | What does NOT belong here |
|------|-------------------|--------------------------|
| **AGENTS.md** | How to work on this project. Behavior, norms, hard rules. | Architecture, design decisions, principles (→ PLAN.md) |
| **PLAN.md** | How the system works and why. Architecture, principles, design decisions, module specs. | Live state, task tracking (→ STATUS.md). Behavioral norms (→ AGENTS.md) |
| **STATUS.md** | What's happening now. Task board, concerns, next actions. ≤4 KB / 60 lines. | Architecture (→ PLAN.md). How-to-work (→ AGENTS.md). Session logs (→ `activity.log`). Landing records (→ git log). |

If it's about the project's architecture or design → PLAN.md.
If it's about how to work on the project → AGENTS.md.
If it's about what's happening right now → STATUS.md.

---

## How to Work

### Orient

1. Read `STATUS.md` (live state, task board, concerns). **Trim check:** if you see resolved concerns, landing records, or entries marked DONE — delete them now. STATUS.md has a 4 KB / 60-line budget; every reader is a janitor.
2. `PLAN.md` is the design reference (18 KB). Load it based on task scope:
   - **Full load** when: planning or scoping a new feature, making or evaluating
     a design decision, checking alignment with project principles, working on
     module architecture or cross-cutting concerns.
   - **Section load** when: fixing a bug in a specific module, making a small
     scoped change. Use `python scripts/docview.py headings PLAN.md` to find
     the relevant section, then read only that section.
   - **Skip** when: routine test fixes, documentation, skill edits, or
     non-architectural code changes.
3. If the idea inbox is non-empty, scan `ideas/PIPELINE.md` and `ideas/INBOX.md`.
4. If your approach conflicts with a PLAN.md principle, do NOT implement it. Add the conflict to STATUS.md Concerns. PLAN.md changes require user approval.

### Updating the Three Files

**Tiered sync — match effort to message type:**

| Message type | STATUS.md | PLAN.md |
|---|---|---|
| Decision, priority change, new concern, task state change, reframing | **Update immediately** before responding | **Update immediately** if design-relevant |
| New idea that won't be executed now | Capture in `ideas/INBOX.md` or `ideas/PIPELINE.md` | — |
| Code change request, bug fix, feedback on output, question | Check mentally; update only if state actually changed | — |
| Greeting, clarification, small talk | — | — |

**The rule:** If the user closes the window after your next message, the files must already reflect any state change from what they said. The check is automatic. But not every message changes state — the previous "check both files on every message including 'hi'" spent ~38 KB of re-reads on turns that changed nothing.

- **Session task lists are ephemeral.** Other sessions can't see them. Use only for sub-steps.
- **If the user raises a new idea that will not be fully executed now, capture it in `ideas/INBOX.md` or `ideas/PIPELINE.md` before the turn ends.**

**STATUS.md deletion is as important as addition.** Every time you write to STATUS.md, also check for content that should leave:
- Concern resolved? Delete the line (don't mark DONE — just delete).
- Work row landed? Delete the row. The commit is the record.
- A concern became a Work row? Delete the concern — the task IS the resolution.
- Accepted design decision? Move to PLAN.md, delete from STATUS.md.
- Session summary or landing narrative? Put it in `activity.log`, not STATUS.md.
- Need detail on a concern? Link to the commit, spec, or `docs/concerns/` — STATUS.md entries stay ≤150 chars.

### Truth And Freshness

- **Truth is typed, not singular.** `AGENTS.md` owns process truth, `PLAN.md` owns design truth, and `STATUS.md` owns live-state truth. Do not silently treat one file as global truth when evidence disagrees.
- **Reality audits are diagnostic, not a fourth living source of truth.** Use them to reconstruct confidence when trust is damaged, then push stable conclusions back into `AGENTS.md`, `PLAN.md`, and `STATUS.md`.
- **Landed items leave STATUS.md.** Don't mark concerns DONE — delete them. If trust in a claim matters, use labels `current:`, `historical:`, `contradicted:`, `unknown:` with date + environment.
- **Verification claims must be freshness-stamped.** If a claim depends on tests, lint, runtime behavior, or environment state, include the date, environment, and evidence/command.
- **Contradictions must be downgraded immediately.** If current code, runtime artifacts, or verification output contradict an older claim, rewrite the `STATUS.md` claim or add a Concern before responding. Do not leave stale certainty in place.
- **Revalidate `PLAN.md` section by section when trust is damaged.** Treat the plan as candidate design intent until the relevant sections are confirmed against code and runtime evidence.

### Client Conversations Are Bug Reports

When the user pastes a chat conversation (from any MCP client or interface), extract issues and fix them immediately.

### Large Docs And Artifacts

Codex may truncate large local-file and tool output. This repo therefore has a
scoped reader at `python scripts/docview.py`.

- Use `python scripts/docview.py` instead of raw whole-file reads for large
  Markdown, text, or JSON artifacts.
- This is required for `PLAN.md`, `output/*/notes.json`, large review
  artifacts, and any text/JSON file likely to exceed roughly 10 KiB or 200
  lines.
- Start with `stat`, then narrow with `headings`, `section`, `lines`,
  `search`, `json-keys`, or `json`.
- If `docview.py` says the result is too large, narrow the query again. Do not
  fall back to raw whole-file reads.
- Raw full-file reads are only acceptable after a scoped query shows the file
  is small enough to fit safely.

### Project Skills

- Project engineering skills live canonically in `.agents/skills/` and are mirrored into `.claude/skills/` for Claude Code's harness discovery.
- Codex and project-visible agents read from `.agents/skills/` directly — there is no separate Codex mirror.
- Claude Code reads from `.claude/skills/`.
- When the right workflow skill is not obvious, start with `using-agent-skills` and then read the matching skill.
- After editing shared skills, run `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1` to refresh the Claude Code mirror.

### Multi-Session Steering

- The user may steer multiple live sessions across different providers at once.
- Durable coordination belongs in files, not private chat memory.
- Use `STATUS.md`, `ideas/*.md`, and `.agents/activity.log` as the shared coordination surface.
- If two sessions may converge on the same idea, narrow the file boundary and record the split in `STATUS.md` or `ideas/PIPELINE.md`.
- A useful idea left only in chat is lost work.

---

## Team Norms

- **Teammates communicate directly.** Dev messages verifier after finishing work. Use SendMessage by name, not broadcast.
- **Verifier is proactive.** Runs tests and reviews diffs after every dev change without being asked. Runs as a background teammate.
- **The team is always ready.** Teammates stay up, idle when not needed. "Standing by" is a valid state.
- **Iterate agent behavior.** If a teammate isn't performing well, refine its `.claude/agents/` definition and respawn.
- **Broadcast sparingly.** Token cost scales with team size. Use direct messages for targeted coordination, broadcast only for team-wide state changes.
- **Claim before working.** When self-claiming from the task list, claim first to prevent collisions. File locking handles races but claiming communicates intent.
- **Shutdown is graceful.** Teammates can reject shutdown if mid-task. Lead shuts down all teammates before running cleanup. Never force-kill without checking.

### Quality Gates

Three patterns keep agent output trustworthy:

**Verification is structural.** Verifier is a core teammate, not on-demand. Every `TaskCompleted` event triggers verifier — it runs tests then reviews the diff. The lead only acts on code that verifier has cleared (verdict: SHIP). If verifier flags critical issues, the task goes back to dev — it is not marked complete.

**Agent team loop guardrails with forced reflection.** If a teammate is stuck retrying the same approach, it must pause and reflect before the next attempt: "What failed? What specific change would fix it? Am I repeating the same approach?" If stuck for 3+ iterations on the same error, message the lead for reassignment or a fresh perspective. Don't loop forever. (Note: this is about dev agent stuck-loops, not daemon-level bounded reflection — see STATUS.md #6 for the daemon concern.)

**REFLECTION.md for compound learning.** After completing a significant task, the teammate writes a short reflection: what surprised me, one pattern worth capturing, one thing I'd do differently. Save to `REFLECTION.md` in the working directory. The lead reviews and merges approved learnings into AGENTS.md or the agent's memory. This is how sessions make future sessions better — systematically, not ad hoc.

### Two Task Systems

The project uses two coordination layers that serve different purposes:

| System | Scope | Lifetime | Who sees it |
|--------|-------|----------|-------------|
| **Agent team task list** | Intra-session. Tasks the lead creates for teammates. | Ephemeral — dies with the session. | Lead + all teammates in this session. |
| **STATUS.md Work table** | Cross-provider. Tasks any provider can claim. | Durable — survives across sessions and providers. | Any AI, any tool, any provider. |

**Rule:** Work items that matter beyond the current session go in STATUS.md. The agent team task list is for sub-steps and intra-session coordination only. When a teammate completes a STATUS.md item, the lead updates STATUS.md — don't rely on the ephemeral task list as the record.

---

## Parallel Dispatch

Multiple providers (Claude Code, Codex, Cowork) work on this project
concurrently. Each uses worktree isolation. Coordination happens through
the STATUS.md Work table, not through locks or runtime signaling.

### Breaking work for parallel execution

Before dispatching a large plan to any provider, break it into the
Work table as separate rows. Each row must have:

- **Files** — specific files or directories this task will write.
  This is the collision boundary. Be concrete: `api.py, author_server.py`
  not `backend`. Read-only dependencies go in Depends, not Files.
- **Depends** — which tasks must merge first. Include both task
  dependencies and file-read dependencies. If your task needs to read
  `api.py` after another task rewrites it, that is a dependency.
- **Status** — `pending`, `claimed:provider`, `done`, or the existing
  states. Provider is the tool name: `codex`, `claude-code`, `cowork`.

### Claiming and executing

Any provider can claim any pending task whose Depends are all `done`.
Claim by updating the Status column to `claimed:yourname`. Work in a
worktree or branch. When finished, merge sequentially — one branch at
a time, rebase remaining branches onto updated main.

### What the dispatcher checks

Before assigning two tasks to run concurrently, verify their Files
columns do not overlap. If they overlap, one must depend on the other.
Read-only overlap is fine — add it as a Depends instead.

### Staying unblocked

If you finish early and no pending tasks have satisfied dependencies,
look for tasks in other areas of the project (docs, skills, tests,
MCP surfaces) that don't overlap with in-progress work. The goal is maximum
useful concurrency, not waiting.

---

## Hard Rules

1. **SqliteSaver only** -- not AsyncSqliteSaver (not production-safe).
2. **LanceDB singleton** -- reuse connection objects, never recreate.
3. **No API SDKs for primary writer** -- Claude/Codex use `claude -p` and `codex exec` subprocesses.
4. **Never block on human input** -- every gate has an autonomous default.
5. **TypedDict + Annotated reducers** -- `Annotated[list, operator.add]` for accumulating fields.
6. **FactWithContext with truth-value typing** -- every extracted fact needs source_type, reliability, temporal_bounds, language_type. Domain skills may extend these fields.
7. **Python 3.11+** required.
8. **Fail loudly, never silently.** Mock fallbacks that look like real output are worse than crashes.
9. **User uploads are authoritative.** Preserved verbatim. Never summarize, truncate, or reformat.
10. **Public-surface changes verify post-change.** After any edit to DNS records, Cloudflare tunnel config, GoDaddy Website Builder config, or any surface affecting `tinyassets.io` / `mcp.tinyassets.io`, run `python scripts/mcp_public_canary.py` (or `scripts/uptime_canary.py --once` when Layer-1 is wired) and confirm a green probe before considering the change complete. The 2026-04-19 P0 outage (`docs/audits/2026-04-20-public-mcp-outage-postmortem.md`) landed when a tunnel reshuffle silently dropped a route — no commit touched the broken surface, so only a post-change out-of-band probe can catch this class.

---

## Testing

- `pytest` for the full suite. `ruff check` before committing.
- Every module must have tests. Nodes must never crash.

---

## Configuration — environment variables

The daemon reads configuration from env vars. Defaults are
CWD-independent so containerized deploys don't drift based on where
the process was launched from.

### Data + paths

| Var | Purpose | Default |
|-----|---------|---------|
| `WORKFLOW_DATA_DIR` | Canonical root for all on-disk state (SQLite checkpoint, LanceDB indexes, per-universe output dirs). Absolute path. | Platform default — Windows: `%APPDATA%\Workflow`; Linux/macOS/container: `~/.workflow`. |
| `WORKFLOW_UNIVERSE` | Per-universe override — specific universe dir for the stdio MCP shim (`workflow.mcp_server`). | `$WORKFLOW_DATA_DIR/default-universe`. |
| `UNIVERSE_SERVER_BASE` | **Deprecated.** Legacy alias for `WORKFLOW_DATA_DIR`. Still honored; emits `DeprecationWarning` when `WORKFLOW_DEPRECATIONS=1`. Pre-commit invariant 5 blocks new reads outside `workflow/storage/__init__.py`. | — |
| `UNIVERSE_SERVER_DEFAULT_UNIVERSE` | Which universe ID is active when none explicit. | First subdir of `$WORKFLOW_DATA_DIR`. |
| `WORKFLOW_REPO_ROOT` | Path to the local git checkout for `workflow.producers.goal_pool` + git-backed catalog writes. When unset, resolved via `Path(__file__).resolve().parent.parent`. | Derived from module path. |
| `WIKI_PATH` | Path to the cross-project knowledge wiki the `wiki` tool reads/writes. | `C:\Users\Jonathan\Projects\Wiki` (Windows dev fallback — configure explicitly on container deploys). |
| `WORKFLOW_UPLOAD_WHITELIST` | Colon/semicolon-separated absolute-path prefixes allowed for `add_canon_from_path`. Unset = accept any absolute path. | Unset (permissive). |

### Auth + identity

| Var | Purpose | Default |
|-----|---------|---------|
| `UNIVERSE_SERVER_USER` | Username the Workflow Server credits for commit-authorship + ledger write-author + request claims. Required for paid-market claims; otherwise falls back. | `anonymous`. |
| `UNIVERSE_SERVER_HOST_USER` | Host-identity username used when a request is claimed by the box running the daemon (as opposed to an individual operator). | `host`. |
| `UNIVERSE_SERVER_AUTH` | Auth mode. `"true"` / `"1"` enables OAuth-gated MCP. Disabled by default for single-operator dev. | `false`. |
| `UNIVERSE_SERVER_PORT` | Port used by `workflow.auth.wellknown` when emitting OAuth metadata URLs. | `8001`. |
| `WORKFLOW_GIT_AUTHOR` | Verbatim override for git commit author (e.g. `"Workflow User <user@users.noreply.workflow.local>"`). Highest precedence; falls through to `UNIVERSE_SERVER_USER`-derived synthetic. | Unset (synthetic from `UNIVERSE_SERVER_USER`). |

### Feature flags

Each flag reads as a string; truthy = `"on"`, `"1"`, `"true"`, `"yes"` (case-insensitive). Defaults chosen so out-of-the-box behavior matches current tier-1 contract.

| Var | Purpose | Default |
|-----|---------|---------|
| `WORKFLOW_DISPATCHER_ENABLED` | Master switch for the dispatcher. Off = every request runs inline; on = dispatch goes through the claim/bid surface. | `on`. |
| `WORKFLOW_PAID_MARKET` | Enables the paid-market bid/claim surface. `WORKFLOW_DISPATCHER_ENABLED` must also be on. Phase-G flag. | `off`. |
| `WORKFLOW_GOAL_POOL` | Enables the goal-pool producer in `workflow.producers.goal_pool` — cross-branch goal aggregation. | `off`. |
| `WORKFLOW_PRODUCER_INTERFACE` | Enables the producer-interface surface — multi-producer concurrency for branches. | `on`. |
| `WORKFLOW_TIERED_SCOPE` | Enables the tiered-memory-scope retrieval router (`workflow.retrieval.router`). Memory scope is tier-gated (node/branch/goal/user/universe). | `off` (Stage 1 monitoring; flip to `on` at Stage 2c per task #19). |
| `GATES_ENABLED` | Enables outcome-gate claims (Phase 6). When off, `gates` tool returns placeholder. | `off`. |
| `WORKFLOW_STORAGE_BACKEND` | Catalog storage backend selection. Values: empty (default), `"git"`, `"sqlite"`. | Empty (auto-select per backend factory). |
| `WORKFLOW_RUN_MAX_CONCURRENT` | Integer cap on concurrent in-flight branch runs. | Unset = unlimited. |

### LLM + provider routing

| Var | Purpose | Default |
|-----|---------|---------|
| `OLLAMA_HOST` | Local Ollama endpoint URL. Presence is the "local-LLM-bound" signal `get_status` reports. | Unset. |
| `ANTHROPIC_BASE_URL` | Alternate Anthropic endpoint (e.g. self-hosted relay). Presence also flips `llm_endpoint_bound` to truthy. | Unset. |
| `WORKFLOW_PIN_WRITER` | Pin a specific writer provider by name (e.g. `"claude-code"`, `"codex"`). Overrides the provider router's fallback chain. | Unset. |
| `GEMINI_API_KEY` / `GROQ_API_KEY` / `XAI_API_KEY` | Provider API keys for the Gemini / Groq / Grok providers respectively. Missing key → provider unavailable. | Unset. |
| `FANTASY_DAEMON_LLM_TYPES` | Comma-separated list of LLM types the fantasy daemon prefers (e.g. `"claude,codex"`). Filters provider selection. | Unset. |

### Observability + uptime

| Var | Purpose | Default |
|-----|---------|---------|
| `WORKFLOW_MCP_CANARY_URL` | Public MCP URL the uptime canary probes. Canary-specific — keeps the `mcp.` direct-tunnel URL so a Worker outage is distinguishable from tunnel/daemon outage. | `https://mcp.tinyassets.io/mcp`. |
| `WORKFLOW_DEPRECATIONS` | Set to `1` / `true` / `yes` to surface deprecation warnings for legacy env vars + import shims. | Unset (silent). |
| `TAB_WATCHDOG_INTERVAL_S` | Interval (seconds) for the tray tab-watchdog's polling. `scripts/tab_watchdog.py`. | `60`. |
| `WORKFLOW_CLAUDE_CHAT_SCREENSHOTS` | User-sim skill flag — capture a screenshot on every `claude_chat.py` response settle. Cost: ~200 KB per response. | Unset (off). |

**Canonical resolver:** `workflow.storage.data_dir()` is the single
source of truth for `WORKFLOW_DATA_DIR` resolution. Do not re-implement
the precedence logic elsewhere — call the resolver.

**Container deploys:** set `WORKFLOW_DATA_DIR=/data` + bind-mount the
host path to `/data`. See `deploy/README.md` for the full pattern.

---

## Project Files

| File | Audience | Purpose |
|------|----------|---------|
| `AGENTS.md` | Any AI, any tool | How to work, team norms, hard rules. |
| `STATUS.md` | Any AI, any tool | Live state: task board, concerns, watch, archive. |
| `PLAN.md` | Any AI, any tool | Architecture, principles, design decisions. |
| `README.md` | Any human or AI | Fast project orientation. |
| `INDEX.md` | Any human or AI | Repo map and Obsidian hub. |
| `CODEX.md` | Codex | Thin routing layer. |
| `notes.json` | Daemon + sessions | Per-universe unified notes (user, editor, structural, system). |
| `scripts/docview.py` | Any AI, any tool | Scoped reader for large Markdown/text/JSON artifacts that should not be read raw. |
| `scripts/capture_idea.py` | Any AI, any tool | Fast append helper for the idea inbox. |
| `scripts/sync-skills.ps1` | Repo maintenance | Re-sync `.agents/skills/` into `.claude/skills/`. |
| `CLAUDE.md` | Claude Code only | Thin routing layer. |
| `CLAUDE_LEAD_OPS.md` | Claude Code lead | Situational: user-sim loops, dev team management, token efficiency. Not auto-loaded. |
| `LAUNCH_PROMPT.md` | Claude Code lead | Team spawn, session protocol, lead norms. |
| `.claude/agents/*.md` | Claude Code only | Individual agent definitions. |
| `.agents/skills/*/SKILL.md` | Codex + project agents (canonical source) | Canonical skill definitions. Edit here first. |
| `.claude/skills/*/SKILL.md` | Claude Code only | Mirror of `.agents/skills/` refreshed by `scripts/sync-skills.ps1`. |
| `.agents/activity.log` | Any AI, any tool | Short cross-session activity feed for coordination. |
| `ideas/*.md` | Any AI, any tool | Idea capture, triage, and shipped traceability. |
| `knowledge/*.md` | Any human or AI | Human-readable compiled knowledge companion to `knowledge.db`. |
| `docs/exec-plans/*.md` | Any AI, any tool | Multi-step execution plans and landing history. |
| `docs/conventions.md` | Any AI, any tool | Stable documentation and linking patterns. |
| `docs/decisions/INDEX.md` | Any AI, any tool | ADR directory surface. |
| `docs/specs/INDEX.md` | Any AI, any tool | Feature/change spec directory surface. |
