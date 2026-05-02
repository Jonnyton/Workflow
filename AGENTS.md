# Workflow

A goal-agnostic daemon engine. You summon it, bind it to a domain, and
let it drive. Fantasy authoring is one domain. There will be others.

---

## Forever Rule (2026-04-18): Complete-System 24/7 Uptime Is Top Priority

One unified priority, not a ranked list. Every surface of the system
works 24/7 with zero hosts online:

- Tier-1 chatbot users create / browse / collaborate on nodes via a
  real chatbot UI with the Workflow connector installed (Claude.ai,
  ChatGPT Developer Mode, or a future equivalent surface).
- Tier-3 OSS contributors `git clone` and run cleanly.
- Tier-2 daemon hosts one-click install the tray (<5min friction).
- Node discovery, remix, converge, and live collaboration surfaces.
- Paid-market inbox + bid matching.
- Moderation + abuse response.

Target architecture:
`docs/design-notes/2026-04-18-full-platform-architecture.md`.

Work ordering: pick the task that unblocks the largest currently-broken
uptime surface. Treat any surface outage as equal severity — tiered
severity invites starvation. When multiple uptime surfaces are broken,
break ties by largest shared dependency impact, then shortest path to
verified recovery. Any uptime-track feature ships with the §14
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
durable state changes — not batched, not deferred. After every user message,
check: does this change any of the three? Multiple sessions from different
providers may be reading these concurrently. They are the shared state.
`STATUS.md` is a live coordination board, not a backlog.

| File | What belongs here | What does NOT belong here |
|------|-------------------|--------------------------|
| **AGENTS.md** | How to work on this project. Behavior, norms, hard rules. | Architecture, design decisions, principles (→ PLAN.md) |
| **PLAN.md** | How the system works and why. Architecture, principles, design decisions, module specs. | Live state, task tracking (→ STATUS.md). Behavioral norms (→ AGENTS.md) |
| **STATUS.md** | What's happening now. Live task board, concerns, next actions. ≤60 lines canonical (~4 KB guidance). | Architecture (→ PLAN.md). How-to-work (→ AGENTS.md). Session logs (→ `activity.log`). Landing records (→ git log). Backlog parking. |

If it's about the project's architecture or design → PLAN.md.
If it's about how to work on the project → AGENTS.md.
If it's about what's happening right now → STATUS.md.

---

## How to Work

### Orient

1. Read `STATUS.md` (live coordination board, concerns, current work). **Trim check:** when reading or writing it, delete resolved concerns, landing records, entries marked DONE, duplicated host asks, and rows no provider can act on. STATUS.md has a 60-line canonical budget (~4 KB guidance); every reader is a janitor.
2. `PLAN.md` is the design reference (~50 KB). Load it based on task scope:
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
- Duplicate host ask? Coalesce to one smallest concrete ask.
- No provider-actionable next step? Move detail to an artifact, or rewrite as a concrete `host-decision` / `host-action` row.
- Session summary or landing narrative? Put it in `activity.log`, not STATUS.md.
- Need detail on a concern? Link to the commit, spec, or `docs/concerns/` — STATUS.md entries stay ≤150 chars.

### Truth And Freshness

- **Truth is typed, not singular.** `AGENTS.md` owns process truth, `PLAN.md` owns design truth, and `STATUS.md` owns live-state truth. Do not silently treat one file as global truth when evidence disagrees.
- **Reality audits are diagnostic, not a fourth living source of truth.** Use them to reconstruct confidence when trust is damaged, then push stable conclusions back into `AGENTS.md`, `PLAN.md`, and `STATUS.md`.
- **Landed items leave STATUS.md.** Don't mark concerns DONE — delete them. If trust in a claim matters, use labels `current:`, `historical:`, `contradicted:`, `unknown:` with date + environment.
- **Verification claims must be freshness-stamped.** If a claim depends on tests, lint, runtime behavior, or environment state, include the date, environment, and evidence/command.
- **STATUS.md Concern row date-stamp format.** Every Concern row begins with `[filed:YYYY-MM-DD]` (when added) and gains `verified:YYYY-MM-DD` once someone re-checks the concern is still valid: `[filed:2026-04-23 verified:2026-04-28]`. Severity prefix optional and goes outside the bracket: `**[P1 filed:... verified:...]**`. Rationale: per `docs/audits/2026-04-28-status-md-coordination-gap.md` Rule 1, single-date stamps decay into stale state without explicit re-verification semantics.
- **Server-bug Concerns cross-reference their wiki BUG.** When a STATUS Concern row maps to a wiki `BUG-NNN` page, append `(see BUG-NNN)` inline. When a wiki BUG-NNN page is severity P0/P1, its header should reference the STATUS row. Rationale: per audit Rule 3, BUG-034 + duplicate Concern rows drifted as 3 separate items for 4 days because no cross-reference convention existed.
- **Contradictions must be downgraded immediately.** If current code, runtime artifacts, or verification output contradict an older claim, rewrite the `STATUS.md` claim or add a Concern before responding. Do not leave stale certainty in place.
- **Revalidate `PLAN.md` section by section when trust is damaged.** Treat the plan as candidate design intent until the relevant sections are confirmed against code and runtime evidence.
- **Audit docs decay too.** Before dispatching prescriptions from an audit older than ~24h, run a freshness check (git log, search, spot-read) and stamp any claim that still matters.

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

