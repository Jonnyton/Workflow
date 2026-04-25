---
name: team-iterate
description: Reviews and improves agent team definitions and launch prompts based on observed behavior. Use when a teammate underperforms, roles overlap, the launch prompt needs tuning, or the user asks to iterate the agent team.
---

Iterate the agent team based on what actually happened. Agent definitions evolve through USE, not upfront planning.

This skill MUST NOT enumerate the current team by name. The roster changes; this skill should not. Read the roster fresh every time from `.claude/agents/` and rubric the agents that are actually there.

## Before making changes

Research current best practices. Pin the upstream:

- Claude Code agent teams: https://code.claude.com/docs/en/agent-teams
- Subagent definitions (the format used in `.claude/agents/`): https://code.claude.com/docs/en/sub-agents

Check Anthropic's latest guidance on agent personas and multi-agent coordination — features and norms shift release-to-release. Don't write from memory.

## What to read

1. **`LAUNCH_PROMPT.md`** — the source of truth for which teammates are spawned, in what order, with what mandate. If this skill and `LAUNCH_PROMPT.md` disagree, `LAUNCH_PROMPT.md` wins.

2. **The current roster: `.claude/agents/*.md`** (skip `retired/`). For each file, read the frontmatter `description` and the body. Use the agent's *own* stated job as the rubric — do not assume role shapes that this skill happened to know about when it was written.

3. **`AGENTS.md`** for project-wide norms; **`STATUS.md`** for in-flight work that may have stressed the team.

## Rubric — apply to every active agent

For each teammate definition in `.claude/agents/`, evaluate against these axes. None of these mention specific role names:

- **Mandate clarity** — does the prompt make ownership unambiguous (what this agent owns vs. consults on vs. ignores)?
- **Responsiveness** — did it go silent this session? Did "report within 60s" / "never go silent" language hold? If respawned, what made the respawn work?
- **Evidence discipline** — does it bring evidence (code paths, web sources, test runs) proportional to its claims, or does it assert?
- **Hand-off shape** — clean inputs/outputs to adjacent roles, or muddied? Did downstream agents get what they needed in the form they needed it?
- **Standing-team behavior** — does it idle correctly between tasks, or exit prematurely? Does it self-claim from the shared task list when free?
- **Earning its keep** — given the current model, is this role still adding value, or is the model strong enough to absorb it into an adjacent role?

For the team as a whole:

- **Coverage gaps** — work this session that fell between roles, or got duplicated across roles?
- **Composition** — should any agents be added, combined, retired? Is the active core the right size (Anthropic guidance: 3–5 teammates is the sweet spot)?

## Harness alignment — verify against the docs

The agent-teams harness has capabilities the team prompts may not be using. Each iteration, ask:

- Are we using `TeammateIdle` / `TaskCreated` / `TaskCompleted` hooks where they would help?
- Do any roles need plan-approval gates or read-only behavior? In agent-team mode, do not assume `permissionMode` frontmatter is enforced per teammate; verify with current docs and prefer tool allowlists, spawn instructions, and hooks.
- Are tasks sized to the 5–6/teammate guidance? Is the lead splitting work small enough?
- Are we using `message` (one teammate) vs `broadcast` (all) deliberately? Broadcast cost scales with team size.
- Does cleanup ordering match the docs (on-demand teammates shut down first, then core, then `cleanup`)?

If a capability would help and isn't being used, propose updating the agent definition or `LAUNCH_PROMPT.md`, not this skill.

## How to iterate

- Read each agent definition in `.claude/agents/` against the rubric above.
- If behavior was good → record what worked in `.agents/activity.log` so it survives. Don't change what isn't broken.
- If behavior was poor → identify the specific failure, update *that agent's* prompt (or `LAUNCH_PROMPT.md` if it's a team-level norm) to address it.
- If a fix is general (applies to any future role too) → it belongs in `AGENTS.md` or this rubric, not in a single agent definition.
- If the team shape changed (added/retired a role) → update `LAUNCH_PROMPT.md` only. This skill should not need editing.

## After editing

Skill files are mirrored. The canonical source is `.agents/skills/`; after editing, run:

```
powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1
```

…to push changes into `.claude/skills/`. Codex reads `.agents/skills/` directly — no separate Codex mirror.

## Standing principles

- The core team named by `LAUNCH_PROMPT.md` stays running. On-demand roles follow the lifecycle in `LAUNCH_PROMPT.md`; don't keep token-heavy specialists up just because this skill exists.
- When an agent isn't performing, refine and respawn — don't wait.
- After 2 unanswered messages, respawn with a sharper prompt.
- Agent definitions are living documents — update after every session.
- This skill is a framework, not a roster. If you find yourself wanting to write a role name into this file, write it into `LAUNCH_PROMPT.md` instead.
