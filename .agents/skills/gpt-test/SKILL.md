---
name: gpt-test
description: Test the Custom GPT through the real ChatGPT web UI. User watches in real-time.
user_invocable: true
---

Test the Custom GPT through the real ChatGPT web UI.

GPT URL: https://chatgpt.com/g/g-69cd9dc9c52c8191a18dd84829712447-fantasy-author

## Browser — pick your method

**The user must be able to see the browser.** This is a live review activity.

### Method A: gpt_builder CLI (Codex, Codex — preferred)

Launch once per session (user's visible Chrome on port 9222):
```
powershell -Command "Start-Process 'C:\Users\Jonathan\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe' -ArgumentList '--user-data-dir=C:\Users\Jonathan\.gpt-test-profile', '--remote-debugging-port=9222', '--no-first-run', '--disable-blink-features=AutomationControlled', 'https://chatgpt.com/g/g-69cd9dc9c52c8191a18dd84829712447-fantasy-author'"
```

```bash
python -m fantasy_author.testing.gpt_builder new-chat           # fresh session
python -m fantasy_author.testing.gpt_builder ask "question"     # send + wait + log
python -m fantasy_author.testing.gpt_builder next               # send last "> NEXT:" from log
python -m fantasy_author.testing.gpt_builder read               # read latest response
python -m fantasy_author.testing.gpt_builder click-dialogs      # click Allow/Confirm
```

`ask` returns ~10 tokens. Full response goes to `output/gpt_test_log.md`.

### Method B: Chrome MCP (Cowork — fallback)

**Visibility:** The MCP tab group opens in a separate Chrome window. It IS visible but may be behind other windows. Tell the user to keep the Chrome window in view (Alt+Tab or taskbar). After navigating, the window usually surfaces — if not, the user needs to manually bring it forward. Chrome MCP cannot force-focus the window on Windows.

```
tabs_context_mcp (createIfEmpty: true)
navigate to GPT URL
```

Send messages:
```
find "message input textarea" → left_click → type "question" → key Return
wait 8-10 seconds → screenshot
```

Action confirmations: click "Always Allow" on the first one.

### How to choose

- Can you run `python -m fantasy_author.testing.gpt_builder`? → Method A
- No Python / no localhost access? → Method B (warn user about visibility)

## Test cases

Run in order. Adapt to host online/offline.

### Host offline
1. "What's the status of my story?" → `getHealth` → "Your host is offline."
2. "What's the weather?" → No action. Redirect: "I'm your fiction writing tool…"
3. "The currency is bone-marks" → Attempt action → host offline (can't verify addCanon without live host)
4. "Make the next scene a flashback" → Attempt action → host offline

### Host online (requires API + tunnel)
5. "What's the status of my story?" → `getOverview` → summarize from returned data
6. "The currency is bone-marks" → `addCanon` (world fact, NOT addNote)
7. "Make the next scene a flashback" → `addNote` (direction, NOT addCanon)
8. "What is the writer working on?" → `getWorkTargets` and/or `getReviewState`
9. "Start the writer" → `controlWriter` action=start. No "should I start?" question.
10. Any creative request → route to actions, never write prose itself
11. Upload a text file → `uploadCanonFiles`, not summarize content

## What to check

Per test:
- **Action called?** Every story request = at least one action call.
- **Correct action?** Expand "Stopped/Talked to App" to verify operationId.
- **No prose?** GPT must never write story content itself.
- **No web search?** If it searches, Web Search is enabled — fix in editor.
- **One response?** No multi-message thinking-aloud.
- **In character?** Off-topic → redirect.

## Logging

After testing, update `output/gpt_test_log.md`:

```markdown
## YYYY-MM-DD HH:MM — Test Run

Host: online | offline
Schema version: X.Y.Z (N operations)
Instructions size: N chars

| # | Test | Action Called | Result | Notes |
|---|------|-------------|--------|-------|
| 1 | Status check | getHealth | PASS | "Your host is offline." |
```

## Rules

- **ONE browser instance.** Never open a second.
- **New chat after changes.** Tunnel restart, instruction update, schema update = fresh chat.
- **Report bugs immediately.** Describe the issue + what instruction/schema change would fix it.
- **NEVER write Playwright/CDP code.** Use the CLI or Chrome MCP tools.
- **NEVER message lead about passing tests.** Log has the details.