### Where new conventions live

This project is multi-provider: Codex, Cursor, Aider, Claude Code, Cowork,
and future agents may work from the same repo. Project-level conventions go
in `AGENTS.md` first so every provider can see the same process truth.
Provider-specific files such as `CLAUDE.md`, `.claude/agents/*`,
`.cursor/rules/*`, `.cursorrules`, and `.codex/*` are for harness-specific
notes or pointers back to `AGENTS.md`.

Before saving a rule, ask whether a teammate in another provider would need
it. If yes, put it in `AGENTS.md`; if it is only about one harness, tag the
section as `[harness-specific]`, `[Claude Code only]`, `[Cursor only]`,
`[Codex only]`, `[Cowork only]`, or `[Aider only]`.

Run `python scripts/check_cross_provider_drift.py` after editing
provider-specific files. Claude Code also wires
`.claude/hooks/cross_provider_drift_guard.py` as a PostToolUse hook for
`Write`, `Edit`, and `MultiEdit` on the developer teammate.

### Multi-Session Steering

- The user may steer multiple live sessions across different providers at once.
- Durable coordination belongs in files, not private chat memory.
- Use `STATUS.md`, `ideas/*.md`, and `.agents/activity.log` as the shared coordination surface.
- If two sessions may converge on the same idea, narrow the file boundary and record the split in `STATUS.md` or `ideas/PIPELINE.md`.
- A useful idea left only in chat is lost work.

---

## Team Norms

- **Teammates communicate directly where the harness supports it.** Claude Code devs message verifier after finishing work. Use SendMessage by name, not broadcast.
- **Verification is proactive.** Every substantive change gets independent verification before landing. Claude's persistent verifier is the background teammate implementation; other providers use focused tests plus independent diff/subagent review when available.
- **Persistent teams stay ready.** Where the harness supports teammates, they stay up, idle when not needed. "Standing by" is a valid state.
- **Iterate agent behavior.** If a teammate isn't performing well, refine its `.claude/agents/` definition and respawn.
- **Broadcast sparingly.** Token cost scales with team size. Use direct messages for targeted coordination, broadcast only for team-wide state changes.
- **Claim before working.** When self-claiming from the task list, claim first to prevent collisions. File locking handles races but claiming communicates intent.
- **Shutdown is graceful.** Teammates can reject shutdown if mid-task. Lead shuts down all teammates before running cleanup. Never force-kill without checking.
- **Despawn discipline.** Floater swaps use Escape-then-`shutdown_request` (Protocol A in `LAUNCH_PROMPT.md`). Verifier and dev despawns wait for in-flight tool calls — no Escape unless the teammate is genuinely idle. Hung teammates require filesystem cleanup of `~/.claude/teams/<team>/`; no force-kill verb exists. Spawn the replacement only AFTER `shutdown_approved` lands — never overlap, since the 3+1 floater roster is sized to the rate-limit budget. See `docs/audits/2026-04-25-despawn-chain-protocol.md`.

### Quality Gates

Three patterns keep agent output trustworthy:

**Verification is structural.** Every substantive change needs test/check evidence and an independent review path before it is treated as landed. Claude Code's `TaskCompleted` -> verifier loop is the preferred team implementation. Codex/Cowork satisfy the same invariant with focused tests plus independent diff/subagent review where available. Self-review alone is not enough for public-surface, storage, auth, migration, concurrency, or data-loss-risk changes.

