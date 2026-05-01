# Open WebUI No-Chatbot-Login Pack

Date: 2026-05-01
Status: setup-ready; runtime proof pending
Owner: lead + available provider

This pack is the first no-hosted-chatbot-login path for Workflow. It is for
users who do not want or cannot use Claude/ChatGPT app directories, but can run
or access an Open WebUI instance.

## Current Truth

- Open WebUI docs say native MCP support starts in Open WebUI `v0.6.31+`.
- Native MCP support is `MCP (Streamable HTTP)` only.
- Workflow exposes a public Streamable HTTP MCP endpoint at
  `https://tinyassets.io/mcp-directory`.
- The full custom-connector endpoint remains `https://tinyassets.io/mcp`, but
  the directory endpoint is the safer first proof surface because it exposes
  only 11 narrow tools.

Do not claim "Open WebUI works with Workflow" publicly until the runtime proof
section below is completed and copied into `docs/ops/mcp-host-proof-registry.md`.

## Recommended Open WebUI Settings

In Open WebUI:

1. Open `Admin Settings -> External Tools`.
2. Add a server.
3. Set `Type` to `MCP (Streamable HTTP)`.
4. Set `Server URL` to:

```text
https://tinyassets.io/mcp-directory
```

5. Set authentication to `None`.
6. Leave the function-name filter empty for the first connection proof.
7. Save. Restart Open WebUI if prompted.

Optional hardening after first proof:

```text
get_workflow_status,list_workflow_goals,search_workflow_wiki,read_workflow_wiki_page,list_workflow_runs
```

Use the optional filter only after proving the unfiltered directory endpoint
connects, because the filter itself can become the source of setup failures.

## User-Facing First Prompts

Use read-only prompts first:

```text
Use Workflow to check the daemon status and tell me any caveats.
```

```text
Use Workflow to list available goals.
```

```text
Use Workflow to search the Workflow wiki for launch risks and summarize the best match.
```

Only test write/propose flows after read-only invocation is visible in the chat
and Open WebUI's approval/tool-call UX is understood.

## Troubleshooting Notes

- If the connection fails, verify the tool type is `MCP (Streamable HTTP)`, not
  OpenAPI.
- If auth is set to `Bearer` without a key, Open WebUI may send an empty
  authorization header. Use `None` for Workflow's current public directory
  endpoint.
- If Open WebUI runs in Docker and the MCP server is on the host machine, Open
  WebUI docs recommend `host.docker.internal`. That is not needed for
  `https://tinyassets.io/mcp-directory` because it is a public HTTPS endpoint.
- Open WebUI recommends setting `WEBUI_SECRET_KEY` for stable OAuth-connected
  tools. Workflow's directory endpoint does not require OAuth today, but a
  stable key is still a good Open WebUI deployment practice.

## Runtime Proof Checklist

Record all values before claiming support:

| Field | Value |
|---|---|
| Open WebUI version | TBD |
| Deployment shape | local Docker / hosted / other |
| Workflow endpoint | `https://tinyassets.io/mcp-directory` |
| Auth mode | None |
| Function filter | empty for first proof |
| Model used | TBD |
| Prompt | TBD |
| Visible tool result | TBD |
| Screenshot/trace path | TBD |
| Date/time | TBD |

Acceptance criteria:

- Open WebUI adds the Workflow MCP server without crashing or infinite loading.
- A chat can invoke at least one read-only Workflow tool.
- The visible response matches the tool result enough for a user to trust it.
- Any console/server error is recorded.
- `docs/ops/mcp-host-proof-registry.md` is updated from `setup-ready` to
  `verified` with the proof date and trace path.

## Supporting Protocol Checks

Run these before and after the Open WebUI proof:

```powershell
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp-directory --timeout 15 --verbose
python scripts/mcp_probe.py --url https://tinyassets.io/mcp-directory tools
```

Expected directory tools:

- `get_workflow_status`
- `list_workflow_universes`
- `inspect_workflow_universe`
- `list_workflow_goals`
- `search_workflow_goals`
- `get_workflow_goal`
- `search_workflow_wiki`
- `read_workflow_wiki_page`
- `list_workflow_runs`
- `propose_workflow_goal`
- `submit_workflow_request`

## Source Notes

Fresh docs checked on 2026-05-01:

- Open WebUI MCP docs: `https://docs.openwebui.com/features/mcp/`
- Workflow proof registry: `docs/ops/mcp-host-proof-registry.md`
- Workflow directory queue: `docs/ops/mcp-directory-rollout-action-queue.md`
