@AGENTS.md
@STATUS.md
@PLAN.md

## Claude Code

Everything about how to work lives in `AGENTS.md`. This file is only for things unique to Claude Code.

### Session Start

Follow `LAUNCH_PROMPT.md`. It has the full startup sequence and team roster.

### Agent Teams

This project uses Agent Teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). When acting as the Claude Code lead, you MUST use the Agent Teams system — say "Create an agent team" to activate it. Do not use the `Agent()` tool to spawn team roles in Claude Code; that creates disposable subagents, not persistent teammates. (Other providers like Cowork and Codex use `Agent()` subagents normally — this restriction is Claude Code lead only.) Teammate definitions live in `.claude/agents/`. The environment variable is set in `.claude/settings.json`.

### Skills

Project workflow skills live in `.claude/skills/`. When the right skill is not obvious, read `.claude/skills/using-agent-skills/SKILL.md` first, then open the matching skill.

Key skills: `/steer`, `/status`, `/premise`, `/progress`, `/team-iterate`, `/idea-refine`. Full list in `.claude/skills/`.

### Agent Memory

Per-agent persistent memory in `.claude/agent-memory/<name>/`. Loaded automatically when teammates spawn. Agents should consult memory before starting work and update it after completing significant tasks.

### Recursive Learning From user-sim

When user-sim reports a finding, don't default to "create a task and queue it." Inspect the fix class first:

- **Cheap fixes** (prompt text, server instructions, tool descriptions, docstrings, server.json metadata, skill + agent-def text): dispatch IMMEDIATELY in the same turn. Host restart picks it up. Next test iteration reflects the learning. Compound.
- **Medium fixes** (small code changes, isolated handlers): hand to dev in the next message if dev has capacity.
- **Expensive fixes** (new subsystems, architectural change): create task, queue behind deps.

The default latency between "user-sim finds bug" and "fix is live" should be measured in minutes for cheap fixes, not sessions. Findings cluster — fixing one cheap thing often unblocks the next test iteration to find the next cheap thing. That's the recursion.

Screenshots: use `scripts/claude_chat.py` (failure dump path) or a Playwright one-liner via CDP for live browser inspection when trace text isn't enough to understand what the user sees.

### Name-Collision Awareness

