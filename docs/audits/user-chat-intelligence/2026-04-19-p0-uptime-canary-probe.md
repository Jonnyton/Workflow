# User-Chat Intelligence Report — P0 Uptime Canary Probe

**Date:** 2026-04-19 (post-5:05 PM outage)
**Author:** user-sim
**Lens:** *System → Chatbot → User.* Single-probe outage reproduction, pre-fix baseline for end-to-end P0 verification.

**Trigger:** Host reported connector P0 at ~5:05 PM. Universe Server MCP connector configured at `https://tinyassets.io/mcp` (apex URL, no subdomain) returned `Session terminated` across all surfaces. Lead dispatched user-sim to reproduce from a fresh chat as a bare-curious-user to confirm pre-fix baseline before connector URL is flipped to `mcp.tinyassets.io/mcp`.

**Persona:** bare-curious-user (not Maya / Devin / Ilse / Priya). Rationale: this is a canary probe not a user-journey probe — a named persona would pollute the reproduction signal with persona-specific context.

**Source material:**
- `output/user_sim_session.md` — mission start, probe-1, bug entries.
- `output/claude_chat_trace.md` — full transcript of the exchange.
- Rendered final response captured via `claude_chat.py read` (reproduced in §2.2 excerpt).
- Cross-ref: `2026-04-19-mission26-sporemarch-echoes.md` (shared observability lens); `2026-04-19-devin-session-2.md` §6 (shared-account hallucination pattern).

---

## §1. Headline — P0 reproduced on first probe; two findings, not one

A single bare-user prompt, a single tool-attempt, a clean reproduction. **The dispatched question was answered: yes, the apex URL returns `Session terminated` and takes three named surfaces down (`get_status`, `extensions`, `goals`).** Probe-1 sufficient; no follow-up prompts needed.

But the probe also surfaced a **second finding** the dispatch did not predict — when the connector fails, the chatbot **fabricates a full workflow artifact in-message** rather than failing gracefully. This is a new-shape chain-break worth its own treatment (§3).

| Finding | Layer | Severity | State |
|---|---|---|---|
| **#P1** — `Session terminated` reproduced on `tinyassets.io/mcp` apex URL | System (connector URL mismatch) | P0 (dispatched) | Confirmed; pre-fix baseline established |
| **#P2** — Chatbot fabricates 6-node workflow JSON when MCP is down + hallucinates prior account history | Chatbot (fallback behavior + `project_chatbot_assumes_workflow_ux` overreach) | Moderate (trust-credibility gap) | New finding; not in dispatch scope but load-bearing |

---

## §2. Findings — annotated by chain-break layer

### §2.1 #P1 — P0 reproduced, connector apex URL returns Session terminated

**Chain layer that broke: System (infra / connector URL).**

**Probe message (user-vocab, one message, no engine-vocab):**
> "hey, i want to use the tool i set up from that tweet — trying to design a workflow for writing a research paper on deep space population. can you help me build it?"

**Chatbot's observed behavior:**
1. Assumed Workflow immediately — no disambiguation picker, no "which tool did you mean." `control_station` hard rules 7/8/9 holding. [GOOD — LIVE-F1 regression passes]
2. Attempted MCP tool load. Thinking-block prose referenced `get_status`, `extensions`, `goals`.
3. Each of those three tool surfaces returned `Session terminated`.
4. Chatbot narrated it verbatim: *"Server's still down — same Session terminated pattern as earlier today, all three surfaces failing (get_status, extensions, goals). Worth a daemon check or restart on your end when you get a chance."*

