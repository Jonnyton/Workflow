Read `STATUS.md` first (live state), then `PLAN.md` (principled architecture).

## Team Spawn

Create an agent team for Fantasy Author. Use Agent Teams (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS enabled). Do NOT use subagents — they auto-complete and can't persist.

### Core Team (always spawn)

Four teammates, all Opus, using `.claude/agents/` definitions:

1. **planner** (planner agent type) — strategic thinker. Owns WHAT and WHY.
2. **dev** (developer agent type) — writes code + debugs. Trusted to figure out HOW.
3. **tester** (tester agent type) — quality gate. Runs tests PROACTIVELY after every dev change. Background.
4. **reviewer** (reviewer agent type) — permanent code reviewer. Auto-notified on every TaskCompleted. 1 reviewer per 3-4 builders. Lead only sees green-reviewed code.

### On-Demand (spawn when needed)

Spawn these when the work requires them. Despawn when their task is done.

- **dev-2** (developer agent type) — second developer. Spawn when parallel file work exists with no overlap. Despawn after.
- **explorer** (explorer agent type) — deep codebase research. Spawn when planner or dev needs heavy context gathering that would blow up their context window. Despawn after reporting.
- **critic** (critic agent type) — creative quality assessor. Spawn when daemon output exists to review. Despawn between batches.
- **story-author** (story-author agent type) — creative collaborator. Spawn when user wants to work on story, steering, or canon.

**user agent** — NOT auto-spawned. Spawn manually when GPT testing needed and rate limit budget allows. See `.claude/agents/user.md`.

Lead absorbs debugger coordination: bug tasks go to dev with diagnostic framing.

## Session Startup

1. Read `STATUS.md` (full board, top to bottom) then `PLAN.md` (principled architecture).
2. Verify state — `git log --oneline -5`, check API (`curl localhost:8321/v1/health`). If not running, ask user (rate limit budget).
3. Triage Watch: increment session counts, check verifications are real, demote shallow to Work.
4. Reorder Work using ordering principles (AGENTS.md). Trace pipelines end-to-end.
5. Spawn the core team (4 teammates — NOT user agent, NOT on-demand agents).
6. Load Work items into session task list. Break STATUS.md items into teammate-sized tasks.
7. Pick up the highest Work item and start.
8. If API is running and code changes affect it, restart and verify.

## Session End

1. Ensure STATUS.md is current — all completed work reflected, new concerns captured.
2. Shut down on-demand teammates first (they can reject if mid-task — wait and retry).
3. Shut down core teammates.
4. Run team cleanup after all teammates confirm shutdown.
5. Update `.agents/activity.log` with session summary.

## Lead Norms

- **When user raises a concern: STOP. LISTEN. TASK BOARD.** Don't jump to fixing. Create a task IMMEDIATELY. If it's a pattern, the task is the pattern. Task stays open until verified end-to-end.
- **If the user drops a new idea that is not being executed now, capture it in `ideas/INBOX.md` or promote it through `ideas/PIPELINE.md` before the turn ends.**
- **Despawn disobedient agents — and VERIFY.** Wait 30s, check if still running, tell user if can't force-kill.
- **Verify fixes against the running process.** Restart API, curl endpoint, confirm behavior changed.
- **Screenshot when stuck on browser issues.** Don't guess at selectors.
- **Build robust from the start.** "For now" costs 5x later.
- **STATUS.md is always live.** Never ask "want me to update?" — should already be current.
- **Manage roster actively.** Spawn on-demand teammates when work appears, despawn when done. Verify team config after spawn/despawn.
- **Assume other providers may be live.** File-backed coordination beats any single chat window.
- **Right-size the team.** 5-6 tasks per active teammate. If teammates are idle, despawn them. If work is piling up, spawn help.

## GPT Testing

Read `/gpt-test` skill. Manual — only when lead decides and rate limit budget allows.

GPT builder updates (lead only):
```bash
python -m fantasy_author.testing.gpt_builder update-all   # instructions + schema + save
```

See AGENTS.md > "GPT Conversations Are Bug Reports" for handling pasted conversations.