**Final chatbot-surface verification is a rendered chatbot conversation through the live connector.** For changes affecting public MCP behavior, chatbot UX, connector tool descriptions, user-visible node/workflow state, or `tinyassets.io`, final acceptance must use a real browser-rendered chatbot conversation with the installed Workflow MCP connector at `https://tinyassets.io/mcp`, following `ui-test`. Claude.ai and ChatGPT Developer Mode both satisfy this when the Workflow connector is visible/installed and the tester types user-like prompts in the browser. The proof requirement is not host-login Claude.ai access; it is a real user path through the live MCP service. Direct MCP calls, local scripts, tests, DOM-only checks, and canaries are supporting evidence, not final user-surface proof. Log the rendered prompt/result in `output/user_sim_session.md` and include a trace or screenshot path when available.

**Post-fix clean-use evidence.** After the fix and `ui-test`, final verification must also look for evidence that actual users have used the affected feature cleanly since the fix landed. Use available production traces, connector/server logs, support reports, user-visible history, or other real-user evidence. Freshness-stamp the evidence. If no post-fix real-user use is visible yet, say that explicitly and, for public-surface or high-risk changes, leave a short watch item in `STATUS.md` instead of claiming proven clean use.

**Agent team loop guardrails with forced reflection.** If a teammate is stuck retrying the same approach, it must pause and reflect before the next attempt: "What failed? What specific change would fix it? Am I repeating the same approach?" If stuck for 3+ iterations on the same error, message the lead for reassignment or a fresh perspective. Don't loop forever. (Note: this is about dev agent stuck-loops, not daemon-level bounded reflection — see STATUS.md #6 for the daemon concern.)

**REFLECTION.md for compound learning.** After completing a significant task, the teammate writes a short reflection: what surprised me, one pattern worth capturing, one thing I'd do differently. Save to `REFLECTION.md` in the working directory. The lead reviews and merges approved learnings into AGENTS.md or the agent's memory. This is how sessions make future sessions better — systematically, not ad hoc.

**Scope-message before implementing self-found tasks.** Even when scope feels obvious, send the lead a one-line scope message and wait for approval before editing. The scope step exists to catch silent divergence from lead intent.

### Two Task Systems

The project uses two coordination layers that serve different purposes:

| System | Scope | Lifetime | Who sees it |
|--------|-------|----------|-------------|
| **Agent team task list** | Intra-session. Tasks the lead creates for teammates. | Ephemeral — dies with the session. | Lead + all teammates in this session. |
| **STATUS.md Work table** | Cross-provider. Tasks any provider can claim. | Durable — survives across sessions and providers. | Any AI, any tool, any provider. |

**Rule:** Work items that matter beyond the current session go in STATUS.md. The agent team task list is for sub-steps and intra-session coordination only. When a teammate completes a STATUS.md item, the lead updates STATUS.md — don't rely on the ephemeral task list as the record.

---

## Parallel Dispatch

**Multi-provider concurrent execution is the default operating mode.**
Multiple providers (Claude Code, Codex, Cursor, Cowork, future) work on
this project at the same time. The host does not announce when a new
provider is started; coordination flows through STATUS.md, not through
chat. Treat any session-start as "the team is already running; what's
safe to claim?"

The complete coordination contract is: **STATUS.md Work table is the
authoritative claim surface.** No external locks. No runtime signaling.
A provider with a fresh checkout, no chat history, and no announcement
should be able to start working productively in under a minute.

### Provider session-start ritual

Every provider, every session, in this order:

1. **Read STATUS.md.** Concerns + Work table + Next.
2. **Run `python scripts/claim_check.py --provider <yourname>`.**
   Output classifies every Work row into CLAIMABLE / BLOCKED / IN-FLIGHT
   / HOST-OWNED / STALE-CLAIM. The CLAIMABLE list is what's safe to
   start on right now; BLOCKED tells you why something isn't; IN-FLIGHT
   shows files off-limits.
3. **Claim by editing STATUS.md.** Change the chosen row's Status cell
   to `claimed:<yourname>`. Use a session-specific provider name when
   more than one session from the same tool may be active (for example
   `codex-gpt5-desktop`, `codex-cli-2`, `cursor-gpt55`). Commit that
   edit on your branch (or directly to main if you're operating without
   a worktree). The edit IS the claim — no other notification required.
4. **Work in a worktree or branch.** `git worktree add ../wf-<task>` or
   feature branch. Do not write outside your row's Files write-set
   without first updating STATUS.md to reflect the new write-set.
5. **On land**, change Status → `done` and delete the row in the same
   commit. The commit is the audit trail.

