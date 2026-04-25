---
title: Acceptance Probe Catalog
date: 2026-04-20
author: navigator
status: living doc — add validated probes here; remove if they go stale
---

# Acceptance Probe Catalog

Named, validated probes for testing the full System → Chatbot → User chain.
Each entry records the exact prompt, what it exercises, and the evidence of
its validation. Use these as reference probes for cutover acceptance, regression
checks, and new-connector verification.

---

## PROBE-001 — Full-stack smoke (cutover acceptance)

**Validated:** 2026-04-20 (DO-cutover acceptance mission)
**Source audit:** `docs/audits/user-chat-intelligence/2026-04-20-do-cutover-acceptance.md`
**Persona:** bare-curious-user (no persona framing; minimal context)
**Connector URL under test:** `https://tinyassets.io/mcp`

### Prompt (paste verbatim)

```
hey i want to use the tool i set up to design a workflow for writing a research
paper on deep space population — can you walk me through it?
```

### What it exercises

| Layer | What's tested |
|---|---|
| System | MCP endpoint reachable via Claude.ai → Cloudflare Worker → tunnel → daemon |
| Chatbot | `control_station` Hard Rule 10 (anti-fabrication): assume → tool-call → correct-if-wrong |
| Chatbot | Chatbot-assumes-Workflow directive (rule 7): no disambiguation picker |
| Chatbot | User-vocabulary discipline (rule 9): no engine-vocab in first response |
| User | Full pipeline recommendation grounded in real tool output, not fabrication |

### Green criteria

- Chatbot invokes at least one Workflow MCP tool (visible in thinking-block or response).
- Response references real daemon state (e.g., empty workspace, named primitives from actual tool output).
- No fabricated workflow JSON, no fabricated prior-session history.
- Settle time under 150s. (>150s with tool invocation = soft-yellow; >150s without tool invocation = suspected fabrication-mode.)
- Zero "Session terminated" errors.

### Red signals

- "Session terminated" on any tool call.
- Chatbot produces a workflow spec without invoking a tool.
- Chatbot claims prior-session context that was never established in this chat.
- No tool call at all (chatbot responded from memory only).
- Settle time >180s with no tool call confirmed.

### Baseline evidence

| Date | Condition | Settle (ms) | Result |
|---|---|---|---|
| 2026-04-19 | P0 outage (pre-fix) | >180,000 | RED — 3x Session terminated, 6-node JSON fabricated, hallucinated history |
| 2026-04-20 | Post-cutover | 116,000 | GREEN — live tool cycle, empty-workspace reported correctly, Hard Rule 10 held |

### When to use

- After any change to the Cloudflare Worker, tunnel config, or daemon deploy.
- After any `control_station` prompt edit.
- As the final acceptance gate before marking a cutover "done."
- As a regression check if Layer-1 canary is green but user-reports suggest broken behavior.

### Limitations

- Exercises the full path but not deeply (1 prompt, 1 tool call). For deep
  persona-specific validation, use the per-persona mission drafts.
- "Deep space population" topic is now known to the system; a future probe
  rotation may want a different topic to avoid any cached warm-path effects.
- **Single-URL architecture (2026-04-20):** this probe targets `tinyassets.io/mcp` only.
  The former dual-URL localization trick (green canonical + red `mcp.` = Worker OK, tunnel broken)
  is retired. Layer diagnosis now uses Cloudflare Worker logs + cloudflared tunnel logs
  (see `docs/ops/dns-tunnel-single-entry-cutover.md` § Observability).

---

## PROBE-002 — Layer-2 liveness (minimal)

**Validated:** design-validated (not yet live-run as automated probe)
**Source doc:** `docs/design-notes/2026-04-19-layer2-canary-scope.md §2.2`
**Persona:** `uptime_canary` (dedicated automated persona)
**Connector URL under test:** `https://tinyassets.io/mcp`

### Prompt (paste verbatim)

```
Are you there? Call get_status and tell me the llm_endpoint_bound value.
```

### What it exercises

- MCP connector reachable from Claude.ai.
- `get_status` tool invocable (lowest-dep read-only tool).
- `evidence.llm_endpoint_bound` field readable and surfaced in response.

### Green criteria

- Chatbot invokes `get_status`.
- Response contains a reference to `llm_endpoint_bound` OR `endpoint` OR `bound` (case-insensitive).
- Settle time within normal range.

### Red signals

- No tool call (exit 10 — `tool_not_invoked`).
- Tool called but response empty (exit 11).
- Tool called but field not referenced in response (exit 12).
- Browser could not reach Claude.ai (exit 13).

### When to use

