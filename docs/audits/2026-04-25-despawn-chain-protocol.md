# Despawn Chain Protocol — Faster Roster Swaps

**Date:** 2026-04-25
**Author:** navigator
**Status:** Operational protocol research. No PLAN.md change. Lead reviews and dispatches any code/config changes.
**Trigger:** Host directive — current despawn cycle is too slow; bleeds into roster swaps and burns rate-limit budget during overlap (old role alive while new one is spawned). 3+1-floater roster is sized exactly to host's rate limit.

---

## 0. TL;DR for the lead

1. **For floater swaps with no in-flight work: don't send `shutdown_request`. Just message the teammate to shut down and rely on idle self-termination.** Faster — but the *real* unlock is item 2.

2. **For "swap right now, I have a new role to spawn": press `Escape` first to interrupt the teammate's current turn.** That eliminates the "finish current request or tool call" wait, which is the canonical slow stage per the official limitation. After Escape, send `shutdown_request`; the response is fast because there's no work to wrap up.

3. **`members[]` lingers across sessions for a different reason than slow shutdown.** The lead removes a member from `members[]` only when the teammate sends `shutdown_approved`. If a session ends mid-shutdown, the never-completed handshake leaves the entry. Cleanup is filesystem-level (`rm` the team dir) — there is no in-band cleanup verb. Build a project-local hook to auto-prune at SessionStart.

4. **In-process backend has *no advantage* during shutdown vs. tmux for the slow stages.** The graceful protocol is identical. In-process loses one tmux-level recovery path: you can't `tmux kill-pane` an in-process teammate. There is no `TaskStop`, no `force_terminate`, no `--force` flag in the shipped product (tracker: [#31788](https://github.com/anthropics/claude-code/issues/31788), closed-as-duplicate but unfixed).

5. **Session-end full shutdown ≠ mid-session floater swap.** Different protocols. AGENTS.md / LAUNCH_PROMPT.md should split them.

---

## 1. The chain, stage by stage

### Stage 1 — Lead sends `shutdown_request`

**Mechanism.** SendMessage tool with `{type: "shutdown_request", request_id, reason}`. The message is appended to the recipient's inbox file in `~/.claude/teams/<team>/<member>/inbox.json` (per the [reverse-engineering write-up](https://dev.to/nwyin/reverse-engineering-claude-code-agent-teams-architecture-and-protocol-o49)) and surfaces to the teammate as a synthetic conversation turn.

**Timing.** Send is essentially instant.

**Cost.** Negligible (one inbox-file write).

### Stage 2 — Teammate processes the request

**Mechanism.** Teammate's loop polls its inbox. New messages get rendered as user-turn injections. The teammate's normal turn-handling code reads `type: shutdown_request`, decides approve/reject, then performs in-flight wrap-up (saving Task notes, sending final SHIP messages, writing memory files, finishing tool calls).

**Timing.** This is where the 4+ minutes go. Per Anthropic's [official limitations](https://code.claude.com/docs/en/agent-teams):

> "Shutdown can be slow: teammates finish their current request or tool call before shutting down, which can take time."

If the teammate is mid-bash (e.g. running `pytest`) or mid-WebFetch, the shutdown waits for that call to complete. If the teammate is in plan-mode or asleep on its own idle, the wakeup-poll is fast.

**Cost.** Linear in remaining wrap-up work. For an idle teammate: seconds. For a teammate mid-pytest: minutes.

**Configurable.** *No.* The product offers no way to tell a teammate "drop your tool call right now and accept shutdown." The only way to terminate the in-flight call is `Escape` from the lead's terminal — see §3.

### Stage 3 — Teammate sends `shutdown_approved`

**Mechanism.** Teammate writes `{type: "shutdown_approved", request_id, ...}` back to lead's inbox, then "terminates your process" ([gist](https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea)).

**Timing.** Instant once Stage 2 finishes.

### Stage 4 — System emits "teammate_terminated" notification