### Work-table row schema

Every row must have:

- **Files** — specific files or directories this task will write.
  This is the collision boundary. Be concrete: `workflow/api/wiki.py, workflow/storage/__init__.py`
  not `backend`. Read-only dependencies go in Depends, not Files. Use
  comma or semicolon between atoms.
- **Depends** — which tasks must merge first. Include both task
  dependencies (`#18, #23`) and file-read dependencies. If your task
  needs to read `api.py` after another task rewrites it, that is a
  dependency.
- **Status** — one of: `pending`, `claimed:<provider>`, `in-flight`,
  `dev-ready`, `host-action`, `host-decision`, `host-review`,
  `monitoring`, `done`. Provider is the tool/session name: `codex`,
  `claude-code`, `cursor`, `cowork`, or a more specific label such as
  `codex-gpt5-desktop` / `cursor-gpt55` when generic names would be
  ambiguous. `claimed:*` and `in-flight` mean the row's Files are
  off-limits to others until status flips.

### Stale-claim reaping

A claim is stale if its Files have seen no commits in 24h and the row
has no fresh active-date heartbeat. `claim_check.py` flags these as
STALE-CLAIM CANDIDATES. Any provider may reap a stale claim by editing
the row Status to `reaped:<yourname>:no-activity-24h`, then re-claiming
as their own (`claimed:<yourname>`). No daemon, no permission needed;
the convention is the policy. If a provider is actively building or
testing before a commit lands, add `ACTIVE YYYY-MM-DD` to the Work row
task text or status note. That heartbeat keeps the claim live for the
date shown and prevents uncommitted active work from being reaped just
because it has not landed yet.

### Pre-claim collision guard

Before adding a new row or broadening a Files cell, run
`python scripts/claim_check.py --provider <yourname> --check-files "path/a.py, docs/foo.md"`.
It warns if your prospective claim's Files overlap any in-flight row's
Files. Substring match either direction. If overlap fires, EITHER add a
Depends edge (the overlap is real coordination) OR refine your row's
Files to be narrower (the overlap was a hint, not a real write).

### Staying unblocked

If `claim_check.py` shows zero CLAIMABLE rows, look for cross-cutting
work that doesn't appear in the Work table: docs hygiene, skill audits,
test surface, design-note classifications, audit follow-ups. Add a new
Work row for the task you pick up rather than working off-table — that
keeps the next provider's `claim_check.py` accurate.

---

## Hard Rules

1. **SqliteSaver only** -- not AsyncSqliteSaver (not production-safe).
2. **LanceDB singleton** -- reuse connection objects, never recreate.
3. **No API SDKs for primary writer** -- Claude/Codex use `claude -p` and `codex exec` subprocesses.
4. **Executable gates need autonomous defaults** -- never block a workflow gate on human input when a safe default exists. True host-only authority is allowed only as a concrete `host-decision` or `host-action` row with the smallest possible ask; it must not block unrelated autonomous work. If no safe default exists, route around it or pick another non-overlapping uptime task.
5. **TypedDict + Annotated reducers** -- `Annotated[list, operator.add]` for accumulating fields.
6. **FactWithContext with truth-value typing** -- every extracted fact needs source_type, reliability, temporal_bounds, language_type. Domain skills may extend these fields.
7. **Python 3.11+** required.
8. **Fail loudly, never silently.** Mock fallbacks that look like real output are worse than crashes.
9. **User uploads are authoritative.** Preserved verbatim. Never summarize, truncate, or reformat.
10. **Contributor attribution uses `CONTRIBUTORS.md`.** When a branch or node ships and `attribution_credit` rows exist, read `CONTRIBUTORS.md` to map each `actor_id` to a GitHub handle and emit `Co-Authored-By:` lines in the commit message. Format: `Co-Authored-By: Display Name <handle@users.noreply.github.com>`. If an actor_id is not in the table, skip silently — never block a commit on missing attribution.
11. **Public-surface changes verify post-change.** After any edit to DNS records, Cloudflare tunnel config, GoDaddy Website Builder config, or any surface affecting `tinyassets.io`, run `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp` (or `scripts/uptime_canary.py --once` when Layer-1 is wired) and confirm a green probe. This canary is required evidence, not final chatbot-surface proof; MCP/chatbot-facing changes also require the rendered chatbot `ui-test` check above before final acceptance. Canonical public endpoint is `https://tinyassets.io/mcp` only. `mcp.tinyassets.io` is an Access-gated internal tunnel origin (host directive 2026-04-20) — it exists in DNS but is not user-facing; direct requests without the Worker's CF Access service-token headers return 401/403. Do not document or share `mcp.tinyassets.io` in user-facing contexts. The 2026-04-19 P0 outage (`docs/audits/2026-04-20-public-mcp-outage-postmortem.md`) landed when a tunnel reshuffle silently dropped a route — no commit touched the broken surface, so only a post-change out-of-band probe can catch this class. Named reference probes (including PROBE-001, the validated full-stack smoke): `docs/ops/acceptance-probe-catalog.md`.
12. **Portfolio graph stays current.** Before changing public-facing docs, project status, repo structure, or lineage, inspect `PROJECT_GRAPH.yml` where present and the standards in `docs/portfolio/`. If the change affects how a project appears publicly, update the relevant manifest, `docs/project-lineage.md`, or portfolio index notes. Default stance is public-draft unless explicitly private, but public publishing remains gated by scan/review.
13. **No destructive git ops without explicit approval.** Do not use `git reset --hard`, `git checkout --`, `git restore`, `git clean`, force-push, or stash/drop as cleanup or diagnostics unless the host explicitly asks for that operation.

