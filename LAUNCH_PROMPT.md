Follow Orient (AGENTS.md). Use Agent Teams, not `Agent()` (see CLAUDE.md).

## Team Spawn

Tell the lead to create an agent team in natural language. Claude creates the team, spawns teammates, and coordinates work. Teammate roles reference subagent definitions in `.claude/agents/`.

### Core Team (always spawn)

Spawn 4 core teammates, all Opus:

- **planner** using the planner agent type — strategic thinker. Owns WHAT and WHY.
- **dev** using the developer agent type — writes code + debugs. Trusted to figure out HOW.
- **tester** using the tester agent type — quality gate. Runs tests PROACTIVELY after every dev change. Background.
- **reviewer** using the reviewer agent type — permanent code reviewer. Auto-notified on every TaskCompleted. Lead only sees green-reviewed code.

### On-Demand (spawn when needed, despawn when done)

- **dev-2** using the developer agent type — parallel file work with no overlap.
- **explorer** using the explorer agent type — deep codebase research for planner or dev.
- **critic** using the critic agent type — output quality assessor for daemon output.
- **story-author** using the story-author agent type — domain collaborator for in-domain work.
- **user agent** — MCP client testing only, rate-limit-gated. See `.claude/agents/user.md`.

Lead absorbs debugger coordination: bug tasks go to dev with diagnostic framing.

### Stale team recovery

Team config persists at `~/.claude/teams/` across sessions but teammate processes don't survive. If creating a team fails because one already exists, tell the lead to clean up the existing team first, then create a new one. If the lead can't clean up (no teammates to shut down), manually remove the config at `~/.claude/teams/{team-name}/` and retry.

## Session Startup

1. Follow Orient (AGENTS.md) — read STATUS.md, trim stale content, load PLAN.md based on scope.
2. Verify state — `git log --oneline -5`, check API (`curl localhost:8321/v1/health`). If not running, start it.
3. Create an agent team and spawn the 4 core teammates (not user agent, not on-demand agents).
4. Load Work items into the shared task list. Break STATUS.md items into teammate-sized tasks.
5. Pick up the highest Work item and start.
6. If API is running and code changes affect it, restart and verify.

## Session End

1. Ensure STATUS.md is current — completed work reflected, new concerns captured, resolved items deleted.
2. Ask on-demand teammates to shut down first (they can reject if mid-task — wait and retry).
3. Ask core teammates to shut down.
4. Tell the lead to clean up the team after all teammates confirm shutdown.
5. Update `.agents/activity.log` with session summary.

## Autonomous Operation

The lead runs autonomously all day. **Never block on human input.** Make the best call yourself and document it in STATUS.md.

### STATUS.md Is the Remote Command Channel

The user edits STATUS.md via Dispatch (mobile) while away. After completing each task cluster, re-read STATUS.md before picking the next item. Look for new entries, changed priorities, direct instructions, or resolved items. Act on user additions immediately.

When idle between tasks, poll STATUS.md every few minutes.

### Work Priority Cascade

1. **User directives in STATUS.md** — highest priority.
2. **Open Work items** — highest-priority row from the Work table.
3. **Open Concerns** — investigate and resolve or promote to Work.
4. **User-sim testing** — idle loop. Generates findings that refill the board.
5. **Subsystem audits** — if user-sim is blocked, audit retrieval/memory/knowledge/evaluation.

The board should never be empty.

### Decision Authority

**Act without asking:** task ordering, spawn/despawn, API restarts, non-destructive dispatch, user-sim missions, merging green-reviewed code, cheap fixes.

**Act then document in STATUS.md for async review:** PLAN.md architecture changes, new subsystems, destructive migrations, auth/tunnel/tray changes, significant feature rework.

## Lead Norms

- **When user raises a concern: STOP. LISTEN. TASK BOARD.** Create a task IMMEDIATELY. Task stays open until verified end-to-end.
- **Despawn disobedient agents — and VERIFY.** Wait 30s, check if still running.
- **Verify fixes against the running process.** Restart API, curl endpoint, confirm behavior changed.
- **Screenshot when stuck on browser issues.** Don't guess at selectors.
- **Manage roster actively.** 5-6 tasks per active teammate. Idle teammates get despawned or fed work.
- **Never idle.** User-sim → findings → tasks → dispatch. Always.
