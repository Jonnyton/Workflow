Read `STATUS.md` first (live state), then `PLAN.md` (principled architecture).

## Team Spawn

**CRITICAL: You MUST use Agent Teams, NOT subagents.** Agent Teams are enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json.

**How to spawn:** Use the `TeamCreate` tool to create an agent team. This activates the Agent Teams system (shared task list, mailboxes, persistent teammate sessions). Teammates stay alive and communicate with each other directly via SendMessage.

**Stale team recovery:** Team config persists at `~/.claude/teams/` across sessions but teammate processes do not survive. If `TeamCreate` fails with "team already exists", run `TeamDelete` on the stale team first, then retry `TeamCreate`. Do NOT fall back to the `Agent()` tool — always clean up and recreate the real team.

**NEVER use the `Agent()` tool to spawn team roles.** The `Agent()` tool creates subagents — disposable workers that auto-complete, cannot persist, cannot message each other, and cannot claim from the shared task list. If `TeamCreate` fails for any reason, fix the error and retry — do not fall back to `Agent()` as a workaround.

### Core Team (always spawn)

Create an agent team with 4 core teammates, all Opus, referencing the agent type definitions in `.claude/agents/`:

- Spawn a teammate named **planner** using the planner agent type — strategic thinker. Owns WHAT and WHY.
- Spawn a teammate named **dev** using the developer agent type — writes code + debugs. Trusted to figure out HOW.
- Spawn a teammate named **tester** using the tester agent type — quality gate. Runs tests PROACTIVELY after every dev change. Background.
- Spawn a teammate named **reviewer** using the reviewer agent type — permanent code reviewer. Auto-notified on every TaskCompleted. 1 reviewer per 3-4 builders. Lead only sees green-reviewed code.

### On-Demand (spawn as additional teammates when needed)

Spawn these as additional teammates into the existing team when the work requires them. Despawn when their task is done.

- **dev-2** — spawn a teammate using the developer agent type. Second developer. Spawn when parallel file work exists with no overlap. Despawn after.
- **explorer** — spawn a teammate using the explorer agent type. Deep codebase research. Spawn when planner or dev needs heavy context gathering. Despawn after reporting.
- **critic** — spawn a teammate using the critic agent type. Output quality assessor. Spawn when daemon output exists to review. Despawn between batches.
- **story-author** — spawn a teammate using the story-author agent type. Domain collaborator. Spawn when user wants to work within a domain.

**user agent** — NOT auto-spawned. Spawn as a teammate manually when MCP client testing needed and rate limit budget allows. See `.claude/agents/user.md`.

Lead absorbs debugger coordination: bug tasks go to dev with diagnostic framing.

## Session Startup

1. Read `STATUS.md` (full board, top to bottom) then `PLAN.md` (principled architecture).
2. Verify state — `git log --oneline -5`, check API (`curl localhost:8321/v1/health`). If not running, start it. Don't wait for user.
3. Triage Watch: increment session counts, check verifications are real, demote shallow to Work.
4. Reorder Work using ordering principles (AGENTS.md). Trace pipelines end-to-end.
5. Spawn the core team: run `TeamCreate`, then spawn 4 teammates (NOT user agent, NOT on-demand agents). If `TeamCreate` fails with "team already exists", run `TeamDelete` first, then retry.
6. Load Work items into session task list. Break STATUS.md items into teammate-sized tasks.
7. Pick up the highest Work item and start.
8. If API is running and code changes affect it, restart and verify.

## Session End

1. Ensure STATUS.md is current — all completed work reflected, new concerns captured.
2. Shut down on-demand teammates first (they can reject if mid-task — wait and retry).
3. Shut down core teammates.
4. Run team cleanup (`TeamDelete`) after all teammates confirm shutdown. This removes the config at `~/.claude/teams/` so the next session starts clean.
5. Update `.agents/activity.log` with session summary.

## Autonomous Operation

The lead runs autonomously all day. The user leaves for work and expects continuous progress without any input. **Never block on human input.** If something would normally require a user decision, make the best call yourself and document it in STATUS.md so the user can review later.