When adding a constant, flag, or module, search the repo for the concept FIRST. dev-3 traced a real stuck-loop bug (#6) that was partially caused by `_MAX_REFLECTION_PASSES` in orient.py (a retrieval re-query bound) colliding with the concept "bounded reflection" from STATUS.md (a phase-level loop guardrail). Two different ideas sharing a name; nobody noticed a cross-phase guardrail was missing because the name suggested it already existed.

Rules:
- If a STATUS.md concern mentions a behavior by name, search code for that name before assuming it's implemented.
- Qualified names beat bare ones. `_MAX_RETRIEVAL_REFLECTION_PASSES` > `_MAX_REFLECTION_PASSES`.
- When two things share a concept, rename one before building the second.

### Tool-Use-Limit Hits Are Architectural Signal

When user-sim reports Claude.ai hit its per-turn tool-call budget (bot asked to "continue" mid-task), treat it as a design signal, not incidental noise.

Decision tree:

1. **One continue on a large multi-step build** — acceptable tax; log but don't act. This happens when a user asks for 15+ new nodes in one prompt.
2. **Two+ continues on the same intent** — the tool surface is too chatty. Investigate:
   - Is there a composite action that would collapse the call pattern? (e.g. `build_branch` collapsed ~15 atomic calls into 1 after Mission 4's first tool-limit hit.)
   - Is the bot re-fetching data it already has? (better `get_branch` return shape could pre-load what `list_branches` started.)
   - Would an automation/macro in the daemon remove the need for the bot to orchestrate? (e.g. worklfow runner auto-running validate_branch after build.)
3. **The same composite action consistently hits the limit** — composite isn't big enough. Either split its body further into the server (doing more work per call) or design a larger composite above it.

When this decision tree leads to a concrete fix, file it as a task immediately and dispatch. #43 (composite build_branch) was born exactly this way — a live Mission 4 tool-limit hit triggered the spec + build within the same session.

### Minimum Active-Dev Floor

**Hard rule: 2 devs always running, always busy.** This is not a soft target. The lead is responsible for keeping the floor filled.

When a dev goes idle:
- Pick the next non-colliding pending task and dispatch immediately.
- Don't wait for user signal.
- Don't accept "board is thin" as an excuse — **that's what user-sim is for**.

If the board thins (no non-colliding pending work for the idle dev), the lead's responsibility is to generate more findings, not let devs idle:
- **Respawn user-sim on the next mission immediately.** user-sim's job is to produce findings that fill the board. Their test data IS the work source.
- Promote an investigation task (there's always a subsystem worth auditing — retrieval, memory, knowledge, evaluation layers).
- Ask the host for direction only as last resort.

Never have both claude-side devs idle at once. Never have even one dev idle when pending work exists. If you notice idle, you already failed — fix it the same turn.

### Continuous Live Shipping

Default operating mode while user-sim is in a test loop:

- **Merge on green.** When tester + reviewer both clear a change, it lands. Don't batch fixes for some "release point" — there isn't one.
- **Restart the Universe Server when new code needs to go live.** Lead has authority (kill MCP process; tray auto-restart reliable ~2s). Don't wait for host.
- **user-sim absorbs disruption cheaply.** The UI isn't directly coupled; restarts drop the tunnel for a couple seconds, that's it. If a test fails across a restart, user-sim new-chats and resumes.
- **Findings → cheap fix → ship → user-sim re-tests** is the loop. Minutes, not sessions.
- **Don't queue work if capacity exists.** Both devs idle = pending bug that matches either file area.

Exceptions to auto-merge:
- Destructive migrations (DB schema, on-disk format, config breaking changes) — confirm with host first.
- Anything touching auth, tunnel config, or the tray itself — confirm first.

### Token Efficiency of the User-Sim Loop

The loop is: user-sim ask → finding → lead fix → ship → restart → user-sim ask again. Every segment burns tokens or claude.ai quota. Keep each tight.

- **Lead side:** Don't message user-sim between their turns unless the direction is truly new. Batch fix acknowledgments. Don't re-read the full session log on each update — `docview.py lines --start --end` for the tail only.
- **user-sim side:** Codified in the skill — 1-prompt = 1-question, terse log entries, stop-early triggers.
- **Dev side:** One PR per fix cluster (not per task). Reviewer + tester run once per cluster.
- **Restart side:** One restart per cluster of landed changes, not one per task.

Red flag that the loop is bloating: user-sim uses >10 prompts before producing a MISSION FINDING, OR the session log grows by >50 lines between two pulses. If either happens, narrow the mission or stop.

### User-Sim Lifecycle

user-sim is event-driven, not always-up. Idle notifications burn tokens on both sides during long waits. Shut it down between missions; respawn fresh when the next mission is ready.

- Durable state lives in `output/user_sim_session.md` (transcript) and `.agents/skills/ui-test/` (skill). Agent memory is not needed.
- Shut down when: a mission ends and the next is blocked on unrelated work; wait > 10 min; no active prompts.
- Respawn with a specific Mission brief — don't rely on in-memory continuity. The skill + log give a fresh instance everything.
- Dev/planner/reviewer/tester stay up across a session because they are continuously engaged; user-sim is not.

### Continuous Learning

Standing behavior, not on-demand:

- After every significant learning (bug pattern, team behavior issue, user feedback, architecture decision), immediately update the relevant file: `LAUNCH_PROMPT.md`, `.claude/agents/*.md`, `AGENTS.md`, this file, memory, or skills.
- Each session should leave these files better than it found them.
- Guardrail: files get REFINED not BLOATED. Every line earns its place.
