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

**Validated:** wiki canary script live since 2026-04-22; logs roundtripped probes to `.agents/uptime.log`. Scheduled in CI 2026-04-26 — Layer-1e step in `.github/workflows/uptime-canary.yml` runs every 5 min on the GHA cron alongside the other Layer-1 probes.
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
| System | `wiki action=write` persists a known content body to `drafts/notes/uptime-probe.md`. |
| System | `wiki action=read` returns that content verbatim. |
| User-impact | Auto-heal pipeline integrity — chatbots filing bugs depend on wiki writes succeeding. |

### Green criteria

- Exit code 0.
- `wiki action=write` succeeds without `isError`.
- `wiki action=read` returns content matching `_CANARY_CONTENT` byte-for-byte.

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

## PROBE-005 — Last-activity freshness (node execution liveness)

**Validated:** registration 2026-04-26 — script live since task #15 landed (tests at `tests/test_last_activity_canary.py`).
**Source script:** `scripts/last_activity_canary.py`
**Persona:** `last-activity-canary` (automated; client name `workflow-last-activity-canary/1.0`)
**Connector URL under test:** `https://tinyassets.io/mcp`

### Invocation

```
python scripts/last_activity_canary.py
python scripts/last_activity_canary.py --url http://127.0.0.1:8001/mcp
python scripts/last_activity_canary.py --threshold-min 60 --verbose
```

Env override: `WORKFLOW_LAST_ACTIVITY_THRESHOLD_MIN` sets the default threshold (minutes).

### What it exercises

| Layer | What's tested |
|---|---|
| System | MCP `initialize` + `notifications/initialized` handshake. |
| System | `universe action=inspect` returns a `daemon.last_activity_at` timestamp. |
| System | The timestamp is fresh — within `--threshold-min` (default 30) of now. |
| User-impact | "MCP green but node execution stalled" failure class — exactly the live-2026-04-22 state before the cloud-side worker landed. |

### Green criteria

- Exit code 0.
- `daemon.last_activity_at` is within the threshold (FRESH).

### Red signals

- Exit 2 — `last_activity_at` exceeds the threshold (STALE — paged regardless of queue depth; persistent stale-but-empty IS pageable per script docstring).
- Exit 3 — daemon responded but no parseable `last_activity_at` (unexpected tool shape, null/malformed field).
- Exit 4 — handshake / connectivity failure (distinct exit so operators can tell stale-execution from dark-daemon at a glance; overlaps with PROBE-001 deliberately).

### Why this probe earns a catalog slot

PROBE-001/002 prove the daemon answers MCP. PROBE-004 proves a tool handler runs. NEITHER proves the daemon is doing actual work — node execution can stall while every probe above stays green. The 2026-04-22 cloud-worker outage is the worked example: green Layer-1, green tool calls, zero scenes shipped. This probe is the only one in the catalog that catches that class.

### When to use

- After any change to dispatcher, executor, or the cloud worker.
- As a continuous Layer-1.5 canary alongside PROBE-002.
- Investigating user reports of "the daemon is up but nothing's happening."

---

## PROBE-006 — Revert-loop detection (busy-broken pathology)

**Validated:** registration 2026-04-26 — script live since revert-loop spec landed; spec at `docs/design-notes/2026-04-23-revert-loop-canary-spec.md`.
**Source script:** `scripts/revert_loop_canary.py`
**Persona:** `revert-loop-canary` (automated; client name `revert-loop-canary/1.0`)
**Connector URL under test:** `https://tinyassets.io/mcp`

### Invocation

```
python scripts/revert_loop_canary.py
python scripts/revert_loop_canary.py --url http://127.0.0.1:8001/mcp
python scripts/revert_loop_canary.py --verbose
```

Env overrides:
- `WORKFLOW_REVERT_CANARY_N` — WARN threshold (default 3)
- `WORKFLOW_REVERT_CANARY_T_MIN` — WARN window minutes (default 10)
- `WORKFLOW_REVERT_CANARY_N_CRITICAL` — CRITICAL threshold (default 5)
- `WORKFLOW_REVERT_CANARY_T_CRITICAL` — CRITICAL window minutes (default 20)

### What it exercises

| Layer | What's tested |
|---|---|
| System | MCP handshake + `get_status.evidence.activity_log_tail` retrieval. |
| System | Terminal REVERT-verdict count within a sliding time window. |
| User-impact | "Daemon IS making progress but every scene REVERTs" — the 2026-04-23 P0 class (67 reverts on `concordance` before host noticed). |

### Green criteria

- Exit code 0 — REVERT count below WARN threshold.

### Red signals

- Exit 2 — WARN: ≥N_WARN REVERTs within T_WARN minutes (page priority=0).
- Exit 3 — CRITICAL: ≥N_CRIT REVERTs within T_CRIT minutes (trigger auto-repair via p0-outage-triage).
- Exit 4 — handshake / connectivity failure (distinct from stale/dark for diagnostics).
- Exit 5 — daemon responded but `activity_log_tail` absent / unparseable.

### Why this probe earns a catalog slot

The 2026-04-23 P0 revert-loop concern is currently top-of-STATUS. PROBE-001 (handshake) and PROBE-005 (last_activity) both stay GREEN during a revert-loop because the daemon IS making progress — it's just throwing every commit away. Only this probe catches the busy-broken state. Spec-driven (Q2 mandate: count terminal REVERT verdicts only; Draft-FAILED retry-recovers within-scene and was explicitly rejected as noise).

### When to use

- After any change to the commit pipeline, scoring rubric, or provider-routing code.
- As a continuous P0 canary — pair with PROBE-005 to cover both "stalled" and "busy-broken" failure modes.
- After provider-quota / model-config changes (a degraded provider is a leading indicator of revert cascade).

---

## Borderline scripts — intentionally not catalogued

These canary-adjacent scripts exist in the repo but do NOT earn standalone catalog slots per the audit's admission criteria. Listed here so future audits can confirm their omission is intentional, not accidental.

| Script | Why no slot |
|---|---|
| `scripts/uptime_canary.py` | Thin wrapper around `mcp_public_canary.probe_result` that adds local-log persistence. Same surface as PROBE-001 — duplicating it as a slot would double-count. The wrapper is the Task-Scheduler-invoked form; PROBE-001 is the user-invocable form. |
| `scripts/uptime_alarm.py` | Escalation **action**, not a probe. Tails `.agents/uptime.log` and emits alarm lines. Note: per task #20, prod alarm log moved to `/var/log/workflow/uptime_alarms.log` (env-overridable). |
| `scripts/selfhost_smoke.py` | Time-bounded Row-F acceptance script (48h offline trial — hour 1, 24, 47). Targets both canonical AND the gated `mcp.tinyassets.io` tunnel for parity comparison; not a steady-state probe. Once Row F closes, this script is archived. |

A "post-fix clean-use evidence" verification primitive (AGENTS.md Quality Gates) also has no automated probe today. This is intentional: the primitive is evidence-gathering against real-user traces, not a parseable green/red script.

---

## Adding new probes

A probe earns a catalog entry when:
1. It has been run live (not just designed) against the production endpoint.
2. It has at least one green baseline AND one red baseline (or a documented pre-fix red state).
3. Its green/red criteria are parseable without human judgment.

Draft probes (designed but not yet live-validated) may be kept in the
mission-draft files until they earn a live run.