---

## Testing

- `pytest` for the full suite. `ruff check` before committing.
- Every module must have tests. Nodes must never crash.
- After canonical `workflow/*` edits that affect the Claude plugin runtime, rebuild/check the mirror with `python packaging/claude-plugin/build_plugin.py`; pre-commit mirror parity is the guardrail. See `packaging/INDEX.md`.
- `actionlint` for GH Actions workflow edits. Install: `choco install actionlint -y` (Windows) / `brew install actionlint` (macOS) / `go install github.com/rhysd/actionlint/cmd/actionlint@latest` (Go). Pre-commit invariant #7 runs it on staged `.github/workflows/*.yml`; CI (`.github/workflows/actionlint.yml`) is the authoritative gate.

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
| `UNIVERSE_SERVER_DEFAULT_UNIVERSE` | Which universe ID is active when none explicit. | First subdir of `$WORKFLOW_DATA_DIR`. |
| `WORKFLOW_REPO_ROOT` | Path to the local git checkout for `workflow.producers.goal_pool` + git-backed catalog writes. When unset, resolved via `Path(__file__).resolve().parent.parent`. | Derived from module path. |
| `WORKFLOW_WIKI_PATH` | Canonical root for the cross-project knowledge wiki the `wiki` tool reads/writes. Resolved via `workflow.storage.wiki_path()`; inherits `data_dir()` platform handling when unset. | `$WORKFLOW_DATA_DIR/wiki` (platform default). |
| `WORKFLOW_UPLOAD_WHITELIST` | Colon/semicolon-separated absolute-path prefixes allowed for `add_canon_from_path`. Unset = accept any absolute path. | Unset (permissive). |

### Auth + identity