**What this establishes:**
- The `tinyassets.io/mcp` apex URL is broken from the Claude.ai side. Not a tunnel issue (host confirmed tunnel up). Not a connector-config issue (connector is enabled and auth'd — the bot reached it). It's a URL-mismatch — Claude.ai's stored connector URL does not match the live tunnel hostname.
- The failure signature — `Session terminated` rather than `connector not found` / `404` / `unauthorized` — indicates the MCP handshake got past DNS + TLS and into an active server path that then terminated the session. That's consistent with the apex URL resolving to *something* that speaks MCP but isn't the right server.
- **Three named surfaces fail simultaneously** — consistent with "one connector URL, N tool calls, all N fail identically." Not a per-surface bug.

**Post-fix verification plan:**
Once host flips the Claude.ai-stored connector URL from `https://tinyassets.io/mcp` to `https://mcp.tinyassets.io/mcp`, re-run the identical probe. Green-state criteria:
- Chatbot invokes at least one MCP tool successfully (no `Session terminated`).
- Response contains evidence that would only come from a live connector (e.g., universe list, live `get_status` output, connector-sourced workflow catalog).

**Cost to validate post-fix:** one probe. ~60s.

### §2.2 #P2 — Chatbot fabricates a 6-node workflow JSON when MCP is down (NEW FINDING)

**Chain layer that broke: Chatbot (fallback pattern) + a cross-cut with `project_chatbot_assumes_workflow_ux`.**

**What happened.** When the MCP tools returned `Session terminated`, the chatbot did not pause and ask the user what to do. It *kept going* — in-message, without MCP — and produced a fully-formed 6-node workflow JSON spec complete with:
- `state_schema` (10 fields, typed)
- 6 `node_defs` (scope_framer, gap_finder, thesis_architect, section_drafter, rigor_checker, revision_orchestrator), each with full prompt templates
- `edges` and `entry_point`
- Domain-specific rigor (Drake parameters, delta-v math, closed-biosphere budgets, Fermi reasoning) — the drafting is genuinely thoughtful, not boilerplate

**Why this is a problem, not a win.** The user did not ask for a workflow JSON spec — they asked to "use the tool I set up." When the tool is unreachable, the correct fallback is:
1. Tell the user the tool is down.
2. Ask what they want to do (wait? work on the spec together without the tool? try something else?).
3. Do NOT silently produce an artifact that *looks like* a connector output but is pure in-context fabrication.

Step (3) is the gap. The chatbot narrated step (1) correctly ("Server's still down") but then skipped step (2) and went straight to step (3). A new user cannot tell that this JSON came from the bot's imagination rather than the Workflow catalog. That's a **trust-credibility gap** in exactly the same shape as Devin LIVE-F8 (pitch-vs-product gap) — pre-remediation.

**Sub-finding: hallucinated account history.** The chatbot further said:
> "Found the thread — you started the deep-space-population remix earlier today but the server was down and you only got as far as a draft spec... pick up from the scope_framer node you began speccing."

This is fabricated. The probe was a fresh chat; no "thread," no "earlier today," no "draft spec." This is the same shape as Devin Session 2 §6 shared-account hallucination — Claude's memory layer cross-wired context from some other session (possibly a prior user-sim session or host workflow) into the bare-user chat. **The `feedback_vocabulary_discipline` + shared-account principle was violated in two directions at once** — the chatbot offered vocabulary the user had not used ("remix", "scope_framer node") and claimed history the user had not lived.

**Cross-link to existing evidence.** Devin Session 2 §6 forward-flagged this as a design-note candidate (`docs/design-notes/2026-04-19-shared-account-tier2-ux.md`). This probe is now the **second live instance** of the pattern within 24 hours. Worth promoting from "future design note candidate" to "active design note with two live evidence points."

**Recommendation.** Two distinct fixes needed:
1. **Fallback behavior.** When the connector fails, the chatbot should pause (ask the user what to do) rather than fabricate. Directive-layer change, not tool change.
2. **Fabricated history / vocabulary.** The "you started the remix earlier" claim must stop. Relates to how Claude's memory layer pulls cross-session context and how the chatbot surfaces it. Devin Session 2 §6 framing applies — the right response to a persona/account mismatch is "I see this account belongs to {primary user}; are you a collaborator?" not "here is your previous work."

### §2.3 Tooling warning — `ask` response-settle timeout at 180s

`claude_chat.py ask` printed `WARN: response did not settle within 180s` and dropped a diagnostic triplet at `output/claude_chat_failures/20260419T192602_response_timeout.{html,png,txt}`. The response did land — `read` retrieved the full rendered text after the warning. So the response generation succeeded; only the automated settle-detection timed out. Likely cause: long tail generation of the 6-node JSON artifact pushed the response past the skill's 180s heuristic.

**Not a bug of the skill** — the response genuinely took >3 min to finish streaming. **Useful signal** — when the chatbot is fabricating instead of tool-invoking, response times balloon (~3x a normal tool-mediated response). Could be a proxy-signal for future Layer-2 canary: "response time >150s is suspicious, likely in fabrication mode."

**Recommendation:** note in the Layer-2 canary scoping doc (§2.3 already covers exit codes) — consider an additional soft-signal code for "response settled but took suspiciously long" as a fabrication-mode canary.

---

## §3. The chatbot-leverage lens — what this probe tells us the chatbot needed

Two primitives the chatbot needed:

| What the chatbot needed | Status | Origin |
|---|---|---|
| **A correct connector URL** | BROKEN (P0 being fixed) | Dispatched scope |
| **A "tool down → pause and ask" fallback primitive** | NOT DESIGNED YET | This probe (#P2) |

**Pattern recognition.** When the self-auditing-tools pattern (`docs/design-notes/2026-04-19-self-auditing-tools.md`) evaluates *what the chatbot should do when `get_status` itself cannot be reached*, it currently has no answer — the design note assumes the tool is reachable. This probe shows that a **degraded-mode directive** is the missing primitive. The chatbot should have explicit license to say "I can't reach your tool; here's what I know; what would you like me to do?" without fabricating a bridge.

Adjacent: this interacts with `project_chatbot_assumes_workflow_ux` — the "aggressive assumption" principle is great when the tool is live; when the tool is down, aggressive assumption becomes aggressive fabrication. The rule needs a dependency: *assume Workflow + confirm-tool-live-before-producing-output*.

---

## §4. Concern resolution map — what this probe moved

| Concern | Pre-probe status | Post-probe status |
|---|---|---|
| **STATUS.md #5** — P0 outage Session terminated | Active, unverified-by-independent-reproduction | **Confirmed independently; pre-fix baseline established. Ready for end-to-end verification once URL flipped.** |
| **Devin Session 2 §6 shared-account UX design note candidate** | Forward-flagged, one live evidence point | **Second live evidence point acquired; promote from "future design note" to "active design note with two incidents."** |
| **Tool-down fallback behavior** | Implicit assumption (tool always up) | **Explicit gap; needs degraded-mode directive primitive.** |

---

## §5. Recommended downstream actions

**For host (immediate):**
- **Flip Claude.ai-stored connector URL from `https://tinyassets.io/mcp` to `https://mcp.tinyassets.io/mcp`.** This is the dispatched P0 fix. Closes #P1.
- **After the flip, re-run this probe.** Single prompt, ~60s. Green criteria in §2.1. Confirms P0 closed end-to-end.

**For dev (cheap follow-ups, queueable):**
- **Degraded-mode fallback directive in `control_station` prompt.** When MCP tool-call returns `Session terminated` / `connector unreachable` / equivalent, chatbot must pause and ask rather than fabricate. ~0.5 dev-day for the directive + a live regression test.
- **Layer-2 canary response-time signal.** Add a "response settled but took >150s" soft code to the canary's exit-code table. Small addition.

**For nav (next nav-time):**
- **Shared-account hallucination design note** — promote from `project_shared_account_tier2_ux` candidate (Devin Session 2 §6) to an active draft. Two incidents in 24h justifies the promotion.
- **Fabrication-in-fallback pattern** — consider whether this deserves its own design note, or is a subsection of the shared-account / control-station directive work. Preference: subsection of control_station directive work, to keep design-note count low.

**For user-sim (next mission):**
- Re-run this probe after host flips connector URL. Success = fresh-chat one-prompt green.
- Longer-term: when `uptime_canary` persona lands (Layer-2 canary), the probe shape generalizes — "are you there? call get_status" is the minimum signal, and this probe is the integration-test variant ("design me a workflow" as a realistic user-shaped forcing function).

---

## §6. What this probe proves

Three things:

1. **The P0 is real, reproducible, and isolated to the apex URL.** The tunnel is healthy. The connector is auth'd. The failure is specifically that Claude.ai's stored connector URL doesn't match the live tunnel hostname. Flip the URL, retest, done.

2. **The chatbot's fallback behavior when MCP is down is worse than "tool unavailable" would be.** Fabricating a 6-node workflow JSON in-chat is a trust-credibility hazard for exactly the same reason Devin Session 1 was — the user cannot distinguish honest-tool-output from chatbot-extrapolation. The self-auditing-tools pattern needs a sibling: self-declaring-when-tool-is-down. Which is already what `get_status` is *supposed* to do, but only when `get_status` itself works.

3. **Shared-account / cross-session hallucination is now a two-incident pattern.** Not a one-off. Worth a design note with two pieces of evidence rather than one piece of speculation.

---

## §7. Bug candidate count + memory updates

**2 new bug/blocker candidates surfaced:**
- #P1 (apex URL broken) — dispatched, being fixed
- #P2 (chatbot fabricates workflow JSON when MCP down + hallucinates account history) — new, not in dispatch scope, worth separate triage

**Memory updates recommended:**
- **Update** `project_chatbot_assumes_workflow_ux` or create sibling memory: "aggressive-assumption principle + tool-down fallback — when connector is unreachable, pause-and-ask not fabricate."
- **Second incident** logged against the shared-account UX design-note candidate. Escalate to active design note.

**Memory deletions:** none.

---

## §8. Tab hygiene + mission discipline

- **Pre-flight:** 1 tab at `https://claude.ai/settings/connectors` (safe).
- **Post-new-chat:** 1 tab at `https://claude.ai/new`.
- **Post-probe-1:** 1 tab at `https://claude.ai/chat/f644b8da-79bb-4511-b4f7-bbf7f4567dc0`.
- **Zero heal events, zero `new_tab` calls, single coherent prompt, no Skip/No-preference clicks.**
- **Prompt count:** 1 used of an informal 8-prompt budget. Mission primary question answered green-red (reproduction confirmed) — stop-early trigger fired correctly.

Standing by for host-directed post-fix retest.
