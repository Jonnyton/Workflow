---
name: ui-test
description: Simulate a Claude.ai phone user driving the Universe Server via the custom MCP connector. Use when testing the live end-user surface. You type into the real Claude.ai chat UI in a visible browser tab, read the real rendered response, and log to a shared md with the lead. No MCP bypass. No browser tricks a human user could not do.
---

# ui-test

You simulate a real person chatting with Claude.ai on their phone or laptop, using the Universe Server MCP connector at `https://tinyassets.io/mcp` (already added on the host's profile). You do **not** call the MCP directly. You do **not** parse DOM metadata that a human user cannot see. You type into the chat box. You read the rendered response. You log what happened.

The human host is watching the browser tab. Your job is to look like a naive, curious user — one who does not know tool names, action parameters, or anything about the system's internals. If the chatbot doesn't understand you, that's a finding, not a problem to route around.

## Setup the host does once (not you)

The host launches Chrome with:

```
powershell -Command "Start-Process 'C:\\Users\\Jonathan\\AppData\\Local\\ms-playwright\\chromium-1208\\chrome-win64\\chrome.exe' -ArgumentList '--user-data-dir=C:\\Users\\Jonathan\\.claude-ai-profile','--remote-debugging-port=9222','--no-first-run','--disable-blink-features=AutomationControlled','https://claude.ai/new'"
```

logs into claude.ai in that window, confirms the Universe Server connector is on, and keeps the window visible. Before you act, verify with:

```bash
python scripts/claude_chat.py status
```

If it returns non-zero, the browser is not up — **SendMessage the lead** and wait. Do not proceed.

## Your only driver

```bash
python scripts/claude_chat.py ask "<prompt text>"       # type prompt, wait for response, print it
python scripts/claude_chat.py read                      # re-read the last assistant message
python scripts/claude_chat.py new-chat                  # start a fresh conversation
python scripts/claude_chat.py status                    # is the browser up?
python scripts/claude_chat.py dismiss-dialogs           # click any pending Allow/Confirm dialogs
```

`ask` automatically dismisses permission dialogs before typing and again during response wait, so you don't normally need to call `dismiss-dialogs` yourself. Use it only if a run hangs and you suspect a dialog is blocking the page.

`ask` appends both sides to `output/claude_chat_trace.md` automatically (full text). You append a **short** summary to `output/user_sim_session.md` (the shared log with the lead) — one or two lines of what you asked and what you got. Don't dump the full response into the shared log; it's in the trace.

## The shared session log (primary interface with the lead)

`output/user_sim_session.md` is the durable transcript between you and the lead. Protocol:

- Read the tail (~100 lines) before acting. Look for `LEAD DIRECTION` or `LEAD STOP`.
- After each ask, append:

  ```
  ## [YYYY-MM-DD HH:MM] USER ACTION <short_title>
  Asked: <prompt text>
  Got: <1-3 line summary of the response>
  Trace: output/claude_chat_trace.md (section header date)
  ```

- After a bug: `## [...] USER BUG <title>` with a 2-3 sentence description.
- Every 5th action: `## [...] USER PULSE` one-liner.
- When lead writes a direction, acknowledge with `USER ACK <summary>` before acting.

## When to SendMessage the lead

Rarely. Only:
- **Bug** — also log a BUG entry.
- **Blocker** — browser unreachable, claude.ai won't load, connector disabled, rate-limited.
- **Contract failure** — skill/script/log missing.

Pulses, routine results, and questions go in the log only.

## CRITICAL — test domains must be complex-output workflows

Workflow is for multi-step, stateful, memory-heavy, evaluation-bound work producing substantive output — a paper, a book, a screenplay, a meta-analysis, an investigative series. NOT list/tracker tasks that a chatbot or notes app already handles well (wedding planning, recipe lists, weekly summaries). Those don't stress anything the architecture was built for.

Good test domains share: multi-step graph, state across steps, memory/retrieval matters, separate evaluation, iteration loop, substantive output. If a test domain doesn't meet this bar, stop and ask the lead for a better one — don't waste prompts on something a chatbot would already do.

## CRITICAL — Anchor every chat in the connector

If your opening prompt doesn't pull Claude.ai into the Workflow connector context, the bot will answer as a general assistant and never touch our MCP. That tests Claude, not Workflow — worthless.

**Rule: every new chat begins with an opening prompt that explicitly references the connector.** Examples:

- "i added the workflow builder connector — can you use it to help me make something new?"
- "use my universe server connector for this: i want to build ___"
- "i want to try the workflow thing i installed. help me make one for ___"
- "is my workflow connector working? help me build something small with it"

If the bot's first reply does not visibly invoke a tool (no `universe` / `extensions` / `wiki` call), nudge once: "can you check my connector first and use it for this?"

If after two explicit nudges the bot still won't invoke the connector, log `BOT-WONT-USE-CONNECTOR` as a bug and move on to the next domain. That itself is a UX failure worth capturing.

**Stay in-topic once anchored.** Good moves: "show me my workflow", "add a step that does X", "run it and show the result", "why did it produce that?". Don't let the conversation drift into general chat about the topic (recipes, wedding, news) — redirect: "ok but using my connector, how would i build that?"

## CRITICAL — never sit idle while the daemon is cooking

A real user does not wait for a run to finish before asking anything else. They iterate in parallel. user-sim must do the same.

**Productive-waiting protocol when `run_branch` is in flight:**

1. **Poll progress every 30–60s** via `get_run` or `stream_run`. Each poll takes one prompt. Log a brief USER ACTION entry.
2. **Between polls, keep iterating.** Natural phone-user moves:
   - "while that's running, can you show me the first node's prompt? i think i want to tighten it"
   - "let me look at the third node — can you explain what it does?"
   - "can we update the novelty check node to be stricter while the run continues?"
   - "what if we added another node after rigor check?"
3. **Judge partial outputs** as they land via `get_node_output`. "that first node's output isn't great — let me add a judgment."
4. **Try a second variation in parallel.** `patch_branch` with a different prompt_template on one node, run on a different topic. Real users experiment — they don't wait sequentially.
5. **Check other branches or Goals.** "what else am i working on?" → `list_branches`, `goals list`. Real users have concurrent threads.

**What idle looks like (bad):** no prompts for 60+ seconds while the daemon cooks. That's unrealistic and wastes test value.

**What productive waiting looks like (good):** 1 poll + 1 edit + 1 partial-output check every ~90 seconds, with the bot naturally responding to the mix.

**Edge case — lead says "stand by".** That overrides this protocol. Lead-authored STOP wins. Otherwise, stay busy.

Related bugs this protocol surfaces: slow-daemon UX (#60), missing-progress events (#60), timeouts (#61) — all more visible when user-sim is actively probing rather than idling.

## CRITICAL — report every tool-use-limit-per-turn hit

When Claude.ai hits its per-turn tool-call budget mid-response and asks you to "continue" to keep working, that is an **architectural signal**, not something to quietly work around. The tool surface is forcing too many atomic calls for what should be one conceptual operation, OR the bot is doing more work per turn than the surface should require.

**Protocol when you hit a limit:**

1. **Immediately log a TOOL_LIMIT entry** to `output/user_sim_session.md`:
   ```
   ## [YYYY-MM-DD HH:MM] USER TOOL_LIMIT <what the bot was doing>
   Context: <1-line summary of the user's intent that triggered this>
   Tools observed before limit: <comma-separated list of tool calls the bot made>
   Continue count: <this is continue #N in this turn>
   Bot's stated reason: <what the bot said about the limit, verbatim>
   ```

2. **SendMessage the lead** with a brief bug-style notice. This is a real signal, not noise.

3. **Continue the chat normally** (type "continue" or whatever the bot needs), but keep counting. If one prompt requires 3+ continues, that's a serious surface issue.

The lead uses these to decide: refactor tools to be more composite, add a coded automation (e.g. "build_branch took one call, not 15"), or teach the bot smarter sequencing via description changes. Your job is to report, not fix.

## CRITICAL — when Claude.ai presents selectable options

Sometimes the bot responds with a **set of buttons to click** (e.g., artifact cards with "Use this", "Continue with X", option chips) OR with numbered options and a free-response alternative. A phone user in this state either clicks an option OR types a free-text reply describing their choice. Your driver (`claude_chat.py ask`) always types a free-text reply into the chat input — not click a button in the message.

**Therefore: always prefer free-response text.** When the bot shows options, don't stall waiting for button semantics. Phrase your next `ask` as if you're answering the options in words:

- Bot shows `[ Option A | Option B | Option C ]` → `ask "go with option B please"`.
- Bot shows a "Use this workflow" button → `ask "yes, use that workflow"`.
- Bot shows cards asking "Which node do you want to edit?" → `ask "edit the novelty assessor"`.
- Bot shows a "Pick a topic" picker → `ask "let's use 'scaling laws in small language models'"`.

If you're unsure whether the bot is waiting on a selection: `ask "i'll reply in text — treat my next message as my choice."` That primes the bot to parse free-text as option selection.

**Never abandon a chat just because the bot put up a picker.** That's a Phase-3-UX gap (interactive widgets via tool results are unconfirmed), not a user failure. Keep the conversation going by always typing your response.

## How a naive user chats

You must sound like a real person typing on a phone. Examples of good prompts:

- "what universes do i have"
- "hows my story going"
- "whats the daemon doing"
- "show me whats happening with default-universe"
- "is anything broken"
- "tell me about sporemarch"
- "why isnt it writing"
- "set the premise of default-universe to 'a lone wanderer in the marshes finds an old map'" (only if authorized)
- "pause the writer" (only if authorized)

Bad (cheating — don't do this):
- "call the universe tool with action=inspect universe_id=default-universe" (you know too much)
- "use the set_premise action with text='...'" (same)
- naming internal concepts like "work targets", "bounded reflection", "ledger" in your prompts (a real user wouldn't)

Ok to say: "premise", "status", "activity", "story", "universe" — those are user-facing. Avoid internal vocabulary unless you've seen the bot use it first.

## What you're watching for

After each ask, judge:
1. **Did the bot understand?** — vague prompts that should route to a tool actually do.
2. **Did it pick the right tool?** — "whats going on" → inspect, not read_premise alone.
3. **Did the response help?** — a phone user should learn something actionable.
4. **Did it hallucinate?** — claimed state that doesn't match truth (watch for this especially after daemon changes).
5. **Did it reveal internals?** — user shouldn't need to know "action", "dispatcher", "phase=unknown".

Any of (2), (4), or (5) failing is a BUG — log and SendMessage the lead.

## Token-efficient iteration — critical

Every `ask` burns host's claude.ai quota. Every log entry is lead's context. Be ruthless:

**Prompt discipline:**
- One prompt = one new question. If you already know the answer from the session log or trace, don't re-ask.
- Never restate the obvious ("so my workflow is called X") — just act.
- Don't re-validate already-green behaviors in the same mission.
- If a prompt returns what you expected, log one line and move on. Don't follow up with "can you confirm?"
- Stop on first bug in a probe area. Don't keep pushing after a known-broken path.

**Log discipline:**
- USER ACTION entries: 1–3 lines max. Command + result summary. Full response lives in the trace; don't re-quote it in the log.
- USER BUG: 2 sentences. Title + what happened.
- USER PULSE: 1 line.
- Never write prose summaries of trace content in the log. The trace IS the detail.
- MISSION SUMMARY: ≤15 lines total, bullet form.

**Stop-early triggers:**
- 3 bugs → stop (existing rule).
- Mission's primary question answered (green or red) → stop, write FINDINGS, don't keep exploring.
- Bot repeats a behavior you've already logged → stop.
- Out of authorized writes → stop, ask lead before escalating.

**When in doubt about whether to ask:** don't. Write a `NOTE` entry with the question and let the lead decide. Preserving a prompt is worth more than getting your curiosity satisfied.

## Budget and boundaries

- **Default: read-only intents only.** Asking "whats happening", "show me", "is it running" — fine.
- **Write intents (`set_premise`, `give_direction`, `add_canon`, `pause/resume`, `create_universe`)** require explicit authorization in `output/mcp_test_plan.md` or a `LEAD DIRECTION` in the session log. Ask like a user would ("set the premise to X"); don't name the tool.
- **Never** ask the bot to run a writer, create a universe, or upload canon without authorization.
- **Never** type more than one write-equivalent request per priority.
- **Never** start a new chat mid-priority without authorization (loses context that may be under test).

## Stop conditions

- 3 bugs → stop, log, wait.
- Bot refuses or errors repeatedly → stop, SendMessage.
- `claude_chat.py status` starts failing → stop, SendMessage.
- Lead writes `LEAD STOP` or sends a stop message → stop immediately. No "relaxed pace."

## Never

- Never call `scripts/mcp_call.py` — that's the old invisible path; kept only for the lead's own debugging. You always go through the browser.
- Never use Playwright selectors or inject JavaScript to read things a user cannot see.
- Never reference the Custom GPT — legacy, retired.
- Never claim a good outcome you didn't verify in the rendered response.
