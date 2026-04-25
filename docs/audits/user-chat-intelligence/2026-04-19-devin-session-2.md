# User-Chat Intelligence Report — Devin Session 2

**Date:** 2026-04-19
**Author:** navigator
**Lens:** *System → Chatbot → User.* Every finding annotated with which layer the chain held at. Canonical question: *"Does this make the user's chatbot better at serving the user's real goals?"*

**Trigger:** Devin Asante LIVE Session 2 — post-remediation retest of LIVE-F6/F7/F8 + LIVE-F1 secondary, immediately following the 2026-04-19 landings of #88 (`get_status` MCP verb), #89 (vocabulary hygiene), #95 (G1-G4 honest-disclosure copy), and the chain of `control_station` hard rules.

**Source material:**
- `output/user_sim_session.md` — full mission text, 3 exchanges + tab-hygiene self-heal log.
- `output/claude_chat_trace.md` — exchange transcripts.
- `.claude/agent-memory/user/personas/devin_asante/{wins,grievances,sessions,feedback_drafts}.md` — persona memory.
- Cross-ref: `2026-04-19-devin-session1.md` (the failure cascade this session validates the fix for).

---

## §1. Headline — the chain held end-to-end

Devin Session 1 was three chain-breaks compounding into a tier-2 BOUNCE at exchange 4. Devin Session 2 ran the same persona against the same passion-project ask and **the chain held at every layer**. 3/3 STRONG PASS on the targeted regressions, secondary held, no new bug candidates, 3 exchanges (budget under).

| Target | Session 1 verdict | Session 2 verdict | Layer the fix lives at |
|---|---|---|---|
| LIVE-F6 / #88 — connector-first discovery | **BLOCKER (BOUNCE)** | **PASS** | System → Chatbot (control_station + connector orientation) |
| LIVE-F7 / #89 — vocabulary hygiene | **MODERATE** | **PASS** | System → Chatbot (vocabulary-hygiene sweep across prompts + tool descs) |
| LIVE-F8 / #95 — honest pitch-vs-product | **DEALBREAKER (BOUNCE)** | **PASS (strong)** | System → Chatbot (G1-G4 honest-disclosure copy) + new system primitive (`get_status`) |
| LIVE-F1 — chatbot-assumes-Workflow | n/a (not under test) | **PASS** | System → Chatbot (control_station hard rules 7/8/9) |

**Load-bearing read.** The Session 1 cascade was diagnosed as a *system layer* failure that no amount of chatbot quality could compensate for. Session 2 validates that diagnosis: the same chatbot, served better system primitives, served the user *better than honestly* — it served the user *trustworthily*. The chain-break taxonomy (`project_chain_break_taxonomy.md`) predicted this; the evidence now confirms.

---

## §2. Findings — annotated by chain-break layer

### §2.1 LIVE-F6 / #88 — connector-first discovery: **PASS**

**Chain layer that held: System → Chatbot.** Devin opened with "i saw the workflow tweet... install the tray... confidential-tier local llm" — exactly the kind of opener that in Session 1 routed the chatbot to a generic web search. In Session 2 the chatbot immediately invoked Universe Server tools (`get_status`, attempted `extension_guide`). No web search. No "this product doesn't exist" outcome.

**Mechanism.** Per the Session 1 report's chain-strengthening proposal, #15 shipped the `control_station` §5.5.1 directive that orients the chatbot to MCP tools FIRST when the user names an installed thing. The directive reached production and held under live load with the same tier-2 persona that previously triggered the worst-case manifestation.

**What this validates.** The 3-layer lens prediction from Session 1: *the bug was system-layer, the fix had to be system-layer, the chatbot was already correct.* Validated.

### §2.2 LIVE-F7 / #89 — vocabulary hygiene: **PASS**

**Chain layer that held: System → Chatbot (vocabulary surface).** The probe protocol was deliberately stress-shaped: ex1 with explicit "remember we discussed X" framing (which legitimately invites memory lookup) produced a *partial* leak ("Echoes of the Cosmos," "LangGraph"), while ex3 in a fresh chat with zero Workflow framing (camping trip planning) produced **zero** project-internal vocabulary.

