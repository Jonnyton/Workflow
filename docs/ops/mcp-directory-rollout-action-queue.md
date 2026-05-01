# MCP Directory Rollout Action Queue

Date: 2026-05-01
Status: active queue after `/mcp-directory` live proof
Owner: lead + available providers

This queue starts after the implementation slice shipped. The live state is:

- Full custom-connector endpoint: `https://tinyassets.io/mcp`
- Directory/review endpoint: `https://tinyassets.io/mcp-directory`
- Public canary: green for both endpoints on 2026-05-01
- Directory tool-list: 11 narrow tools from `/mcp-directory`

The rollout is not complete until Workflow is accepted into host-native
directories or registries, normal eligible users can find/add it without
Developer Mode or custom URL friction, and first-use evidence is recorded.

## Completion Definition

Done means all of these are true:

- MCP Registry lists Workflow and points clients at `https://tinyassets.io/mcp-directory`.
- Claude lists Workflow in the Connectors Directory, not only as a custom MCP URL.
- ChatGPT lists Workflow in the App Directory for eligible logged-in users, not
  only in Developer Mode.
- The public site tells each customer which path fits them: directory listing,
  custom URL fallback, no-chatbot-login local/self-hosted path, or planned host.
- The proof registry has a normal-user trace for each listed host.

## Host/Admin Actions

These require account, workspace, or directory submission authority. Do not mark
them complete from code-only evidence.

### MCP Registry Publish

Artifact: `packaging/registry/server.json`

Steps:

1. Install the official `mcp-publisher` CLI in an environment controlled by the
   repository/namespace owner.
2. Run `mcp-publisher login github`.
3. Run `mcp-publisher publish packaging/registry/server.json`.
4. Verify Workflow appears through the public registry/search path.
5. Update `docs/ops/mcp-host-proof-registry.md` with registry URL, date, and
   verification command/output.

Blocker from 2026-05-01: `mcp-publisher --help` was not available in the Codex
Windows PATH.

### Claude Connectors Directory Submission

Artifact: `docs/ops/mcp-directory-submission-packet.md`

Submit:

- Name: Workflow
- Endpoint: `https://tinyassets.io/mcp-directory`
- Website: `https://tinyassets.io/connect`
- Support: `ops@tinyassets.io`
- Security: `security@tinyassets.io`

Acceptance proof:

- Workflow appears in the Claude Connectors Directory.
- A normal logged-in Claude user adds Workflow without pasting a custom URL.
- Claude invokes `get_workflow_status` or `list_workflow_goals`.
- Trace goes to `output/claude_chat_trace.md` and summary to
  `output/user_sim_session.md`.

### ChatGPT App Directory Submission

Artifact: `chatgpt-app-submission.json`

Submit through an OpenAI workspace that has app write/read permissions and org
verification complete.

Known blockers:

- BUG-034 tracks the current ChatGPT connector approval/post-approval stall.
- If the App Directory dashboard requires an embedded app resource, a widget/CSP
  slice must land before pressing Submit.
- Screenshots and privacy/safety fields must be captured from the verified live
  deployment.

Acceptance proof:

- Workflow appears in the ChatGPT App Directory for eligible logged-in users.
- A normal eligible user invokes Workflow without Developer Mode.
- At least one read-only tool call succeeds and is logged in the proof registry.

## Website Editor Handoff

Do not edit these files from this queue while the website row is claimed. Hand
this section to the website-editing session that already owns `WebSite/site/*`.

Observed on the live site/source, 2026-05-01:

- `/` and `/connect` still lead with the custom URL path: `tinyassets.io/mcp`.
- `/connect` mentions Claude and ChatGPT as gates, but it does not yet make the
  new `/mcp-directory` route visible as the review/listing endpoint.
- `llms.txt` correctly warns that ChatGPT guest users cannot connect apps/MCP,
  but it still names only the full custom connector as the canonical MCP server.

Website task:

1. Add a customer path chooser to `/connect`:
   - "Find Workflow in your app/connector directory" once a host is accepted.
   - "Use custom connector URL today" with `https://tinyassets.io/mcp`.
   - "No hosted chatbot login" with Open WebUI/LibreChat/LM Studio/Jan/OpenClaw
     status, marked verified only after proof.
   - "Developer/IDE" with MCP Registry/config snippets.
2. Add an honest status band:
   - `mcp` full custom connector: live.
   - `mcp-directory` directory/review endpoint: live, pending host acceptance.
   - Claude directory: submission pending.
   - ChatGPT App Directory: submission pending.
3. Update AI-readable docs:
   - Keep `https://tinyassets.io/mcp` as full custom connector.
   - Add `https://tinyassets.io/mcp-directory` as the reviewed directory endpoint.
   - Keep the ChatGPT guest/no-app caveat.
   - Avoid claiming any host directory acceptance until proof lands.
4. After edits, run the website skill's full check/build/browser-preview loop
   and attach screenshots to the proof registry.

Acceptance criteria:

- A non-technical user can tell whether they should use an app directory, paste
  a URL, use a local/no-login host, or wait.
- No page says Workflow is in a host directory before acceptance.
- Mobile `/connect` shows the chooser without horizontal overflow.

## Dev Verification Queue

These can be picked up by any non-website dev with a narrow worktree.

### No-Chatbot-Login Pack

First target: Open WebUI.

Setup pack: `docs/ops/open-webui-no-login-pack.md`.

Deliverables:

- Host version and transport notes.
- Minimal config for `https://tinyassets.io/mcp-directory`.
- Tool-list proof and one visible read-only user result.
- Proof registry row.

Then repeat for LibreChat, LM Studio/Jan, OpenClaw/channel gateway, and any
custom host that claims MCP support. If a host needs a bridge, document the
bridge truthfully instead of saying it works natively.

### IDE/Developer Pack

Targets:

- VS Code / Copilot MCP config
- Cursor MCP config/add-button path
- Gemini CLI config
- Cline/Roo/Continue/Windsurf where practical

Acceptance proof per host:

- Config snippet committed or documented.
- Tool list succeeds.
- One safe read-only tool call succeeds.
- Proof registry updated with date, version, and command/UI trace.

### Partner Packet

Create a compact package for host/platform maintainers:

- One-paragraph category: "live collaborative workflow/node daemon for AI agents"
- Endpoint and transport matrix
- Tool surface summary
- Privacy/safety/support links
- Uptime/proof registry links
- Negative invocation cases

This should reuse `docs/ops/mcp-directory-submission-packet.md` rather than
forking a second source of truth.

## Status Update Rules

When a host moves forward:

1. Update `docs/ops/mcp-host-proof-registry.md`.
2. Update `docs/ops/mcp-directory-submission-packet.md` if reviewer-facing facts
   changed.
3. Update `STATUS.md` only if there is still an active blocker or next action.
4. Do not mark completion until normal-user discovery and first-use proof exist.
