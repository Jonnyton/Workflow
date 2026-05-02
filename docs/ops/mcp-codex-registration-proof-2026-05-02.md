# Codex CLI MCP Registration Proof

Date: 2026-05-02
Host: Codex CLI 0.104.0 on Windows x64
Endpoint: `https://tinyassets.io/mcp-directory`
Status: registration path verified; Codex tool-list/read-call proof still pending

## What This Proves

Codex CLI accepts Workflow as a Streamable HTTP MCP server and writes the
expected isolated configuration without mutating the user's real
`~/.codex/config.toml`.

```toml
[mcp_servers.workflow]
url = "https://tinyassets.io/mcp-directory"
```

This is not yet a full Codex support claim. A full support claim still needs a
Codex runtime/tool session to list Workflow tools and complete one safe
read-only call.

## Commands

```powershell
codex --version
```

Output:

```text
codex-cli 0.104.0
```

Isolated registration command:

```powershell
$temp = Join-Path $env:TEMP 'workflow-codex-mcp-proof'
New-Item -ItemType Directory -Force -Path $temp | Out-Null
$env:CODEX_HOME = $temp
codex mcp add workflow --url https://tinyassets.io/mcp-directory
```

Observed result:

```text
Added global MCP server 'workflow'.
```

List readback:

```powershell
$env:CODEX_HOME = "$env:TEMP\workflow-codex-mcp-proof"
codex mcp list --json
```

Output:

```json
[
  {
    "name": "workflow",
    "enabled": true,
    "disabled_reason": null,
    "transport": {
      "type": "streamable_http",
      "url": "https://tinyassets.io/mcp-directory",
      "bearer_token_env_var": null,
      "http_headers": null,
      "env_http_headers": null
    },
    "startup_timeout_sec": null,
    "tool_timeout_sec": null,
    "auth_status": "unsupported"
  }
]
```

Server readback:

```powershell
$env:CODEX_HOME = "$env:TEMP\workflow-codex-mcp-proof"
codex mcp get workflow --json
```

Output:

```json
{
  "name": "workflow",
  "enabled": true,
  "disabled_reason": null,
  "transport": {
    "type": "streamable_http",
    "url": "https://tinyassets.io/mcp-directory",
    "bearer_token_env_var": null,
    "http_headers": null,
    "env_http_headers": null
  },
  "enabled_tools": null,
  "disabled_tools": null,
  "startup_timeout_sec": null,
  "tool_timeout_sec": null
}
```

## Remaining Proof

Before public copy says Codex is verified, run a Codex session with this MCP
server enabled and record:

- Workflow appears in the Codex MCP tool surface.
- Codex lists Workflow tools from `https://tinyassets.io/mcp-directory`.
- Codex completes one safe read-only call, preferably `get_workflow_status`.
- The trace includes the Codex version, isolated config, transport, and visible
  result.