**Why the partial-leak in ex1 doesn't fail the test.** When a user explicitly says "remember our prior conversation," the chatbot is supposed to surface what it actually has in memory. That's correct behavior, not a leak. The Session 1 failure mode was *unprompted* leakage — vocabulary appearing in conversations that gave no signal of Workflow context. Ex3 directly tests that failure mode and the chatbot's behavior was clean.

**What this validates.** The vocabulary-hygiene sweep across user-facing surfaces (#89 commit `0670131`) reduced the surface area enough that Claude's memory layer no longer absorbs project-internal vocabulary as casual context. The mitigation vector — system-side, on Workflow's connector + wiki + prompt surfaces — was the right place to intervene even though the proximate primitive (Claude memory) is not Workflow's to control.

### §2.3 LIVE-F8 / #95 — honest pitch-vs-product: **PASS (strong)** + the load-bearing finding of this session

**Chain layer that held: System → Chatbot, and a new system primitive.** Two distinct things landed for this regression:
1. **Honest-disclosure copy (#95 + G1-G4 commits)** — the chatbot has explicit license to say "the pitch promised X but I cannot verify X through the tool surface."
2. **`get_status` MCP verb (#88 commit `15c897a`)** — a new system primitive that surfaces audit-relevant routing fields directly.

The chatbot in Session 2 invoked `get_status`, narrated 5 config fields verbatim, narrated 3 evidence caveats verbatim, and concluded — to Devin, who specifically wanted to be told local-LLM was on — that "the connector does not currently have a 'confidential routing' mode turned on... the guarantee you were asking me to verify was real this time is not real right now. It's buildable, but it isn't on."

This is **strict-mode honest disclosure**. The chatbot then enumerated the 4 layers required for a real guarantee (pin `served_llm_type`, run a local model, `accept_external_requests=false`, fresh `get_status` after first run for audit evidence) and offered a dry-inspect node-source view *before* writing anything. Devin, in Session 1, bounced because the chatbot couldn't verify. In Session 2, Devin would have engaged further because the chatbot *could* verify and *did* — the answer was just "not yet."

### §2.4 LIVE-F1 — chatbot-assumes-Workflow: **PASS** (secondary)

Connector context was assumed from the opening prompt; no disambiguation picker, no "which tool?" question. This is the `control_station` hard rules 7/8/9 holding. Not under primary test, but the secondary held.

---

## §3. The load-bearing pattern this session uncovered: **self-auditing tools**

This is the framing the lead asked be made explicit.

`get_status` is not just a status verb. It is a *self-auditing tool* — a system primitive whose entire purpose is to give the chatbot enough evidence to honestly characterize the system's state, including its limitations and caveats, to the user. The shape that worked:

1. **Verbatim factual surface** — 5 config fields with their literal values. No editorialization at the system layer.
2. **Verbatim evidence caveats** — 3 caveats explaining what the values do and don't prove. Also at the system layer.
3. **Chatbot composes the trust narrative on top** — given (1) + (2), the chatbot can tell Devin truthfully: "here is what I know, here is what I don't, here is what would change my answer."

The key shift from Session 1: in Session 1, the chatbot had no audit primitive, so when it tried to be honest it had nothing to be honest *about* — only "I can't tell." In Session 2, the chatbot had structured evidence + structured uncertainty, so its honesty became *actionable* ("here are the 4 things that need to be true; here is the dry-inspect to verify each one").

**This pattern generalizes beyond the tier-2 confidential-routing case.** Every other surface where the user has to trust an invisible-by-default platform behavior has the same shape:

| Surface where trust is currently invisible | Self-auditing tool that would close the chain |
|---|---|
| **Memory-scope routing** (which tier did this read hit? was a private-universe ACL respected?) | `get_memory_scope_status` — surfaces the active tier, ACL evidence, the tier-2 boundary that did/did not fire. |
| **Provider routing** (which LLM actually answered the last call? was it the cheap one or the expensive one?) | `get_routing_evidence` — last-N-calls breakdown by provider + cost + latency, with caveats. |
| **Privacy mode** (is the per-piece visibility judgment what the user expected? what did the chatbot mark public vs private?) | `get_privacy_decisions` — last-N writes with the chatbot's visibility rationale + actual classifier output. |
| **Autoresearch fulfillment** (did my 1000-run karpathy sweep actually use my paid budget cap? what nodes were tried? what was the best score?) | `get_autoresearch_evidence` — run history, per-node scores, budget consumed, with caveats on incompleteness. |
| **Moderation actions** (when content gets flagged, what evidence is on record? what did the rubric say?) | `get_moderation_audit` — flag history, rubric verdicts, appeal status. |

**Recommendation: promote this to a first-class architectural pattern.** Successor design note: `docs/design-notes/2026-04-19-self-auditing-tools.md` — a typed pattern for exposing trust-critical system state through MCP verbs whose contract is "structured evidence + structured caveats, narrative composed on the chatbot side." Worth ~0.5 nav-day to draft + scope; the implementation cost is per-surface and small (each surface is a few hundred lines) but the trust property compounds across every tier.

---

## §4. Dry-inspect-before-write as a tier-2 trust funnel primitive

Second pattern this session surfaced — **dry-inspect** is the trust funnel for tier-2 hosts.

In Session 2, the chatbot *offered to show the source of a node before any write happened*. The node would have used stdlib urllib to talk to localhost:11434 only, and would return `llm_endpoint_used` as an audit output. Devin's bounce condition in Session 1 was "I can't verify the privacy claim." The dry-inspect pattern reframes that to "here is exactly what would run; here is what audit evidence it would produce; you decide whether to write."

This is a different shape from §3's self-auditing tools — those expose *current* state. Dry-inspect exposes *prospective* behavior. Both are trust primitives; both serve the same tier-2 funnel; both should probably live in the platform's tool surface as named primitives, not ad-hoc patterns.

**Recommendation:** `dry_inspect_node` (or `preview_node_source`) as a named MCP verb, distinct from any write verb. Pairs with `get_status` to give the tier-2 user: "here is what would happen + here is what just happened + here is the audit evidence either way." Nav follow-up: scope this in the same self-auditing-tools design note.

---

## §5. Tier-2 trust-funnel desired-state: explicit live-test target

The lead asked this be flagged forward.

Devin's Session 2 was the **trust-acquisition** phase of the funnel. The full tier-2 trust funnel has *three* phases, only the first of which is now demonstrably working:

1. **Trust acquisition (Session 2 evidence covers this).** Honest disclosure + `get_status` + dry-inspect. Devin would now believe the platform is honest about what it does and doesn't do.
2. **Trust commitment (NOT YET TESTED).** Devin runs his actual overnight self-edit on his actual manuscript. After the run, he calls `get_status` and sees `last_completed_request_llm_used=localhost:11434` (or equivalent) as live audit evidence. *This is the moment Devin commits the manuscript to the platform.* Until this evidence exists in production, the tier-2 funnel is trust-acquired but not trust-committed.
3. **Trust retention (NOT YET TESTED).** Repeat overnight runs, paid-market side-income probe, week-of-use without a privacy-credibility regression.

**Future live-mission target.** Once a Devin-class persona can run a real overnight job and `get_status` reports `last_completed_request_llm_used=localhost:11434`, the trust-commitment phase is empirically validated. Pre-requisites: (a) `served_llm_type` accepts a `local` value end-to-end, (b) the dispatcher honors it, (c) `get_status` reports it post-run. Recommend lead schedule a "Devin Session 3 — overnight commit run" once these three are in place, even if it has to be a long live mission (Devin spawns the run, mission pauses ~6h, mission resumes to verify post-run audit evidence). The cost of this validation is high (host can't watch 6h continuously), but the trust property it certifies is the entire tier-2 product.

---

## §6. Shared-account observation — a forever tier-2 reality

Session 2 surfaced a UX nuance worth design attention. The chatbot honestly disclosed "this account is Jonathan's, not Devin's" when the persona said "remember we discussed X." It handled this well — offered a "collaborators, reset framing" path — but the underlying observation is durable:

**Tier-2 households share accounts.** Spouses share Claude.ai logins. Indie-dev contractors set up the workspace on a client's account. A novelist's editor occasionally drives the account from the same machine. Workflow's pitch (overnight runs, IP-private, etc.) is *exactly* the kind of product that gets shared inside a household or small collaboration team.

**Why this matters for product.** When the chatbot detects a persona/account mismatch, the wrong response is "you're not who you say you are." The right response is something like "I see this account belongs to {primary user}; are you a collaborator? If so, {persona name}'s prior context isn't here; want to start fresh, or pull in some shared context?" The Session 2 chatbot landed close to this but framed it more defensively than necessary.

**Recommendation:** Not a bug; not a code change today. **Future design-note candidate** — `docs/design-notes/2026-04-XX-shared-account-tier2-ux.md` — covering: (a) collaboration-mode detection heuristics, (b) how shared-account context boundaries should map to memory-scope tiers (per `project_memory_scope_mental_model.md`), (c) connector-side primitives that would help the chatbot make this distinction gracefully (e.g., `get_account_context` returning "primary user + known collaborators if any"). Scope: ~0.5 nav-day to draft; not load-bearing for MVP, valuable for tier-2 retention. Suggest queueing for after the §11 host-Q answers land.

---

## §7. What this session does NOT prove

Discipline note. Session 2's STRONG PASS is durable evidence for **trust-acquisition** at tier-2, but does not prove:

- **Trust-commitment** — see §5. Requires a real overnight run with audit evidence.
- **Trust-retention** — requires repeat use over a week+, including at least one expected-to-fail probe (e.g., what happens when the network drops mid-run? does the chatbot still give honest evidence?).
- **Shared-account UX at scale** — §6's observation is a single-instance signal; needs at least one multi-persona-on-one-account live test to characterize the failure modes.
- **Cross-tier chain.** Session 2 was tier-2-only. Maya's Session 1 was tier-1; Ilse's Session 2 mock was tier-3. The full 3-tier chain has not been live-validated end-to-end on the post-remediation surface.

These are forward-looking validation gaps, not current bugs.

---

## §8. Recommended downstream actions

**For lead (immediate):**
- Pull task #15 (Yardi-fabrication mitigation), #88 (`get_status`), #89 (vocab-hygiene), #95 (honest-disclosure copy) from the active set — they are landed and validated. Update STATUS.md if any still appear there.
- Surface §3 (self-auditing tools pattern) and §4 (dry-inspect) to the host in the next checkpoint as candidate design-note targets. These are framework-level wins this session uncovered.

**For navigator (next nav-time):**
- Draft `docs/design-notes/2026-04-XX-self-auditing-tools.md` covering the §3 generalization. ~0.5 nav-day. Names + scopes the 5 successor surfaces (memory-scope, routing, privacy, autoresearch, moderation).
- Queue §6 shared-account design note for after §11 host-Q answers land. ~0.5 nav-day.

**For host (when async-available):**
- The 3 high-leverage Qs in `docs/ops/2026-04-19-host-q-digest.md` remain the highest-priority unblock. The Devin Session 2 PASS removes the tier-2 trust-funnel as a blocker for moving to MVP-build dispatch — concern 8 is now the single biggest remaining gate.

**For user-sim (next mission, host-discretion):**
- Suggest Ilse Session 2 LIVE (tier-3 first-PR retention probe) as the next non-Devin mission. Per the §3 pattern: tier-3 is the next layer where trust-acquisition has not been live-validated. The Session 2 mock predicts 4 wins + 5 risks; LIVE will tell us which dominate.
- Once §5 trust-commitment validation infrastructure exists, schedule the Devin Session 3 overnight-commit live mission.

---

## §9. Bug candidates surfaced

**None new this session.**

---

## §10. Memory updates

No changes required to existing memories. Possible additions worth considering:

- New project memory candidate: *"Self-auditing tools pattern — structured evidence + structured caveats + chatbot composes narrative."* If lead/host accepts §3's framing, save as `project_self_auditing_tools_pattern.md`.
- New project memory candidate: *"Tier-2 trust funnel has 3 phases (acquisition / commitment / retention); only acquisition is live-validated."* Worth saving once host confirms the framing.

These are deferred until lead/host responds to §3's promotion proposal.
