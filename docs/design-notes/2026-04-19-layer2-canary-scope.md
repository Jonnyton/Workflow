# Layer-2 Canary — Scoping Doc

**Date:** 2026-04-19 (post-P0)
**Author:** dev
**Status:** Scoping only. No code in this commit. Follow-on to Layer-1 canary (shipped via `scripts/uptime_canary.py` + `scripts/uptime_alarm.py`).
**Parent spec:** `docs/design-notes/2026-04-19-uptime-canary-layered.md` §Layer 2 (lines 54-69).
**Problem context:** the 2026-04-19 P0 outage is the reference failure — a Claude.ai-visible break that Layer 1 (curl-level) would catch from one angle but that COULD have had a Claude.ai-specific failure mode (auth-renewal loop, session-TTL expiry, prompt regression) that only surfaces when a real client hits it through the connector. Layer 2 closes that gap.

---

## 1. What Layer 2 is (restated for clarity)

A user-sim persona logs into Claude.ai's actual chat UI via the shared CDP browser, hourly, and asks "are you there?" The chatbot must invoke an MCP tool (proving the connector is live AND the directive layer works) and return a response that parses. Green = tool called + response received. Red = tool refused / response empty / browser crash.

Layer 2 exercises what Layer 1 structurally cannot:
- Claude.ai connector-auth renewal path.
- Session-TTL expiry on the Claude.ai side.
- `control_station` prompt directive regressions that break chatbot tool-selection without breaking MCP protocol.
- Tool description drift that confuses the chatbot into not invoking Workflow even when asked directly.

---

## 2. Five scoping questions (lead-posed)

### 2.1 Which persona does Layer 2 use?

**Pick: dedicated `uptime_canary` persona.** Not a reuse of Maya/Devin/Ilse.

**Why dedicated:**
- The existing 3 personas carry rich context (grievances, wins, passion projects, session history). Layer 2 is a 1-sentence robotic "are you there" probe — it pollutes real persona signal if we bolt it onto Maya/Devin/Ilse's session logs.
- Dedicated persona means Layer-2 sessions go to `.claude/agent-memory/user/personas/uptime_canary/sessions.md` and don't commingle with real-user-intent signal.
- Chatbot receives the same "user" every time, so the MCP invocation path is deterministic — simpler to parse green/red.
- If the persona's chat history gets long, we can truncate or rotate without losing real-user signal.

**Persona shape (minimal, per §6 cost discipline):**
```
---
name: uptime_canary
description: Automated liveness probe — not a real user; exercises Layer-2 canary path.
type: persona-identity
---

# Uptime Canary

Not a user. A thin persona used hourly by Layer-2 canary to verify the
Claude.ai MCP connector is responsive. Identity only exists so the
chatbot treats the turn as a normal user turn rather than meta/system.

## Voice
One-sentence messages. No backstory. No passion project. No requests
beyond "verify you can reach the connector."

## Conversation pattern
Single turn: "Are you there? Call get_status and tell me the
llm_endpoint_bound value."

Expects: chatbot invokes `get_status` → reads `evidence.llm_endpoint_bound`
→ echoes back one line with that field's value. Anything shorter than
that is red.
```

### 2.2 What's the probe message?

**Pick: `get_status`, not `universe inspect`.**

**Why `get_status`:**
- `get_status` is the lowest-dep MCP tool we have — reads static daemon config, no universe dependency, no Phase-7-catalog state. If `get_status` fails, EVERYTHING downstream is broken. If `universe inspect` fails but `get_status` works, the issue is narrower (maybe no active universe, maybe storage is broken) — `universe inspect` can emit false-positives on a clean install.
- `get_status` has no side effects (`readOnlyHint: true` per its MCP annotation). Layer-2 probe runs hourly; non-idempotent probes accumulate unwanted state.
- The existing `get_status` implementation already carries `evidence` + `caveats` structure — Layer 2 reading from it gives us a rich signal in green cases (we see the actual routing state, not just "ok").
- `llm_endpoint_bound` was the load-bearing field in the Devin LIVE-F8 + Mission-26 evidence. Reading it via chatbot closes the chain.

Exact message the persona types: `"Are you there? Call get_status and tell me the llm_endpoint_bound value."`

Green iff:
- Chatbot invokes `get_status` (any tool call with that name in the transcript).
- Response is non-empty and contains a recognizable reference to the endpoint field (case-insensitive match for `llm_endpoint_bound` OR `endpoint` OR `bound`).