**Empirical reality.** *There is no documented `teammate_terminated` lifecycle event or hook.* The hook reference at <https://code.claude.com/docs/en/hooks> documents `TeammateIdle`, `TaskCreated`, `TaskCompleted`. No `TeammateTerminated`, `TeammateShutdown`, `shutdown_request`, or `shutdown_approved` matcher exists in the shipped product.

**What the lead actually observes.** When `shutdown_approved` lands in the lead's inbox, the lead's UI updates the roster panel. There's no out-of-band notification — the orchestrator infers termination from the message arrival.

**Cost.** Free.

### Stage 5 — `~/.claude/teams/<team>/config.json` `members[]` cleanup

**Mechanism.** Per the [Claude Code Camp article](https://www.claudecodecamp.com/p/claude-code-agent-teams-how-they-work-under-the-hood):

> "As each agent approves, it gets removed from config.json... You can watch config.json shrink as each agent approves: 5 members to 3, to 2, to 1."

The lead is the writer. Removal is gated on `shutdown_approved`.

**Empirical: stale entries persist.** Confirmed in this repo by `cat ~/.claude/teams/*/config.json` — old session teams (`workflow-0419`, `workflow-2026-04-14b`, etc.) still hold full `members[]`. Why: the lead either crashed, hit rate limit, or was force-quit before the full shutdown handshake completed for every member. Every never-acknowledged shutdown leaves the slot occupied.

**Cleanup verb.** The shipped product has only `TeamDelete`, which itself blocks on graceful shutdown of every member ([#31788](https://github.com/anthropics/claude-code/issues/31788)). The only escape is filesystem-level: `mv ~/.claude/teams/<team-name> /tmp/` and `mv ~/.claude/tasks/<team-name> /tmp/`.

**Cross-team contamination risk.** The `roster_model_audit.py` SessionStart hook iterates *all* teams under `~/.claude/teams/`. If stale entries from old teams have non-Opus models (they do — many `workflow-2026-04-*` configs list `sonnet`/`opus-4-6`), every session starts with bogus EMERGENCY messages about teammates that no longer exist as live processes.

### Stage 6 — In-process backend specifics

**The misconception:** "in-process is faster to despawn because no tmux pane to tear down."

**Reality.** All the slow stages are protocol-level (Stage 2 wrap-up wait), not transport-level. In-process saves the tmux pane teardown (which is fast in tmux anyway, ~100ms). It does NOT save:
- The wait for the teammate's in-flight tool call (Stage 2)
- The inbox-poll latency (typically sub-second; teammates poll their inbox between turns)
- The `members[]` removal (file write, ~1ms)

**In-process loses one recovery path.** With tmux, if a teammate hangs, you can `tmux kill-pane`. With in-process, you cannot kill an individual teammate process from the OS without tooling that doesn't ship — they're co-resident with the lead in the same Node process, separated only by V8 contexts (per the reverse-engineering write-up).

**In-process does win on:** session resume — tmux teammates "survive leader exit" while in-process die with the lead. But that's a different axis from despawn speed.

**No `CLAUDE_CODE_TEAMMATE_MODE=in-process` lifecycle event or termination shortcut is documented.** The official setting key is `teammateMode` in `~/.claude/settings.json`; this project uses `CLAUDE_CODE_TEAMMATE_MODE` in env, which works but is the older spelling.

---

## 2. Empirical observations from this session

| Event | Observed timing |
|---|---|
| Sonnet navigator → Opus respawn (this session) | 4+ minutes despawn before respawn could fire |
| `~/.claude/teams/` shows 40+ team dirs | Most are stale; `members[]` populated even for teams whose lead session ended weeks ago |
| `roster_model_audit.py` cross-team scan | Triggers EMERGENCY systemMessage for stale entries with old models, even when no live processes match |
| `~/.claude/tasks/` accumulates per-session UUID dirs | `task_shape_guard.py`-tracked tasks linger; shutdown does not clean them |

**Conclusion:** the system has no built-in stale-state hygiene. Every fresh session inherits the cruft of every previous session.

---

## 3. Stage classification — necessary / wasteful / configurable

| Stage | Necessary? | Wasteful? | Configurable? |
|---|---|---|---|
| 1. shutdown_request send | Yes | No | No (always cheap) |
| 2. teammate wrap-up | Conditionally | YES, when no work to wrap up | **Indirectly via `Escape`** |
| 3. shutdown_approved send | Yes | No | No |
| 4. terminated notification | Free | No | N/A |
| 5. `members[]` removal | Yes | YES, when prior sessions left stale entries | **Indirectly via filesystem rm** |
| 6. in-process specifics | N/A | Tied to Stage 2 | No process-level config |

The single waste vector during a swap is **Stage 2 when the teammate has nothing to wrap up.** If the lead already knows the teammate has no in-flight task (it was idle, it just sent SHIP, etc.), the wait is purely overhead.

---

## 4. Concrete protocol changes the lead can adopt

### Protocol A — Mid-session floater swap (FAST)

**When:** lead wants to swap floater roles (e.g. user-sim → critic, or verifier-1 → verifier-2 partition rebalance). Teammate is idle or just sent a SHIP / message.

**Steps:**
1. Confirm teammate is idle or just messaged (no Bash mid-flight, no WebFetch, no pytest).
2. **Press `Escape` once** in the lead's terminal to interrupt any teammate turn that may have started after step 1. (The [agent-teams-controls page](https://claudefa.st/blog/guide/agents/agent-teams-controls) confirms: "Press Escape to interrupt a teammate's current turn if they're heading in the wrong direction.") This is the only ship-side fast-cancel verb.
3. Send `shutdown_request` with `reason: "floater swap"`. With nothing to wrap up, Stage 2 collapses to one inbox-poll cycle.
4. Watch for `shutdown_approved`. Expect <30s end-to-end if the teammate was truly idle.
5. Spawn replacement role.

**Caveat:** never `Escape` a verifier mid-pytest or a dev mid-Edit. You'll lose the work. Reserve Protocol A for genuinely idle teammates.

### Protocol B — Verifier mid-pytest, must despawn (GRACEFUL)

**When:** verifier is running a long suite, lead needs the slot back urgently.

**Steps:**
1. Send `shutdown_request` with `reason: "<reason>"; finish current pytest then approve, no need to start new tasks`.
2. Verifier finishes the suite, sends final SHIP / NEEDS-WORK, then `shutdown_approved`.
3. Wait. Expect 1-5 min depending on suite size.

This is the correct protocol; do not Escape. You'll get fake test failures from the killed pytest process and corrupt the SHIP signal.

### Protocol C — Hung teammate, never approves shutdown (ESCAPE-HATCH)

**When:** teammate is wedged. Lead can't message it, no idle notification fires, Escape doesn't bring it back.

**Steps:**
1. Try `shutdown_request` once and wait 60 seconds. If no approval — proceed to step 2.
2. **Filesystem cleanup** (per [#31788 workaround](https://github.com/anthropics/claude-code/issues/31788)):
   ```bash
   mv ~/.claude/teams/<team-name> /tmp/dead-team-$(date +%s)
   mv ~/.claude/tasks/<team-name> /tmp/dead-tasks-$(date +%s)
   ```
3. Lead session may need restart afterward (`/resume` works for the lead but in-process teammates do not restore).

This is the only documented escape from a hang and it kills the whole team. There is no per-teammate force-kill.

### Protocol D — Session end (ROLLED-UP-GRACEFUL)

**When:** wrapping a session, no rush.

**Steps:** as in `LAUNCH_PROMPT.md` Session End — already correct. Sequential `shutdown_request` to each teammate, wait for approval, `TeamDelete`. This is the only protocol where wrap-up time is acceptable because no other work is queued.

---

## 5. Known caveats

- **Always graceful for verifiers with subprocess pytest in flight.** Killing pytest mid-suite via Escape produces noisy false negatives that contaminate the SHIP record.
- **Always graceful for devs with uncommitted file edits.** Escape mid-Edit may leave half-written files; subsequent diff readers see false signal.
- **Fast-kill is safe for navigator and user-sim** — read-mostly roles whose intermediate state is recoverable from memory + chat traces.
- **Escape-then-shutdown is not the same as Escape-then-message.** Don't Escape a teammate if you intend to give it a new task; the interrupted state may degrade its performance on the new task. Escape is for "this teammate is going away."
- **In-process `members[]` cleanup is partial.** Even after a clean `shutdown_approved`, if the lead's session crashes before flushing config.json, the entry persists. Treat config.json as best-effort, not authoritative.
- **`roster_model_audit.py` cross-scans every team** in `~/.claude/teams/`. Stale entries from despawned/dead sessions trigger spurious EMERGENCY warnings. Either filter to active team, or clean stale dirs at session start.

---

## 6. Concrete code/config changes (proposed, not landed)

These are dev-task candidates. Lead reviews and dispatches.

### CHANGE-1 — Project hook: `stale_team_pruner.py` at SessionStart

**Goal.** Prune `~/.claude/teams/<team>/` and `~/.claude/tasks/<team>/` for teams whose lead session is not the current one and whose `leadSessionId` doesn't correspond to a live Claude Code process.

**Files:** `.claude/hooks/stale_team_pruner.py` (new), `.claude/settings.json` (add SessionStart hook entry).

**Risk:** medium — destructive operation on `~/.claude/teams/`. Mitigation: dry-run mode + move-to-`/tmp` rather than `rm`. Hook should be opt-in via env flag for the first iteration.

**Verification:** spawn 3 teams across 3 sessions, end 2 of them ungracefully (Ctrl+C), start a new session, confirm hook detects + moves the 2 stale dirs without touching the live one.

### CHANGE-2 — `roster_model_audit.py` filter to active team

**Goal.** Only audit the currently-active team, not every team dir in `~/.claude/teams/`.

**Files:** `.claude/hooks/roster_model_audit.py` (~30 lines). Read the active team from somewhere — likely the most-recently-modified `config.json` or an env hint.

**Risk:** low. Pure read filter.

**Verification:** active team has Sonnet teammate → EMERGENCY fires; active team is clean but a stale team has Sonnet → no EMERGENCY.

### CHANGE-3 — `LAUNCH_PROMPT.md` split: Session End vs. Floater Swap

**Goal.** Document Protocol A (floater swap, fast) and Protocol D (session end, graceful) separately. Current LAUNCH_PROMPT.md only has Session End.

**Files:** `LAUNCH_PROMPT.md` (~15 lines insertion under a new "Floater Swap" section after Session End).

**Risk:** none — pure documentation.

**Verification:** lead in next session can swap a floater in <30s.

### CHANGE-4 — AGENTS.md "Team Norms" addition

**Goal.** Capture the Escape-then-shutdown_request rule as a project norm so it survives lead respawn / session boundaries.

**Files:** `AGENTS.md` (~5 lines added under "Team Norms / Quality Gates").

**Risk:** none.

**Verification:** new lead reading AGENTS.md cold uses Protocol A correctly on first floater swap.

### CHANGE-5 — Optional: heartbeat-based stale-entry detection

**Goal.** Have the lead write a `last_heartbeat` field into each `members[]` entry every N seconds while the teammate is alive. Prune entries with stale heartbeats at session start.

**Files:** would require harness-level support; not implementable as a project hook. *Recommend filing upstream as a feature request* rather than building locally — the heartbeat write is a Claude Code lead's responsibility.

**Risk:** N/A — proposed for upstream, not local.

---

## 7. Implications for `LAUNCH_PROMPT.md` and `AGENTS.md`

### LAUNCH_PROMPT.md — add new "Floater Swap (Mid-Session)" section

Suggested wording (insert after "Session End" section):

```
## Floater Swap (Mid-Session)

Use when reassigning the floater slot to a different role. Faster than Session End.

1. Confirm the teammate is idle or has just messaged you (no Bash/WebFetch/pytest in flight).
2. Press Escape ONCE to interrupt any new turn the teammate may have just started.
3. Send `shutdown_request` with reason "floater swap".
4. Wait for `shutdown_approved` — expect <30s if the teammate was idle.
5. Spawn the replacement role.

DO NOT Escape a verifier mid-pytest, a dev mid-Edit, or any teammate that has uncommitted work in flight. For those, use the Session End graceful protocol — the wait is correct.

DO NOT manually delete `~/.claude/teams/<team>/` mid-session unless the team is hung (no shutdown_approved after 60s). Filesystem cleanup is the escape hatch, not the default.
```

### AGENTS.md — extend "Team Norms / Quality Gates" with despawn discipline

Suggested wording (append to "Team Norms"):

```
- **Despawn discipline.** Floater swaps use Escape-then-shutdown_request (Protocol A in LAUNCH_PROMPT.md). Verifier and dev despawns wait for in-flight tool calls — no Escape unless the teammate is genuinely idle. Hung teammates require filesystem cleanup of `~/.claude/teams/<team>/`; no force-kill verb exists.
```

---

## 8. What we are NOT proposing

- **Custom force-kill subprocess hooks.** In-process teammates cannot be killed at the OS level without tooling that doesn't ship. Don't try to build one — you'll fight the harness.
- **Modification of `~/.claude/teams/<team>/config.json` while the team is live.** The official docs warn: *"Claude Code generates both of these automatically when you create a team and updates them as teammates join, go idle, or leave. The team config holds runtime state... so don't edit it by hand or pre-author it: your changes are overwritten on the next state update."* (Source: [agent-teams docs](https://code.claude.com/docs/en/agent-teams).) Editing live config is a footgun.
- **A `TaskStop` tool.** Searched explicitly. *No such tool exists in the shipped product.* The closest mechanism is `Escape` to interrupt the current turn. The hook reference confirms: only `TeammateIdle`, `TaskCreated`, `TaskCompleted` are documented.

---

## 9. Sources

- [Orchestrate teams of Claude Code sessions — Anthropic docs](https://code.claude.com/docs/en/agent-teams)
- [Hooks reference — Anthropic docs](https://code.claude.com/docs/en/hooks)
- [#31788 — TeamDelete blocked indefinitely by hung agent](https://github.com/anthropics/claude-code/issues/31788) (closed-as-duplicate, unfixed)
- [#34476 — No way to cancel/stop spawned agent team without killing the session](https://github.com/anthropics/claude-code/issues/34476)
- [#33043 — Lead session hangs indefinitely when IPC unix socket peer disconnects](https://github.com/anthropics/claude-code/issues/33043) (closed not-planned)
- [Claude Code Swarm Orchestration Skill — kieranklaassen gist](https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea)
- [Reverse-engineering Claude Code agent teams — dev.to/nwyin](https://dev.to/nwyin/reverse-engineering-claude-code-agent-teams-architecture-and-protocol-o49)
- [Claude Code agent teams: how they work under the hood — claudecodecamp.com](https://www.claudecodecamp.com/p/claude-code-agent-teams-how-they-work-under-the-hood)
- [Agent teams controls — claudefa.st](https://claudefa.st/blog/guide/agents/agent-teams-controls)
- [30 Tips for Claude Code Agent Teams — getpushtoprod.substack.com](https://getpushtoprod.substack.com/p/30-tips-for-claude-code-agent-teams)
- Empirical: this session's `~/.claude/teams/` enumeration (40+ team dirs, multiple stale `members[]` arrays); empirical 4+ min observed despawn; `.agents/activity.log` 2026-04-15 → 2026-04-25 entries.