| Var | Purpose | Default |
|-----|---------|---------|
| `UNIVERSE_SERVER_USER` | Username the Workflow Server credits for commit-authorship + ledger write-author + request claims. Required for paid-market claims; otherwise falls back. | `anonymous`. |
| `UNIVERSE_SERVER_HOST_USER` | Host-identity username used when a request is claimed by the box running the daemon (as opposed to an individual operator). | `host`. |
| `UNIVERSE_SERVER_AUTH` | Auth mode. `"true"` / `"1"` enables OAuth-gated MCP. Disabled by default for single-operator dev. | `false`. |
| `UNIVERSE_SERVER_PORT` | Port used by `workflow.auth.wellknown` when emitting OAuth metadata URLs. | `8001`. |
| `WORKFLOW_GIT_AUTHOR` | Verbatim override for git commit author (e.g. `"Workflow User <user@users.noreply.workflow.local>"`). Highest precedence; falls through to `UNIVERSE_SERVER_USER`-derived synthetic. | Unset (synthetic from `UNIVERSE_SERVER_USER`). |
| `WORKFLOW_CODEX_AUTH_JSON_B64` | Base64-encoded `~/.codex/auth.json` bundle for the codex provider's subscription auth. Decoded by `deploy/docker-entrypoint.sh` on container startup and written to `~/.codex/auth.json`. Required for `codex` provider availability under the default subscription-only posture. Replaces the retired `OPENAI_API_KEY`-driven `codex login --with-api-key` path. Rotate on each codex CLI re-auth. Source: b8d30ac. | Unset. |
| `WORKFLOW_CLOUD_DAEMON_SUBSCRIPTION_ONLY` | **Deprecated** legacy alias for the canonical default `WORKFLOW_ALLOW_API_KEY_PROVIDERS=0` (see §LLM + provider routing). Kept for back-compat with older compose / operator docs; new operators should set `WORKFLOW_ALLOW_API_KEY_PROVIDERS` directly. Source: b8d30ac. | Unset. |
| `OPENAI_API_KEY` | **Stripped at entrypoint** by `deploy/docker-entrypoint.sh` unless `WORKFLOW_ALLOW_API_KEY_PROVIDERS=1`. The legacy `codex login --with-api-key` path is intentionally not run; codex auth flows through `WORKFLOW_CODEX_AUTH_JSON_B64`. Setting `OPENAI_API_KEY` without the opt-in flag has no effect. Source: b8d30ac. | Unset. |

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
| `WORKFLOW_ALLOW_API_KEY_PROVIDERS` | Explicit opt-in for API-key-backed daemon providers. Default project-wide policy, including self-hosted daemons, is subscription-only: API-key env vars are ignored unless this is truthy. Use only when the host deliberately chooses to run an API-key daemon. | `off` |
| `GEMINI_API_KEY` / `GROQ_API_KEY` / `XAI_API_KEY` | Provider API keys for the Gemini / Groq / Grok providers respectively. Ignored unless `WORKFLOW_ALLOW_API_KEY_PROVIDERS` is truthy. | Unset. |
| `FANTASY_DAEMON_LLM_TYPES` | Comma-separated list of LLM types the fantasy daemon prefers (e.g. `"claude,codex"`). Filters provider selection. | Unset. |

### Observability + uptime

| Var | Purpose | Default |
|-----|---------|---------|
| `WORKFLOW_MCP_CANARY_URL` | Public MCP URL the uptime canary probes. | `https://tinyassets.io/mcp` (canonical apex; `mcp.tinyassets.io` is an Access-gated internal tunnel origin, not user-facing — host directive 2026-04-20). |
| `TAB_WATCHDOG_INTERVAL_S` | Interval (seconds) for the tray tab-watchdog's polling. `scripts/tab_watchdog.py`. | `60`. |
| `WORKFLOW_CLAUDE_CHAT_SCREENSHOTS` | User-sim skill flag — capture a screenshot on every `claude_chat.py` response settle. Cost: ~200 KB per response. | Unset (off). |

**Canonical resolver:** `workflow.storage.data_dir()` is the single
source of truth for `WORKFLOW_DATA_DIR` resolution. Do not re-implement
the precedence logic elsewhere — call the resolver.

**Container deploys:** set `WORKFLOW_DATA_DIR=/data` + bind-mount the
host path to `/data`. See `deploy/README.md` for the full pattern.

### Local secrets — vault-first

Local operator secrets (Cloudflare tokens, DigitalOcean token, Hetzner creds, OpenAI key) load from a password manager, not a plaintext file. Vendor is chosen via `WORKFLOW_SECRETS_VENDOR` — `1password` (default), `bitwarden`, or `plaintext` (migration-period opt-out, to be retired after cutover).

Bootstrap on a fresh machine:

```bash
# 1. install vendor CLI (see docs/design-notes/2026-04-22-secrets-vault-integration.md)
# 2. sign in:
eval $(op signin)                       # 1Password
# or: bw login && export BW_SESSION=$(bw unlock --raw)   # Bitwarden
# 3. load into current shell:
set -a; source scripts/load_secrets.sh; set +a
```

One-shot migration from the legacy `$HOME/workflow-secrets.env`:

```bash
python scripts/migrate_secrets_to_vault.py --vendor 1password --dry-run
python scripts/migrate_secrets_to_vault.py --vendor 1password
# verify, then shred ~/workflow-secrets.env
```

Canonical list of keys: `scripts/secrets_keys.txt` (edit there, not in shell profiles). Full rationale + vendor comparison + bootstrap runbook: `docs/design-notes/2026-04-22-secrets-vault-integration.md`. GitHub Actions secrets are out of scope — they stay in repo settings.

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
| `scripts/claim_check.py` | Any AI, any tool | Multi-provider session-start helper. Classifies STATUS.md Work rows as CLAIMABLE / BLOCKED / IN-FLIGHT / HOST-OWNED / STALE. Run with `--provider <yourname>` before claiming work. |
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