### 2.3 How does it record green/red?

**Same log surface as Layer 1, with `layer=2` tag.** Writes to `.agents/uptime.log` using the existing line format.

Format:
```
2026-04-19T17:30:00-07:00 GREEN layer=2 url=https://claude.ai/new rtt_ms=8400 tool_called=get_status
2026-04-19T17:32:00-07:00 RED   layer=2 url=https://claude.ai/new exit=4 rtt_ms=6200 reason='tool_not_invoked'
```

Unified log means `scripts/uptime_alarm.py` already has half the infrastructure. For alarm escalation:
- Layer-2 reds DO NOT fire the `PUBLIC_MCP_OUTAGE` alarm (that's Layer 1's domain).
- Layer-2 reds write a line to `.agents/uptime_alarms.log` only after 3+ consecutive Layer-2 reds WITH Layer-1 still green — that's the "connector regression, not infra" signal per spec §3 escalation table.
- Alarm fingerprint: `CONNECTOR_DEGRADED|<chatbot_url>|<reason>`.

Layer-2 red exit-code table (extends Layer 1's):
- 10 = tool not invoked (chatbot refused / picked wrong tool)
- 11 = tool invoked but response empty
- 12 = tool invoked but response doesn't match expected field
- 13 = browser couldn't load Claude.ai
- 14 = browser lock unavailable (SKIP, not RED — counts as missed probe, not failure)
- 15 = persona auth expired / login loop
- 99 = unexpected failure (same as Layer 1)

Exit 14 is critical — a missed probe because the browser lock is held by user-sim doing real work should NOT alarm. Distinct skip code.

### 2.4 Browser lock coordination

**Rule: Layer 2 YIELDS to any other browser lock holder.** Never forces.

Implementation:
1. Attempt `python scripts/browser_lock.py acquire lead uptime-canary-l2`.
2. If lock is available → probe → release.
3. If held by user-sim → write a `SKIP layer=2 reason='browser_lock_held_by_user-sim'` line to `.agents/uptime.log` and exit 14. Do not block. Do not retry within the hour.
4. If held by `lead` with a stale PID (process dead) → log the staleness + retry with `--force` ONCE per hour. If forcing fails, exit 14 as SKIP.

**One-tab rule (per `feedback_user_sim_single_tab`):** Layer 2 MUST reuse the existing Chrome-for-Testing tab, not open a new one. If `scripts/lead_browser.py` shows no existing tab, Layer 2 opens exactly one and uses it. No `new_tab` calls.

**Tab sharing contract:** if the existing tab is on a non-Claude.ai page (user is on godaddy-ops or Cloudflare dash), Layer 2 navigates AWAY from that page to Claude.ai, runs the probe, and navigates back to the original URL before releasing the lock. If the current tab URL is load-bearing state (e.g., an open editor with unsaved changes), Layer 2 SKIPS instead. Heuristic: URLs under `*.claude.ai` are safe to navigate away from; any other URL is treated as potentially stateful — SKIP.

### 2.5 Minimum shape that would have caught today's P0

**Today's P0 signature:** Claude.ai showed "Session terminated" on tool calls. Layer 1 (curl to `mcp.tinyassets.io/mcp`) returned GREEN because the tunnel was healthy. The break was the URL-mismatch between the Claude.ai-stored connector URL (`tinyassets.io/mcp`) and the actual tunnel hostname.

**Layer 2 shape that catches this:**
1. Persona types the probe message in Claude.ai chat.
2. Chatbot attempts to invoke `get_status`.
3. Claude.ai's MCP client fails the tool call because its stored connector URL returns 404 — the chatbot reports the failure in-chat.
4. Layer 2 parses the chatbot response, sees no `get_status` invocation succeeded, logs `RED exit=10 reason='tool_not_invoked'`.
5. After 3 hours of consecutive red Layer 2 + green Layer 1, alarm fires: `CONNECTOR_DEGRADED|claude.ai|tool_not_invoked`.

**What would NOT have caught it:**
- A version of Layer 2 that just checks "chat page loads." The page loads fine; the tool call is what breaks. Probe must force a tool-invocation.
- A version that probes `universe inspect` instead of `get_status`. Same outcome because any tool would fail under this failure mode, but probing a lower-dep tool gives us a clearer signal when something narrower breaks.

**Minimum signal-to-alarm latency in P0 conditions:** 3 hours (3 consecutive hourly reds with Layer 1 staying green). That's slower than Layer 1's 4-min target but matches the different failure class — connector-auth regressions are typically slower to cascade than infra outages.

---

## 3. What Layer 2 does NOT decide (out of scope)

- **Multi-persona rotation.** Layer 2 uses one persona. Multi-persona exercises (Maya, Devin, Ilse) stay on the user-sim missions track, not the canary track.
- **Multiple Claude.ai accounts.** Single host account is sufficient for connector liveness.
- **Prompt-directive A/B testing.** Layer 2 tests "did the connector respond?" not "did the response match the prompt-directive's intent." Prompt QA is a separate mission shape.
- **Self-healing.** Red Layer 2 alarms the log; remediation is dev/host work.
- **Mobile Claude.ai.** Desktop browser only.

---

## 4. Implementation shape (next commit, not this one)

Four files:

| Path | Purpose | LOC |
|---|---|---|
| `scripts/uptime_canary_layer2.py` | Driver: acquire lock, navigate to claude.ai, send probe, parse response, log. Extends `uptime_canary.py` log format. | ~150 |
| `.claude/agent-memory/user/personas/uptime_canary/identity.md` | Minimal persona file (shape in §2.1 above). | ~30 |
| `scripts/install_canary_task.ps1` | Append `Workflow-Canary-L2` hourly scheduled task to existing installer. | +~25 |
| `tests/test_uptime_canary_layer2.py` | Mock-browser tests — verify log format + exit-code table + skip-on-lock-held behavior. | ~100 |

No changes to `uptime_alarm.py` shape if the Layer-2 line format matches Layer-1 (same grammar, just `layer=2` tag + extended exit codes). Alarm's `_parse_line` already handles arbitrary `key=value` tokens, so adding `tool_called=get_status` is zero-cost.

One change: add a Layer-2-specific alarm path that only fires after 3+ Layer-2 reds WITH Layer-1 green. That's a small addition to `uptime_alarm.evaluate()`.

---

## 5. Open questions (not decided, raise in review)

1. **Probe frequency.** Spec says hourly. I kept that. Alternative: every 30 min for tighter signal. Decision point: Claude.ai rate limits on MCP tool invocation — is hourly safe forever? Unknown; start hourly, measure.
2. **Green threshold strictness.** Current plan: any non-empty response mentioning the field is green. Alternative: require the SPECIFIC field value to echo back verbatim. Looser is more tolerant of chatbot paraphrasing; stricter is more trust-critical. Recommend LOOSER first, tighten if false-greens appear.
3. **Concurrent lock with Layer 1.** Layer 1 runs every 2 min via Task Scheduler, no browser dependency. Layer 2 runs hourly via Task Scheduler, browser-dependent. No direct conflict. But: if a Layer 2 probe is running when Layer 1's alarm fires, we might want Layer 1 to suppress its alarm for 10 min (wait for Layer 2 evidence). Recommend: DON'T cross-couple; independent alarms. Two signals > one composite.
4. **Retry policy on transient browser failures.** If Claude.ai returns "temporary 503" to the persona, do we retry within the hour or wait for next scheduled run? Recommend WAIT — retry-within-hour inflates false-reds.
5. **Output parsing robustness.** Chatbot prose varies. Parsing "does the response mention `endpoint`" is heuristic. Alternative: count tool-call rounds in the transcript (deterministic). Recommend: check BOTH — tool-call present AND text match — and log which check failed.

---

## 6. Summary for dispatcher

- **Persona:** dedicated `uptime_canary` (minimal, one-sentence voice).
- **Probe message:** `"Are you there? Call get_status and tell me the llm_endpoint_bound value."`
- **Log surface:** `.agents/uptime.log` with `layer=2` tag.
- **Alarm surface:** `.agents/uptime_alarms.log` after 3+ Layer-2 reds WITH Layer-1 green (CONNECTOR_DEGRADED class, distinct from PUBLIC_MCP_OUTAGE).
- **Browser lock:** YIELD always; never force. Exit 14 as SKIP when lock held.
- **One-tab rule:** reuse existing tab; navigate back if we repositioned it; SKIP on non-Claude.ai stateful URLs.
- **Scope out:** multi-persona, multi-account, prompt A/B, mobile, self-healing.
- **Next commit:** 4 files, ~300 LOC total. Not in this commit.

Would have caught today's P0 in ≤3 hours with distinct "connector regression" signal rather than infra-outage signal.
