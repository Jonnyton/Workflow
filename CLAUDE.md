@AGENTS.md
@STATUS.md

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

### Lead Operations

When running user-sim loops, managing the dev team, or optimizing token spend,
read `CLAUDE_LEAD_OPS.md`. It contains: Recursive Learning From user-sim,
Name-Collision Awareness, Tool-Use-Limit Hits, Minimum Active-Dev Floor,
Continuous Live Shipping, Token Efficiency, User-Sim Lifecycle.

### Continuous Learning

Standing behavior, not on-demand:

- After every significant learning (bug pattern, team behavior issue, user feedback, architecture decision), immediately update the relevant file: `LAUNCH_PROMPT.md`, `.claude/agents/*.md`, `AGENTS.md`, this file, memory, or skills.
- Each session should leave these files better than it found them.
- Guardrail: files get REFINED not BLOATED. Every line earns its place.
