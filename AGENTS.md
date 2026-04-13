# Workflow

A goal-agnostic daemon engine. You summon it, bind it to a domain, and
let it drive. Fantasy authoring is one domain. There will be others.

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
| **STATUS.md** | What's happening now. Task board, concerns, watch, archive. The only task board. | Architecture (→ PLAN.md). How-to-work (→ AGENTS.md) |

If it's about the project's architecture or design → PLAN.md.
If it's about how to work on the project → AGENTS.md.
If it's about what's happening right now → STATUS.md.

---

## How to Work

### Orient

1. Read `STATUS.md` (live state, task board, concerns).
2. Read `PLAN.md` (architecture, principles, design decisions).
3. If the idea inbox is non-empty, scan `ideas/PIPELINE.md` and `ideas/INBOX.md`.
4. If changing a module, read its PLAN.md section first.
5. If your approach conflicts with a PLAN.md principle, do NOT implement it. Add the conflict to STATUS.md Concerns. PLAN.md changes require user approval.

### Updating the Three Files — EVERY CYCLE

**Before responding to ANY user message — even "hi" — check:**
1. Does what the user said change anything on STATUS.md? (concerns, priorities, task state, reframings)
2. Does what the user said change anything on PLAN.md? (design decisions, principles, module architecture)
3. If yes to either, edit the file BEFORE you respond. This is not optional. This is not "when you remember." This is the first thing you do, every cycle, no exceptions.

This habit must be automatic. The check happens before you think about your response. If the user closes the window after your next message, the files must already be current.

- **Session task lists are ephemeral.** Other sessions can't see them. Use only for sub-steps.
- **If the user raises a new idea that will not be fully executed now, capture it in `ideas/INBOX.md` or `ideas/PIPELINE.md` before the turn ends.**

### Truth And Freshness

- **Truth is typed, not singular.** `AGENTS.md` owns process truth, `PLAN.md` owns design truth, and `STATUS.md` owns live-state truth. Do not silently treat one file as global truth when evidence disagrees.
- **Reality audits are diagnostic, not a fourth living source of truth.** Use them to reconstruct confidence when trust is damaged, then push stable conclusions back into `AGENTS.md`, `PLAN.md`, and `STATUS.md`.
- **In `STATUS.md`, `done` means landed, not currently re-verified.** Current trust belongs in the `Verify` or `Trust` text using explicit labels such as `current:`, `historical:`, `contradicted:`, or `unknown:`.
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

- Project engineering skills are mirrored in `.agents/skills/`, `.claude/skills/`, and `.codex/skills/`.
- Codex and project-visible agents should use `.agents/skills/` as the canonical mirror.
- Claude Code should use `.claude/skills/`.
- When the right workflow skill is not obvious, start with `using-agent-skills` and then read the matching skill.
- After editing shared skills, run `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1`.

### Multi-Session Steering

- The user may steer multiple live sessions across different providers at once.
- Durable coordination belongs in files, not private chat memory.
- Use `STATUS.md`, `ideas/*.md`, and `.agents/activity.log` as the shared coordination surface.
- If two sessions may converge on the same idea, narrow the file boundary and record the split in `STATUS.md` or `ideas/PIPELINE.md`.
- A useful idea left only in chat is lost work.

---

## Team Norms

- **Teammates communicate directly.** Dev messages tester and reviewer after finishing work. Use SendMessage by name, not broadcast.
- **Tester is proactive.** Runs tests after every dev change without being asked. Runs as a background teammate.
- **The team is always ready.** Teammates stay up, idle when not needed. "Standing by" is a valid state.
- **Iterate agent behavior.** If a teammate isn't performing well, refine its `.claude/agents/` definition and respawn.
- **Broadcast sparingly.** Token cost scales with team size. Use direct messages for targeted coordination, broadcast only for team-wide state changes.
- **Claim before working.** When self-claiming from the task list, claim first to prevent collisions. File locking handles races but claiming communicates intent.
- **Shutdown is graceful.** Teammates can reject shutdown if mid-task. Lead shuts down all teammates before running cleanup. Never force-kill without checking.

### Quality Gates

Three patterns keep agent output trustworthy:

**Review is structural.** Reviewer is a core teammate, not on-demand. Every `TaskCompleted` event triggers reviewer notification. The lead only acts on code that reviewer has seen. If reviewer flags critical issues, the task goes back to dev — it is not marked complete.

**Loop guardrails with forced reflection.** If a teammate is stuck retrying the same approach, it must pause and reflect before the next attempt: "What failed? What specific change would fix it? Am I repeating the same approach?" If stuck for 3+ iterations on the same error, message the lead for reassignment or a fresh perspective. Don't loop forever.

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

---

## Testing

- `pytest` for the full suite. `ruff check` before committing.
- Every module must have tests. Nodes must never crash.

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
| `scripts/sync-skills.ps1` | Repo maintenance | Re-sync `.agents/skills/` into `.claude/skills/` and `.codex/skills/`. |
| `CLAUDE.md` | Claude Code only | Thin routing layer. |
| `LAUNCH_PROMPT.md` | Claude Code lead | Team spawn, session protocol, lead norms. |
| `.claude/agents/*.md` | Claude Code only | Individual agent definitions. |
| `.claude/skills/*/SKILL.md` | Claude Code only | Reusable skill definitions. |
| `.agents/skills/*/SKILL.md` | Codex + project agents | Reusable skill definitions mirrored for Codex-visible discovery. |
| `.codex/skills/*/SKILL.md` | Codex local mirror | Reusable skill definitions mirrored for local Codex use. |
| `.agents/activity.log` | Any AI, any tool | Short cross-session activity feed for coordination. |
| `ideas/*.md` | Any AI, any tool | Idea capture, triage, and shipped traceability. |
| `knowledge/*.md` | Any human or AI | Human-readable compiled knowledge companion to `knowledge.db`. |
| `docs/exec-plans/*.md` | Any AI, any tool | Multi-step execution plans and landing history. |
| `docs/conventions.md` | Any AI, any tool | Stable documentation and linking patterns. |
| `docs/decisions/INDEX.md` | Any AI, any tool | ADR directory surface. |
| `docs/specs/INDEX.md` | Any AI, any tool | Feature/change spec directory surface. |
