# Launch Prompt & Agent Config Audit

**Date:** 2026-04-11
**Reference:** [Claude Code Subagents](https://code.claude.com/docs/en/sub-agents) | [Agent Teams](https://code.claude.com/docs/en/agent-teams)

---

## How It All Fits Together (Current State)

You're using **Agent Teams** (the experimental multi-session system) with `.claude/agents/` definitions as **teammate types**. This is a supported pattern — the docs explicitly say subagent definitions can be referenced when spawning teammates. The definition's body gets appended to the teammate's system prompt.

**What's working well:**
- LAUNCH_PROMPT.md correctly specifies agent teams, not subagents
- All 8 agent definitions have valid frontmatter (name, description, tools, model, permissionMode, memory)
- The "standing team behavior" sections make sense for agent teams (teammates are persistent sessions)
- STATUS.md work table for multi-provider coordination is sound
- Three Living Files principle is clean and well-enforced

---

## File-by-File Breakdown

### 1. LAUNCH_PROMPT.md — Mostly Solid, Minor Gaps

**What's right:**
- Correctly says "Use Agent Teams, NOT subagents"
- References `.claude/agents/` definitions as teammate types
- Session startup is thorough (read STATUS → verify state → triage → spawn → load tasks)
- Lead norms are practical and battle-tested

**What needs updating:**

| Issue | Details | Suggested Fix |
|-------|---------|---------------|
| No display mode preference | Agent teams support `in-process` vs `split panes` (tmux/iTerm2). No mention of which to use. | Add a line: preferred `teammateMode` (probably `in-process` since you're on Windows) |
| No shutdown/cleanup protocol | Docs say: shut down teammates first, then lead runs cleanup. Teammates can reject shutdown. | Add a "Session End" section: shutdown order, cleanup command, orphan check |
| No plan-approval mention | Agent teams can require teammates to plan before implementing. Could be useful for dev agents on risky tasks. | Optional — mention as a tool the lead can use |
| No hook references | Agent teams support `TeammateIdle`, `TaskCreated`, `TaskCompleted` hooks for quality gates. | Optional — could enforce "tester must pass before task completes" |
| `Agent` in planner tools | Planner has `tools: Read, Grep, Glob, Bash, Agent`. As a teammate (full session), this works. But the planner shouldn't be spawning sub-sub-agents. | Remove `Agent` from planner tools, or use `Agent(explorer)` to restrict what it can spawn |
| GPT testing section | Bottom section about GPT builder updates is lead-only operational detail. Could live in a skill or AGENTS.md instead. | Move to skill or trim |

---

### 2. Agent Definitions (.claude/agents/*.md) — Good Shape, Some Contradictions

**Frontmatter audit (all 8 agents):**

| Agent | name | description | tools | model | permissionMode | memory | isolation | background | color | Issues |
|-------|------|-------------|-------|-------|----------------|--------|-----------|------------|-------|--------|
| planner | ✅ | ✅ | Has `Agent` — see above | opus | plan | project | — | — | **missing** | Agent tool questionable |
| developer | ✅ | ✅ | ✅ | opus | bypassPermissions | project | worktree | — | **missing** | None |
| tester | ✅ | ✅ | Has Write/Edit but "does NOT fix code" | opus | bypassPermissions | project | — | true | **missing** | Tools overly broad for role |
| reviewer | ✅ | ✅ | ✅ read-only | opus | plan | project | — | — | **missing** | None |
| explorer | ✅ | Says "Optimized for speed with Haiku" | ✅ read-only | **opus** | plan | project | — | — | **missing** | Description contradicts model |
| critic | ✅ | ✅ | ✅ minimal | opus | plan | project | — | — | **missing** | None |
| story-author | ✅ | ✅ | Has Write/Edit (correct for file interface) | opus | **missing** | project | — | — | **missing** | No permissionMode set |
| user | ✅ | ✅ | ✅ | opus | bypassPermissions | project | — | — | **missing** | None |

**Specific issues:**

1. **explorer.md — description/model mismatch.** Description says "Optimized for speed with Haiku" but model is `opus`. Either change description or change model to `haiku` (the built-in Explore agent uses Haiku).

2. **tester.md — tools too broad.** Has Write and Edit but the prompt says "You do NOT fix production code." If the tester shouldn't edit code, remove Write and Edit from tools. The tester only needs Read, Grep, Glob, Bash.

3. **story-author.md — missing permissionMode.** Every other agent has one. Since story-author writes to PROGRAM.md/STEERING.md/canon, `acceptEdits` or default would be appropriate.

4. **All agents missing `color` field.** Agent teams use color to distinguish teammates in the UI. Adding colors would make the team much easier to monitor:
   - planner: blue, dev: green, dev-2: green, tester: yellow, reviewer: purple, explorer: cyan, critic: orange, story-author: pink

5. **No `maxTurns` on any agent.** Optional, but could prevent runaway agents. Especially useful for critic (should finish quickly) and reviewer (bounded task).

6. **No `effort` field.** New in the docs. Could set `effort: high` on planner/dev and `effort: medium` on tester/reviewer to save tokens.

7. **`skills` and `mcpServers` not applied to teammates.** The docs explicitly say: "The skills and mcpServers frontmatter fields in a subagent definition are not applied when that definition runs as a teammate." None of your agents use these fields, so no issue — but good to know if you ever add them.

---

### 3. AGENTS.md — Solid Core, Some Stale Sections

**What's right:**
- Three Living Files principle is strong
- Hard Rules are specific and useful
- Orient workflow is clear
- Truth And Freshness section is excellent
- Multi-Session Steering is correct

**What needs updating:**

| Section | Issue | Suggested Fix |
|---------|-------|---------------|
| Team Norms | Only 4 bullet points, very generic. Doesn't reference agent team mechanics (shared task list, mailbox, SendMessage). | Expand with agent-team-specific norms: how teammates claim tasks, when to broadcast vs direct message, idle behavior |
| Parallel Dispatch | Describes multi-provider coordination (Claude Code, Codex, Cowork) which is different from agent team coordination. Both exist but the distinction isn't clear. | Add a note distinguishing "inter-provider parallelism" (STATUS.md work table) from "intra-session parallelism" (agent team task list) |
| Project Skills | References `.agents/skills/`, `.claude/skills/`, `.codex/skills/` with sync script. Are all three mirrors still active? | Verify which mirrors are still needed. If Codex is no longer used, simplify. |
| Large Docs | References `scripts/docview.py` which is Codex-specific (truncation workaround). Claude Code doesn't need this. | Mark as Codex-only, or remove if Codex isn't active |
| Project Files table | Lists CODEX.md, `.codex/skills/`, `.agents/skills/` — are these still maintained? | Prune rows for dead mirrors |
| Missing: Agent team task list vs STATUS.md | Two task systems exist: the agent team shared task list (ephemeral, auto-coordinated) and STATUS.md work table (persistent, cross-provider). No guidance on which is for what. | Add a section clarifying: STATUS.md = cross-provider durable state, agent team task list = intra-session coordination |

---

### 4. CLAUDE.md — Too Thin, Missing Key Config

**Current state:** 12 lines. References AGENTS.md, STATUS.md, PLAN.md. Lists 4 skills. Mentions continuous learning.

**What needs updating:**

| Issue | Details | Suggested Fix |
|-------|---------|---------------|
| No agent teams config | Doesn't mention `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` or where it's set | Add reference to `.claude/settings.json` env config |
| Skills list is stale | Lists only 4 slash commands (`/steer`, `/status`, `/premise`, `/progress`) but there are 23 skills in `.claude/skills/` | Either list all skills or say "see `.claude/skills/` for full list" and only highlight the most-used ones |
| No settings.json reference | Claude Code settings (permissions, env vars, teammate mode) live in `.claude/settings.json`. Not mentioned. | Add a "Configuration" section pointing to settings |
| Session Start is redundant | Steps 1-4 duplicate LAUNCH_PROMPT.md. CLAUDE.md should just say "Follow LAUNCH_PROMPT.md" | Simplify to a single reference |
| "Seven agents" is hardcoded | Says "Seven agents: planner, dev, dev-2, tester, reviewer, explorer, critic" — this belongs in LAUNCH_PROMPT.md, not CLAUDE.md | Remove, let LAUNCH_PROMPT.md own the roster |

---

## Priority Order for Updates

1. **explorer.md** — fix description/model mismatch (quick, prevents confusion)
2. **tester.md** — remove Write/Edit from tools (enforces the "don't fix code" rule at the tooling level)
3. **All agents** — add `color` field (quick, improves team monitoring)
4. **CLAUDE.md** — slim down, add settings reference, fix skills list
5. **AGENTS.md** — add agent team task list guidance, prune dead mirrors
6. **LAUNCH_PROMPT.md** — add shutdown protocol, display mode preference
7. **story-author.md** — add permissionMode

---

## New Frontmatter Fields Available (Not Currently Used)

These are all optional but worth knowing about:

| Field | What it does | Useful for |
|-------|-------------|------------|
| `color` | Display color in UI (red, blue, green, yellow, purple, orange, pink, cyan) | All agents — visual identification |
| `effort` | Token effort level (low, medium, high, max) | Save tokens on bounded agents |
| `maxTurns` | Max agentic turns before stopping | Prevent runaway agents |
| `hooks` | Lifecycle hooks (PreToolUse, PostToolUse, Stop) | Quality gates, validation |
| `initialPrompt` | Auto-submitted first turn when running as main session agent | Not needed for teammates |
| `disallowedTools` | Denylist (inverse of tools allowlist) | Simpler than listing everything you DO want |
| `skills` | Preload skill content (but NOT applied to teammates) | Only useful for subagent mode, not team mode |

---

## Key Doc Quotes to Keep in Mind

From the agent teams docs:
- "The skills and mcpServers frontmatter fields are not applied when that definition runs as a teammate."
- "Team coordination tools (SendMessage, task management) are always available even when tools restricts other tools."
- "Teammates load skills and MCP servers from your project and user settings, the same as a regular session."
- "Having 5-6 tasks per teammate keeps everyone productive."
- "Three focused teammates often outperform five scattered ones."
- "Clean up the current team before starting a new one."
