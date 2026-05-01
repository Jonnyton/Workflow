# MCP Host Proof Registry

Date: 2026-05-01
Owner: lead + codex-gpt5-desktop
Canonical MCP URL: `https://tinyassets.io/mcp`

This registry is the source for public claims about where Workflow works. If a
host is not listed as verified here, public copy should say "compatible by
spec" or "planned", not "works".

## Verification Rules

- Public endpoint proof starts with `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp`.
- Hosted chatbot proof must use the real chatbot UI with the Workflow connector
  enabled, then log the trace in `output/claude_chat_trace.md` or the matching
  host trace file.
- Developer/IDE proof must include a host-specific config plus a tool-list or
  safe tool-call smoke.
- Local/self-hosted proof must include the host version, transport, config, and
  visible user result.
- Claims expire when host docs change, the endpoint flakes, or a connector/app
  submission is rejected.

## Current Gate State

| Gate | Status | Evidence | Notes |
|---|---|---|---|
| Public MCP endpoint | watch/flapping | Latest 2026-05-01 diagnostic: 5/5 local canaries green and GitHub Actions uptime run `25231089323` green after intermittent HTTP 502s | Keep monitoring before public app/directory launch claims |
| Official MCP Registry metadata | ready-draft | `packaging/registry/server.json` validates against schema and points at `https://tinyassets.io/mcp` | Needs `mcp-publisher login github` + publish by repo owner/admin |
| AI-readable web docs | ready-draft | `WebSite/site/static/llms.txt` | Ships with site deploy |
| `/connect` customer chooser | ready-draft | `npm run check`, `npm run build`, Playwright desktop/mobile smoke on 2026-05-01 | Ships with site deploy |

## 2026-05-01 Local Verification

- `python packaging/registry/generate_server_json.py --check --validate` passed.
- Public MCP diagnostics after one local HTTP 502: 5 consecutive
  `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --timeout 15 --verbose`
  probes passed; GitHub Actions uptime run `25231089323` passed; direct
  `https://mcp.tinyassets.io/mcp` stayed Access-gated at HTTP 403 as expected.
- `npm run check` in `WebSite/site` passed with 0 errors and 0 warnings.
- `npm run build` in `WebSite/site` passed and emitted `build/connect.html`
  plus `build/llms.txt`.
- Playwright production-preview smoke passed on desktop 1440x1100 and mobile
  390x900: 0 console/page errors, no horizontal overflow, 6 customer path
  cards, 3 gate rows, canonical URL value present, mobile host table stacks to
  one column, `/llms.txt` includes Workflow and ChatGPT guest caveats.
- Screenshots: `output/connect-desktop-2026-05-01.png`,
  `output/connect-mobile-2026-05-01.png`.

## Host Matrix

| Host surface | Customer path | Status | Proof / blocker |
|---|---|---|---|
| Claude.ai custom connector | Logged-in Claude user | verified-historical; refresh needed | Real Claude.ai proof exists in site capture; refresh after copy/metadata lands |
| Claude Connectors Directory | Logged-in Claude users/admins | submission-needed | Prepare metadata, privacy/safety copy, icon/favicon, examples, support path |
| ChatGPT custom MCP / developer mode | Logged-in eligible ChatGPT user/workspace | blocked | BUG-034/admin approval path blocks clean custom connector approval |
| ChatGPT App Directory | Logged-in ChatGPT users/admins | submission-needed | Needs Apps SDK manifest/widget/test cases and OpenAI app submission |
| ChatGPT guest | No logged-in chatbot account | unsupported by ChatGPT path | Route to local/self-hosted/no-chatbot-login options |
| Mistral Le Chat MCP connector | Logged-in Mistral user/admin | planned | Need connector config proof and directory/submission research |
| Open WebUI | No hosted chatbot login if self-hosted | planned | Verify Streamable HTTP MCP config against `https://tinyassets.io/mcp` |
| LibreChat | No hosted chatbot login if self-hosted | planned | Verify MCP config or bridge path |
| LM Studio / Jan | Local model user | planned | Verify native MCP support or document bridge/fallback truthfully |
| OpenClaw / channel gateway | Channel user | planned | Need direct support proof before claiming |
| VS Code / GitHub Copilot | Developer/IDE user | planned | Verify `.vscode/mcp.json` or user MCP config with Copilot Chat |
| Cursor | Developer/IDE user | planned | Verify Cursor MCP config/add button path |
| Gemini CLI | Developer/CLI user | planned | Verify `settings.json`/command path and a safe tool call |
| Microsoft Copilot Studio | Enterprise maker/admin | planned | Build custom MCP connector/Power Platform package or OpenAPI fallback |
| Custom MCP host | Builder | compatible-by-spec | Provide minimal integration contract and smoke command |

## First Prompts To Verify

Use host-specific wording, but each host should prove at least one of these:

- "Use Workflow to list available goals."
- "Use Workflow to browse the live wiki and summarize the current launch risks."
- "Use Workflow to inspect universes and tell me what durable state exists."
- "Use Workflow to create or propose a node for a simple workflow." Only use
  this once write permissions and approval UX are verified in that host.

## Open Follow-Ups

- Publish `packaging/registry/server.json` to the official MCP Registry after
  the public endpoint stays green long enough for launch confidence.
- Prepare Claude directory submission kit.
- Prepare ChatGPT Apps SDK submission kit and resolve BUG-034 approval path.
- Verify one no-chatbot-login host first, preferably Open WebUI because it
  supports Streamable HTTP MCP directly.
- Add host-specific proof traces as they land.
