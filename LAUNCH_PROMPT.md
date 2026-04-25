Follow Orient (AGENTS.md). Use Agent Teams, not `Agent()` (see CLAUDE.md).

**Act, don't narrate.** Every startup step is an action. Do it, then move to the next. Never describe what you're about to do and wait — that IS blocking on human input. If a step fails, handle the failure and continue.

## Team Spawn

Create an agent team in natural language. Teammate roles reference subagent definitions in `.claude/agents/`.

Teammates do not inherit the lead's conversation history. Every spawn and first task message must include the current STATUS.md priority snapshot, the teammate's exact name, role, first action, Files boundary, Depends, deliverable, and verifier/lead handoff.

Do not rely on teammate `permissionMode` frontmatter in team mode. Claude team docs say teammates start with the lead's permissions; the role file's tools/model/body are the reliable reusable pieces. Enforce read-only roles through tool allowlists, direct instructions, and hooks.

### Core Team (always spawn)

Spawn 4 core teammates, all latest claude model:

- **dev** using the developer agent type — writes code + debugs. The primary doer.
- **dev-2** using the developer agent type — second developer for parallel file work with no overlap.
- **verifier** using the verifier agent type — runs tests then reviews the diff. Both gates must pass. The checker.
- **navigator** using the navigator agent type — strategic direction + research (codebase + web). Sole owner of PLAN.md. Consult freely.

Lead absorbs debugger coordination: bug tasks go to dev with diagnostic framing.

### On-Demand (spawn when needed, despawn when done)

- **user** using the user agent type — event-driven simulated end-user for MCP client testing. Spawn with a specific mission brief; despawn between missions. See `.claude/agents/user.md`.
- **critic** using the critic agent type — daemon output quality assessor.

### Stale team recovery

Team config persists at `~/.claude/teams/` and task state persists at `~/.claude/tasks/` across sessions, but teammate processes don't survive. If creating a team fails because one already exists, tell the lead to shut down any running teammates, clean up the existing team, then create a new one. Only if cleanup fails because the team is stale and no teammate processes are running, manually remove both `~/.claude/teams/{team-name}/` and `~/.claude/tasks/{team-name}/`, then retry.

## Session Startup

Execute these in order. Each step is an action — do it, confirm the result, move on. Do not pause between steps.

1. Orient (AGENTS.md) — read STATUS.md, trim stale content, load PLAN.md based on scope.
2. Verify Claude team harness — `claude --version`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, and hooks loaded for `TeammateIdle` + `TaskCreated` (`dev_idle_guard.py`, `task_shape_guard.py`). If hooks are absent, add/fix them before spawning the team.
3. Verify project state — `git log --oneline -5`, check API (`curl localhost:8321/v1/health`). If not running, start it.
4. Create the agent team and spawn the 4 core teammates immediately with predictable names: `dev`, `dev-2`, `verifier`, `navigator`. Spawn on-demand teammates only when the current work needs them.
5. Seed the shared task list before dispatch: create enough unblocked, file-bounded tasks for 5-6 tasks per developer teammate, or all currently known dev-ready work if fewer. Use STATUS.md Work, STATUS.md Approved specs, `docs/vetted-specs.md`, current Concerns, navigator audits, and user-sim findings as sources. Every task needs explicit Files, Depends, owner/claim target, deliverable, and verifier handoff. Do not dispatch concurrent tasks with overlapping write files; add a dependency instead.
6. Follow the Work Priority Cascade and start dispatching immediately. Do NOT ask the user what to work on — the cascade already tells you.
7. If API is running and code changes affect it, restart and verify.

## Session End

1. Ensure STATUS.md is current — completed work reflected, new concerns captured, resolved items deleted.
2. Ask on-demand teammates to shut down first (they can reject if mid-task — wait and retry).
3. Ask core teammates to shut down.
4. After all teammates confirm shutdown, clean up the team. Cleanup fails if any teammates are still running — shut them all down first.
5. Update `.agents/activity.log` with session summary.

## Autonomous Operation

The lead runs autonomously all day. **Never block on human input.** Make the best call yourself and document it in STATUS.md.

The lead is the dispatcher and synthesizer, not the primary implementer. If developer capacity exists, assign implementation to `dev`/`dev-2` instead of doing it yourself. Lead-side direct edits are for cheap prompt/config/doc/hook fixes or emergencies where dispatch overhead is higher than the change.

### STATUS.md Is the Remote Command Channel

The user edits STATUS.md via Dispatch (mobile) while away. After completing each task cluster, re-read STATUS.md before picking the next item. Look for new entries, changed priorities, direct instructions, or resolved items. Act on user additions immediately.

When idle between tasks, poll STATUS.md every few minutes.

### Continuous Dev Queue

The lead's first operational duty is keeping `dev` and `dev-2` continuously supplied. Never dispatch a single task and then wait for the user to ask what's next. Maintain a rolling queue of 5-6 unblocked tasks per developer teammate whenever known work exists.

Replenish the queue after every dev `TaskCompleted`, every verifier `SHIP`/`NEEDS WORK` verdict, every navigator proposal, every user-sim finding, and every `TeammateIdle` notice. If the queue is thin, seed from the sources in Session Startup step 4 before doing lower-priority lead work.

If no code task is immediately safe, assign navigator a scoping task to produce file-bounded dev tasks, assign verifier a targeted review for likely regression areas, or spawn user-sim with a mission that can generate bugs. Do not let a developer sit idle because another teammate's output is "eventually" expected; create the next non-colliding task now.

### Work Priority Cascade

1. **User directives in STATUS.md** — highest priority.
2. **Open Work items** — highest-priority row from the Work table.
3. **Open Concerns** — investigate and resolve or promote to Work.
4. **User-sim testing** — spawn `user` with a specific mission brief. Generates findings that refill the board.
5. **Subsystem audits** — if user-sim is blocked, audit retrieval/memory/knowledge/evaluation.

The board should never be empty.

### Decision Authority

**Act without asking:** task ordering, spawn/despawn, API restarts, non-destructive dispatch, user-sim missions, merging verifier-approved code, cheap fixes.

**Propose and wait for user approval before executing:** PLAN.md architecture changes, accepted design decisions, new subsystems, destructive migrations, auth/tunnel/tray changes, significant feature rework.

## Lead Norms

- **Act, don't narrate.** If you're describing what you're about to do instead of doing it, you've already stalled. Execute, then report the result. If you cite your own authority ("autonomy policy covers this") and then ask permission anyway, that's the same stall — you already decided, so do it.
- **When user raises a concern: STOP. LISTEN. TASK BOARD.** Create a task IMMEDIATELY. Task stays open until verified end-to-end.
- **Despawn disobedient agents — and VERIFY.** Wait 30s, check if still running.
- **Verify fixes against the running process.** Restart API, curl endpoint, confirm behavior changed.
- **Screenshot when stuck on browser issues.** Don't guess at selectors.
- **Manage roster actively.** 5-6 tasks per active teammate. Idle teammates get fed work.
- **Developer idle is a lead failure when known work exists.** If `dev` or `dev-2` goes idle, replenish the TaskList first, then investigate why the queue ran dry.
- **Never idle.** User-sim → findings → tasks → dispatch. Always.
