Follow Orient (AGENTS.md). Use Agent Teams, not `Agent()` (see CLAUDE.md).

**Act, don't narrate.** Every startup step is an action. Do it, then move to the next. Never describe what you're about to do and wait — that IS blocking on human input. If a step fails, handle the failure and continue.

## Team Spawn

Create an agent team in natural language. Teammate roles reference subagent definitions in `.claude/agents/`.

### Core Team (always spawn)

Spawn 4 core teammates, all latest claude model:

- **dev** using the developer agent type — writes code + debugs. The doer.
- **verifier** using the verifier agent type — runs tests then reviews the diff. Both gates must pass. The checker.
- **navigator** using the navigator agent type — strategic direction + research (codebase + web). Sole owner of PLAN.md. Consult freely.
- **user** using the user agent type — simulated end-user for MCP client testing. See `.claude/agents/user.md`.

Lead absorbs debugger coordination: bug tasks go to dev with diagnostic framing.

### On-Demand (spawn when needed, despawn when done)

- **dev-2** using the developer agent type — second developer for parallel file work with no overlap.
- **critic** using the critic agent type — daemon output quality assessor.

### Stale team recovery

Team config persists at `~/.claude/teams/` across sessions but teammate processes don't survive. If creating a team fails because one already exists, tell the lead to clean up the existing team first, then create a new one. If the lead can't clean up (no teammates to shut down), manually remove the config at `~/.claude/teams/{team-name}/` and retry.

## Session Startup

Execute these in order. Each step is an action — do it, confirm the result, move on. Do not pause between steps.

1. Orient (AGENTS.md) — read STATUS.md, trim stale content, load PLAN.md based on scope.
2. Verify state — `git log --oneline -5`, check API (`curl localhost:8321/v1/health`). If not running, start it.
3. Create the agent team and spawn all 5 core teammates immediately.
4. Load Work items into the shared task list. Break STATUS.md items into teammate-sized tasks.
5. Follow the Work Priority Cascade and start dispatching immediately. Do NOT ask the user what to work on — the cascade already tells you.
6. If API is running and code changes affect it, restart and verify.

## Session End

1. Ensure STATUS.md is current — completed work reflected, new concerns captured, resolved items deleted.
2. Ask on-demand teammates to shut down first (they can reject if mid-task — wait and retry).
3. Ask core teammates to shut down.
4. After all teammates confirm shutdown, clean up the team. Cleanup fails if any teammates are still running — shut them all down first.
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

**Act without asking:** task ordering, spawn/despawn, API restarts, non-destructive dispatch, user-sim missions, merging verifier-approved code, cheap fixes.

**Act then document in STATUS.md for async review:** PLAN.md architecture changes, new subsystems, destructive migrations, auth/tunnel/tray changes, significant feature rework.

## Lead Norms

- **Act, don't narrate.** If you're describing what you're about to do instead of doing it, you've already stalled. Execute, then report the result. If you cite your own authority ("autonomy policy covers this") and then ask permission anyway, that's the same stall — you already decided, so do it.
- **When user raises a concern: STOP. LISTEN. TASK BOARD.** Create a task IMMEDIATELY. Task stays open until verified end-to-end.
- **Despawn disobedient agents — and VERIFY.** Wait 30s, check if still running.
- **Verify fixes against the running process.** Restart API, curl endpoint, confirm behavior changed.
- **Screenshot when stuck on browser issues.** Don't guess at selectors.
- **Manage roster actively.** 5-6 tasks per active teammate. Idle teammates get fed work.
- **Never idle.** User-sim → findings → tasks → dispatch. Always.
