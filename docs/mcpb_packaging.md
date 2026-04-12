# MCPB Packaging

The official MCPB packaging path now lives under `packaging/mcpb/`.

## What is checked in

- `packaging/mcpb/manifest.json`: spec-aligned MCPB manifest template
- `packaging/mcpb/pyproject.toml`: minimal runtime config for the bundle
- `packaging/mcpb/server.py`: stdio entrypoint used inside the bundle
- `packaging/mcpb/build_bundle.py`: stages the bundle source, validates it,
  and optionally packs `workflow-universe-server.mcpb`

## Why the build script stages files

The repository source of truth for the packaged server remains
`fantasy_author/universe_server.py`. The MCPB bundle, however, should ship a
small runtime surface with only the files and dependencies it actually needs.

`build_bundle.py` copies the current Universe Server implementation plus the
bundle template files into `packaging/dist/workflow-universe-server-src/`,
then validates and packs that staged directory with the official
`@anthropic-ai/mcpb` CLI.

## Commands

Validate the staged bundle:

```powershell
python packaging/mcpb/build_bundle.py --validate
```

Validate and pack:

```powershell
python packaging/mcpb/build_bundle.py --pack
```

## Runtime shape

The packaged bundle runs as a local stdio MCP server. During installation,
the host client prompts for:

- `Universe Base Directory`: required directory containing universe folders
- `Default Universe`: optional universe ID used when the client does not pass one

The bundle then launches `packaging/mcpb/server.py`, which loads the staged
copy of `fantasy_author/universe_server.py` and starts it with
`transport="stdio"`.

Note: the official `@anthropic-ai/mcpb` validator currently rejects
`server.type = "uv"` even though the public manifest docs mention it. The
manifest therefore uses `server.type = "python"` while `mcp_config.command`
still launches the bundle with `uv run`.