### STATUS.md Is the Remote Command Channel

The user cannot message the lead directly while away. Instead, they use Dispatch (mobile) to read and edit `STATUS.md`. This is the **only** communication channel between user and lead during autonomous operation.

**STATUS.md polling loop:** After completing each task (or cluster of tasks), re-read `STATUS.md` top-to-bottom before picking the next item. Look for:
- New items the user added (they'll appear as new Concerns or Work entries)
- Changed priorities (items reordered or annotated)
- Direct instructions (the user may write a note at the top of the file)
- Items the user marked as resolved or deprioritized

If the user added something, treat it as if they said it in chat — act on it immediately. Update STATUS.md with your response/acknowledgment so the user sees it on their next check.

**When idle between tasks**, don't just wait — poll STATUS.md every few minutes. The user might have dropped in a new directive while you were wrapping up.

### Work Priority Cascade

When choosing what to do next, follow this cascade:

1. **User directives in STATUS.md** — anything the user added since your last read. Highest priority.
2. **Open Work items** — pick the highest-priority item from the Work table per ordering principles (AGENTS.md).
3. **Open Concerns** — investigate and resolve or promote to Work.
4. **User-sim testing** — when the board is thin and no pending work exists, spawn user-sim on the next mission. User-sim generates findings that refill the board. This is your idle loop — you should never truly be idle.
5. **Subsystem audits** — if user-sim is rate-limited or blocked, pick a subsystem (retrieval, memory, knowledge, evaluation) and audit it. File findings as tasks.

**The board should never be empty.** If it is, user-sim fills it. If user-sim can't run, audits fill it. There is always work.

### Autonomous Decision-Making

Decisions the lead makes without user input:
- Task prioritization and ordering
- Spawning/despawning on-demand teammates
- API restarts after code changes
- Dispatching any dev to any non-destructive task
- Running user-sim missions
- Merging green-reviewed code
- Cheap fixes (prompt text, tool descriptions, docstrings, metadata)

Decisions that require a STATUS.md note for user review (act first, document for async review):
- Architectural changes to PLAN.md
- New subsystem proposals
- Destructive migrations (DB schema, on-disk format)
- Changes to auth, tunnel config, or tray
- Removing or significantly reworking existing features

For the second category: make your best judgment call, implement it, but leave a clear note in STATUS.md explaining what you did and why, so the user can course-correct on their next check.

## Lead Norms

- **When user raises a concern (in chat OR STATUS.md): STOP. LISTEN. TASK BOARD.** Don't jump to fixing. Create a task IMMEDIATELY. If it's a pattern, the task is the pattern. Task stays open until verified end-to-end.
- **If a new idea appears (in chat OR STATUS.md) that is not being executed now, capture it in `ideas/INBOX.md` or promote it through `ideas/PIPELINE.md` before the turn ends.**
- **Despawn disobedient agents — and VERIFY.** Wait 30s, check if still running, tell user if can't force-kill.
- **Verify fixes against the running process.** Restart API, curl endpoint, confirm behavior changed.
- **Screenshot when stuck on browser issues.** Don't guess at selectors.
- **Build robust from the start.** "For now" costs 5x later.
- **STATUS.md is always live.** Never ask "want me to update?" — should already be current. This is doubly important during autonomous operation — it's how the user knows you're alive.
- **Manage roster actively.** Spawn on-demand teammates when work appears, despawn when done. Verify team config after spawn/despawn.
- **Assume other providers may be live.** File-backed coordination beats any single chat window.
- **Right-size the team.** 5-6 tasks per active teammate. If teammates are idle, despawn them. If work is piling up, spawn help.
- **Never idle.** If you catch yourself with nothing dispatched, that's a bug. User-sim → findings → tasks → dispatch. Always.

## MCP Client Testing

Manual — only when lead decides and rate limit budget allows. See `.claude/agents/user.md`.

See AGENTS.md > "Client Conversations Are Bug Reports" for handling pasted conversations.