- Automated hourly Layer-2 canary (Windows Task Scheduler entry `Workflow-Canary-L2` invokes `scripts/uptime_canary_layer2.py`).
- Quick manual liveness check when Layer-1 is green but something feels wrong.

---

## PROBE-003 — Wiki write-roundtrip (auto-heal pipeline integrity)

**Validated:** wiki canary script live since 2026-04-22; logs roundtripped probes to `.agents/uptime.log`.
**Source script:** `scripts/wiki_canary.py`
**Persona:** `wiki-canary` (automated; client name `wiki-canary/1.0`)
**Connector URL under test:** `https://tinyassets.io/mcp`

### Invocation

```
python scripts/wiki_canary.py
python scripts/wiki_canary.py --url http://127.0.0.1:8001/mcp --verbose
python scripts/wiki_canary.py --once --format=gha
```

### What it exercises

| Layer | What's tested |
|---|---|
| System | MCP `initialize` handshake reaches the daemon. |
| System | `wiki action=write` persists a known body to `drafts/canary/uptime-probe.md`. |
| System | `wiki action=read` returns that body verbatim. |
| User-impact | Auto-heal pipeline integrity — chatbots filing bugs depend on wiki writes succeeding. |

### Green criteria

- Exit code 0.
- `wiki action=write` succeeds without `isError`.
- `wiki action=read` returns body matching `_CANARY_BODY` byte-for-byte.

### Red signals

- Exit 2 — MCP handshake failed (initialize or session establishment).
- Exit 6 — wiki write failed (`isError=true` or network error).
- Exit 7 — wiki read failed or roundtrip content mismatched.
- Exit 99 — unexpected error.

### Why this probe earns a catalog slot

BUG-028 demonstrated that a slug-normalization bug could silently break bug filing while the Layer-1 MCP handshake stayed green. PROBE-001 (full-stack smoke) and PROBE-002 (handshake liveness) would not catch this class of regression. Wiki-write failure is P0 per the Forever Rule (24/7 uptime, auto-heal pipeline).

### When to use

- After any change to wiki write/read tool handlers, slug normalization, or wiki storage backend.
- After any deploy that touches `_wiki_file_bug` or related tools.
- As a continuous P0 canary alongside PROBE-002.

---

## PROBE-004 — MCP tool-invocation end-to-end (handshake-vs-handler gap)

**Validated:** mcp_tool_canary script live since 2026-04-22; closes the gap flagged in canary task #6.
**Source script:** `scripts/mcp_tool_canary.py`
**Persona:** `mcp-tool-canary` (automated; client name `mcp-tool-canary/1.0`)
**Connector URL under test:** `https://tinyassets.io/mcp`

### Invocation

```
python scripts/mcp_tool_canary.py
python scripts/mcp_tool_canary.py --url http://127.0.0.1:8001/mcp
python scripts/mcp_tool_canary.py --verbose --timeout 20
```

### What it exercises

| Layer | What's tested |
|---|---|
| System | `initialize` handshake (same as PROBE-002). |
| System | `notifications/initialized` (MCP-protocol mandatory before tool calls). |
| System | `tools/list` returns a non-empty tools array. |
| System | `tools/call` for `universe action=inspect` returns valid JSON carrying a `universe_id` field. |

### Green criteria

- Exit code 0 — all four steps passed.

### Red signals

- Exit 2 — handshake failed (initialize error, network, TLS, non-200).
- Exit 3 — session establishment failed (no `mcp-session-id` header, or `notifications/initialized` POST errored).
- Exit 4 — `tools/list` failed or returned an empty tools array.
- Exit 5 — `tools/call universe action=inspect` failed or returned an invalid response (no `universe_id`, `isError` set, etc.).

### Why this probe earns a catalog slot

`mcp_public_canary.py` (PROBE-001/002 layer) only probes `initialize`, which proves the daemon answers the MCP handshake but NOT that any tool handler actually works. The "handshake green, tool handler crashed" failure class would go undetected without this probe. Catches a distinct failure mode: handshake passes but a tool handler raises uncaught, an export is broken, or `universe_server.py` boot succeeds but a registered tool fails on first call.

### When to use

- After any code change to `universe_server.py` tool registration or handler bodies.
- After any deploy that adds/renames/removes MCP tools.
- As a continuous Layer-1.5 canary between handshake-only and full chatbot probes.

---

## Adding new probes

A probe earns a catalog entry when:
1. It has been run live (not just designed) against the production endpoint.
2. It has at least one green baseline AND one red baseline (or a documented pre-fix red state).
3. Its green/red criteria are parseable without human judgment.

Draft probes (designed but not yet live-validated) may be kept in the
mission-draft files until they earn a live run.
