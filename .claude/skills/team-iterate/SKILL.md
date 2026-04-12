---
name: team-iterate
description: Review and improve agent team definitions and the launch prompt based on observed behavior this session.
user_invocable: true
---

Iterate the agent team based on what actually happened. Agent definitions evolve through USE, not upfront planning.

## Before making changes

Research current best practices for AI agent team design, prompt engineering for agent personas, and multi-agent coordination. Check Anthropic's latest guidance on agent teams, harness design, and prompt patterns. Don't just write from memory.

## What to review

1. **LAUNCH_PROMPT.md** — Does the startup sequence still work? Are the team norms right? Did we learn new norms this session?

2. **Each agent in `.claude/agents/`:**
   - **planner.md** — Did planner provide good strategic direction? Was it too verbose or too terse? Did it make architecture decisions it shouldn't have?
   - **developer.md** — Did dev ship code reliably? Did it go silent? Does it need stronger "report immediately" language?
   - **tester.md** — Did tester run proactively? Did it catch regressions? Did it flag the right things?
   - **reviewer.md** — Did reviewer catch real issues? Was feedback specific enough? Did it review without being asked?
   - **explorer.md** — Was research fast and accurate? Did it jump in proactively when teammates needed context?
   - **debugger.md** — Did it find root causes? Was diagnosis systematic? Did it fix things cleanly?

3. **Team composition** — Should any agents be added, removed, or combined? Are six the right number?

## How to iterate

- Read the agent definition
- Compare against observed behavior this session
- If behavior was good → note what worked (don't change what isn't broken)
- If behavior was poor → identify the specific failure, update the prompt to address it
- If an agent went silent → add explicit "never go silent, report within 60 seconds" language
- If an agent was respawned → update the definition with whatever made the respawn work better

## Standing principles

- The full team is ALWAYS running. Never dismiss teammates.
- When an agent isn't performing, refine and respawn — don't wait.
- After 2 unanswered messages, respawn with a sharper prompt.
- Agent definitions are living documents — update after every session.
