# MCP Host Proof Registry

Date: 2026-05-01
Owner: lead + codex-gpt5-desktop
Canonical full MCP URL: `https://tinyassets.io/mcp`
Directory/review MCP URL: `https://tinyassets.io/mcp-directory`

This registry is the source for public claims about where Workflow works. If a
host is not listed as verified here, public copy should say "compatible by
spec" or "planned", not "works".

## Verification Rules

- Public endpoint proof starts with `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp`.
- Directory endpoint proof also requires `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp-directory`.
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
| Public MCP endpoint | live-green | 2026-05-01: prod deploy `25233226847` green; Worker deploy `25233386849` green; `mcp_public_canary.py --url https://tinyassets.io/mcp` OK | Legacy custom connector surface remains available |
| Directory-safe MCP endpoint | live-green | 2026-05-01: `mcp_public_canary.py --url https://tinyassets.io/mcp-directory` OK; `mcp_probe.py --url https://tinyassets.io/mcp-directory tools` returned 11 narrow tools | Use this endpoint for host-directory review |
| Official MCP Registry metadata | artifact-ready; publish-blocked | `packaging/registry/server.json` points at `https://tinyassets.io/mcp-directory` | Local PATH lacks `mcp-publisher`; needs CLI install, `mcp-publisher login github`, and publish by repo owner/admin |
| AI-readable web docs | live | `WebSite/site/static/llms.txt` live from PR #122 | Needs periodic source freshness check |
| `/connect` customer chooser | live | PR #122 deployed; Playwright desktop/mobile smoke on 2026-05-01 | Copy is truthful but directory acceptance is still pending |

## 2026-05-01 Local Verification

- `python packaging/registry/generate_server_json.py --check --validate` passed.
- `python -m pytest tests/test_directory_server.py tests/test_universe_server_directory_app.py tests/smoke/test_mcp_tools_list_non_empty.py tests/test_universe_server_metadata.py` passed.
- `node --test worker.test.js` passed in `deploy/cloudflare-worker`.
- `python packaging/claude-plugin/build_plugin.py` passed with import probe, including the new directory server module in the plugin runtime mirror.
- Local Streamable HTTP runtime smoke passed: `scripts/mcp_public_canary.py`
  initialized both `http://127.0.0.1:8017/mcp` and
  `http://127.0.0.1:8017/mcp-directory`; `scripts/mcp_probe.py` listed the
  11 directory tools from `/mcp-directory`.
- `mcp-publisher --help` failed because the CLI is not installed in the
  current Windows PATH; registry publish remains blocked on CLI install and
  GitHub device authentication.
- Public MCP diagnostics after one local HTTP 502: 5 consecutive
  `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --timeout 15 --verbose`
  probes passed; GitHub Actions uptime run `25231089323` passed; direct
  `https://mcp.tinyassets.io/mcp` stayed Access-gated at HTTP 403 as expected.
- Production rollout proof after PR #123/#124/#125:
  - Deploy prod run `25233226847` passed for merge `d6a44eb`.
  - Manual Worker deploy run `25233386849` passed for main `e8e0fd0`.
  - `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --timeout 15 --verbose` returned OK.
  - `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp-directory --timeout 15 --verbose` returned OK.
  - `python scripts/mcp_probe.py --url https://tinyassets.io/mcp-directory tools` returned exactly the 11 directory tools.
  - `python scripts/mcp_probe.py --url https://tinyassets.io/mcp tools` still returned the 7 legacy custom-connector tools.
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
| Claude.ai custom connector | Logged-in Claude user | protocol-live; UI refresh needed | Full surface is `https://tinyassets.io/mcp`; protocol proof green 2026-05-01; live Claude.ai proof still needs refresh |
| Claude Connectors Directory | Logged-in Claude users/admins | packet-ready; submission-needed | Use `https://tinyassets.io/mcp-directory` and `docs/ops/mcp-directory-submission-packet.md` |
| ChatGPT custom MCP / developer mode | Logged-in eligible ChatGPT user/workspace | blocked | BUG-034/admin approval path blocks clean custom connector approval |
| ChatGPT App Directory | Logged-in ChatGPT users/admins | packet-ready; submission-needed | `chatgpt-app-submission.json` covers the 11 directory tools; actual submission requires OpenAI workspace/admin flow |
| ChatGPT guest | No logged-in chatbot account | unsupported by ChatGPT path | Route to local/self-hosted/no-chatbot-login options |
| Mistral Le Chat MCP connector | Logged-in Mistral user/admin | planned | Need connector config proof and directory/submission research |
| Open WebUI | No hosted chatbot login if self-hosted | planned | Verify Streamable HTTP MCP config against `https://tinyassets.io/mcp` or directory-safe `https://tinyassets.io/mcp-directory` |
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
  the public directory endpoint is deployed and green.
- Submit the Claude directory packet through Anthropic's review flow.
- Submit `chatgpt-app-submission.json` through OpenAI's app submission flow and resolve BUG-034 approval path for custom connectors.
- Verify one no-chatbot-login host first, preferably Open WebUI because it
  supports Streamable HTTP MCP directly.
- Add host-specific proof traces as they land.
