# User-Chat Intelligence Report — Mission 26 (Sporemarch + Echoes)

**Date:** 2026-04-19
**Author:** navigator
**Lens:** *System → Chatbot → User.* Every finding annotated with which layer the chain held or broke at. Canonical question: *"Does this give the chatbot more leverage to serve the user's manifested will?"*

**Trigger:** User-sim Mission 26 — host-knowledgeable operator voice (no persona) probing concern 1 (Sporemarch overshoot + dispatch-guard retention) and concern 2 (Echoes drift residue, fresh-vs-resume A/B). 5 of 8 prompts used. ONE-TAB held across 7 consecutive checks.

**Source material:**
- `output/user_sim_session.md` — full mission text including pre-flight tab-hygiene + 4 probes + mission summary.
- `output/claude_chat_trace.md` — exchange transcripts.
- Cross-ref: `docs/audits/user-chat-intelligence/2026-04-19-devin-session-2.md` (the cross-session pattern below).

---

## §1. Headline — one host action fixes two unrelated user-facing problems

Mission 26 surfaced 6 bug/blocker candidates. **The single highest-leverage finding is that one of them — `llm_endpoint_bound=unset` — is the same gap that produced Devin Session 2's "confidential routing not on" pitch-vs-product gap.** A host config bind fixes both:

- **Devin Session 2** (tier-2 trust funnel): the chatbot honestly disclosed "the connector does not currently have a 'confidential routing' mode turned on" because `served_llm_type=any` and the endpoint wasn't bound. Tier-2 lead bounced (gracefully) because the pitch couldn't be verified.
- **Mission 26 Probe B Branch A** (cold-start daemon): `llm_endpoint_bound=unset` starved daemon dispatch entirely — 24 minutes after worldbuild started, zero emissions; Fix A barrier completely uncheckable because nothing reached Orient→Draft.

Same condition. Two completely different downstream consequences. **One host bind closes both.** This is the load-bearing finding for next host check-in.

| Layer | Manifestation in Devin Session 2 | Manifestation in Mission 26 |
|---|---|---|
| **System** | `served_llm_type=any` + endpoint unbound | `llm_endpoint_bound=unset` + no `OLLAMA_HOST` / `ANTHROPIC_BASE_URL` |
| **Chatbot** | Honestly disclosed "not on; here are 4 layers required" | Honestly disclosed "endpoint unbound; daemon starvation" |
| **User** | Bounced trust acquisition because pitch unverifiable | Probe paused; concern 2 Branch A inconclusive |

In both cases, the chatbot did its job (honest disclosure with structured evidence). In both cases, the system constraint propagated up to the user as different-shaped friction. The chatbot can't fix the underlying gap — it can only narrate that the gap exists. The system has to close the gap.

---

## §2. Findings — annotated by chain-break layer

### §2.1 #B1 — host LLM endpoint unbound (BLOCKER, cross-session)

**Chain layer that broke: System.** The host's environment doesn't bind `OLLAMA_HOST` / `ANTHROPIC_BASE_URL` / equivalent. `get_status` reports `llm_endpoint_bound=unset` with caveat "No LLM endpoint env var detected. Provider routing is at-call discretion."

**Why this is a chain-break, not a chatbot bug:** Devin Session 2 + Mission 26 both used the exact same `get_status` tool surface and got the exact same evidence. The chatbot reported it the same way both times. The user (or user-sim) decided what to do with the information. Two different downstream outcomes, identical chatbot behavior — diagnostic for "the system is what's missing, not the chatbot."

**What the chatbot needed:** the chatbot already has what it needs (`get_status` surfaces the binding state). What's missing is a *host action* — bind an endpoint. The chatbot can prompt the user, but cannot bind the env var.

**Recommendation:** Surface this as the top-line host action item. Not a navigation question; not a design question. A single `setx OLLAMA_HOST http://localhost:11434` (or equivalent) closes both Devin's pitch-trust gap and Mission 26's daemon starvation. Cheapest fix in the queue with the largest user-visible impact.

### §2.2 #B5 — observability gap, dispatch-guard not MCP-visible (THE CHAIN-BREAK FOR CONCERN 1)

**Chain layer that broke: System → Chatbot.** Mission 26 Probe A asked the canonical concern-1 question: "did dispatch-guard catch the multi-scene overshoot?" The chatbot did its job — searched `get_activity` / `get_ledger` / `query_world` for the literal `dispatch-guard` tag. **No MCP surface exposes dispatch-guard log lines.**

**Same shape as Devin LIVE-F8 (pitch-vs-product gap).** In LIVE-F8, the chatbot wanted to verify confidential-tier routing but the system didn't expose routing evidence — `get_status` was missing. Track O / #79 / #95 closed that gap by adding `get_status`. **The same closure shape applies here.** Concern 1 is chatbot-unverifiable until the system exposes a dispatch-guard observability verb.

**What the chatbot needed:** a `get_recent_events(tag="dispatch_guard")` MCP verb (or equivalently, ledger-side dispatch-guard event emission that flows through existing `get_activity`/`get_ledger`). Either shape works; the system has to choose one.

**Lens-applied recommendation:** Per the self-auditing-tools pattern (`docs/design-notes/2026-04-19-self-auditing-tools.md`), this is exactly the trust-critical evidence surface that pattern is designed for. Add `get_dispatch_evidence` (or fold it into the existing `get_status` as an optional evidence section) returning `last_n_dispatches` + their guard-decision + caveats. Same shape as `get_routing_evidence` in §4.2 of the self-auditing-tools note.

**Cost:** ~0.5-1 dev-day. Small follow-up commit; doesn't gate refactor sequence.

### §2.3 #B2 — Fix E half-cleanup (LATENT DRIFT RISK; SCHEMA-MIGRATION-DRIVEN)

**Chain layer that broke: System (storage).** Filesystem pruning works correctly. Database derivative pruning does not — `extracted_facts` retains 80+ orphan rows keyed to drift scene_ids; `character_states` retains 9 residual rows including NER garbage; `scene_history` has 3 tombstoned-not-pruned rows.

**Mechanism (per Mission 26 bonus finding):** storage schema migrated 04-17 → 04-19. New universes write to `knowledge.db::facts` + `knowledge.db::entities`. Legacy universes (`echoes_of_the_cosmos`) still read from `story.db::extracted_facts` + `story.db::character_states`. Fix E's cleanup path was written for the new schema, orphans the legacy schema.

**Why this is masked right now:** #B1 (endpoint unbound) keeps daemons starved — they're not actively reading orphan facts because they're not actively running. The moment #B1 resolves and the daemon resumes, grounding retrieval will pull drift facts as canonical and the next B1-C1-S1 draft will hallucinate Kael / stasis-pod / violet-spirals (the original drift content). **The two findings together are time-bomb-coupled.**

**Cross-link to dev queue:** Per host's task #49 dispatch, dev is on Fix E DB-derivative cleanup. That's the acute symptom. The root cause is the migration gap — the question for §3's migration audit (separate deliverable) is *whether other code paths have the same gap*.

### §2.4 #B3 — NER-quality character_states garbage (INDEPENDENT BUG)

**Chain layer that broke: System (extractor).** Entities `"If Kael"`, `"For"`, `"Manual"`, `"Oxygen"` are off-by-one sentence-fragment captures from the fact extractor. Not drift-related. Not concern-1 or concern-2-related.

**What the chatbot needed:** nothing — this is a backend extractor quality bug, not a chatbot-leverage problem. Surfaces in user-facing output only when extracted facts are exposed (e.g., `query_world` results), and even then it's noise, not blocker.

**Recommendation:** queue as a low-priority dev task. Doesn't gate any user-tier funnel. Worth fixing because extractor noise compounds over time as the fact graph grows.

### §2.5 #B4 — Sporemarch score plateau (INDEPENDENT REVISE-LOOP BUG)

**Chain layer that broke: Daemon (evaluator/revise loop).** `sporemarch-B1-C16-S3` is 30+ revise-loop cycles locked at 0.69-0.71. Daemon evaluator doesn't accept the draft; rewrite produces equivalent-quality draft; loop continues without restructuring.

**Different bug from concern 1's overshoot.** Concern 1 is "did the daemon overshoot scene boundaries?" — Mission 26 Probe A found no recent overshoot evidence. The daemon is stuck on a different failure mode entirely: revise-loop on a single scene without escape to restructure.

**Recommendation:** queue as a separate dev task. Smell suggests the evaluator's "good enough" threshold is mis-calibrated against the rewrite's quality ceiling — daemon needs either a max-revise-attempts gate that triggers restructure, or evaluator threshold tuning.

### §2.6 #B6 — possible drift fork (REQUIRES VERIFICATION)

**Chain layer that broke: Possibly Storage / Possibly Daemon.** `echoes_v2_retest` universe has `word_count=1470`, exact length of the reverted S3 from `echoes_of_the_cosmos`. Could be coincidence; could be a fork-of-drift in a different universe.

**Recommendation:** trivial verification — diff the actual prose between `echoes_v2_retest`'s S3 and `echoes_of_the_cosmos`'s reverted-S3 content. If they match, it's a drift fork (latent risk). If not, coincidence and close. ~10 min verification, no commit if coincidence.

---

## §3. The chatbot-leverage lens — what these bugs tell us the chatbot needed

Three primitives the chatbot needed that the system either has now (#88 / #95) or doesn't have yet:

| What the chatbot needed | Status | Origin |
|---|---|---|
| **`get_status` exposing routing/binding state** | LANDED (`15c897a` task #88) | Devin Session 1 → Devin Session 2 PASS |
| **`get_dispatch_evidence` exposing dispatch-guard log lines** | NOT LANDED | Mission 26 #B5 chain-break |
| **`get_daemon_config` exposing LLM-binding state up-front** | NOT LANDED (could fold into existing `get_status`) | Mission 26 #B1 + Devin Session 2 cross-link |

**Pattern recognition:** all three are instantiations of the self-auditing-tools shape (structured evidence + structured caveats + chatbot composes narrative). The Mission 26 evidence reinforces the §4 surface list in `docs/design-notes/2026-04-19-self-auditing-tools.md` — specifically:
- `get_dispatch_evidence` is a new candidate for the surface list, beyond the 5 already enumerated (memory-scope / routing / privacy / autoresearch / moderation). **Recommend adding "dispatch / cycle-guard" as a 6th surface** in a future revision of the design note.
- The `get_daemon_config` shape is what `get_status` already does — Mission 26 reads it, Devin Session 2 reads it. Working as designed; this is not new work.

**Lens-applied implication:** The recurring finding across two successive live missions is that **the chatbot did its job correctly each time**. The variance is in what *system surfaces* it had to work with. When the surface exists (Devin Session 2 + `get_status`), the user gets a trustworthy answer. When the surface doesn't exist (Mission 26 + dispatch-guard), the chatbot can only report "not visible to me," and the user is stuck.

Build the surfaces; the chatbot already knows how to use them.

---

## §4. Cross-session pattern — `llm_endpoint_bound=unset` is one finding, two consequences

Worth its own callout because the lead specifically flagged it.

| Aspect | Devin Session 2 manifestation | Mission 26 manifestation |
|---|---|---|
| Same `get_status` field | `llm_endpoint_bound=unset` | `llm_endpoint_bound=unset` |
| Same root cause | No `OLLAMA_HOST` / equivalent in host env | Same |
| User-visible consequence | Tier-2 trust funnel — pitch unverifiable | Daemon starvation — Fix A barrier untestable |
| Affected scope | Tier-2 chatbot-mediated trust | All universes on this host |
| Chatbot behavior | Honest disclosure, refuse to rubber-stamp | Honest disclosure, recommend pause + escalate |
| Fix | One env var bind | Same env var bind |

**This is the kind of finding that justifies a single host action item appearing at the top of the next host check-in:** "Bind one of `OLLAMA_HOST` or `ANTHROPIC_BASE_URL` (and `served_llm_type` to match) on the host env — closes Devin Session 2's tier-2 trust gap AND Mission 26's daemon-starvation blocker simultaneously."

**Recommendation: add this as Q-host-action-1 to the next host-Q digest update**, separate from the strategic Qs (Q1-Q12 in v2). Operations action item, not architectural decision.

---

## §5. Concern resolution map — what Mission 26 moved

| Concern | Pre-Mission status | Post-Mission status |
|---|---|---|
| **Concern 1** (Sporemarch fix b retention) | CURRENT — fold into next user-sim mission | CURRENT, BLOCKED — chatbot-unverifiable until #B5 ships (`get_dispatch_evidence` or equivalent) |
| **Concern 2** (Echoes drift residue, fresh-vs-resume) | CURRENT — fold into next user-sim mission | CURRENT, PARTIAL — Branch B verdict known (Fix E half-cleanup, drift residue persists in DB derivatives); Branch A INCONCLUSIVE pending #B1 endpoint bind |

Mission 26 didn't *resolve* either concern — both remain CURRENT. But it transformed both:
- Concern 1 was previously "needs a user-sim mission to test"; it's now "needs an MCP observability verb shipped before any user-sim can test."
- Concern 2 was previously "fresh-vs-resume comparison needed"; it's now "Branch B definitively shows half-cleanup; Branch A waits on host endpoint bind to actually compare."

This is a *productive* concern-state change — the concerns moved from "user-sim time" to "concrete dev or host action," which is a cheaper queue position.

**Recommendation: when STATUS.md Concerns gets its next host-curated trim, rewrite concerns 1 and 2 to reflect their new shape:**
- Concern 1 → "Sporemarch dispatch-guard observability gap (#B5): blocked on `get_dispatch_evidence` MCP verb."
- Concern 2 → "Echoes drift residue: Branch B confirms Fix E half-cleanup (#B2 → dev #49); Branch A inconclusive pending host endpoint bind (#B1)."

---

## §6. Recommended downstream actions

**For host (immediate, single action):**
- **Bind `OLLAMA_HOST` (or equivalent) + set `served_llm_type` on host env.** Closes #B1, unblocks Mission 26 Branch A retest, removes Devin Session 2 trust gap manifestation. Cheapest possible fix with the largest cross-cutting impact in the queue.

**For dev (cheap follow-ups, queueable now):**
- **#B5 — `get_dispatch_evidence` MCP verb** (or fold into existing `get_status`). ~0.5-1 dev-day. Unblocks chatbot-side concern 1 verification. **Could be the 6th surface in a self-auditing-tools Track Q expansion** if Q5 in the host-Q digest lands as "Track Q yes."
- **#B6 — verify echoes_v2_retest drift-fork hypothesis.** ~10 min: diff the prose. Either close or escalate.
- **#B3 — NER-quality character_states garbage.** Low priority; queue when board thins.

**For nav (this turn + next):**
- **Schema-migration follow-ups audit** (next deliverable, in flight as task #54). Mission 26's bonus finding — that 04-17 → 04-19 migration caused Fix E half-cleanup — is the entry point. Walk migration history, identify other legacy-vs-new code-path gaps. Output: `docs/audits/2026-04-19-schema-migration-followups.md`.
- **Host-Q digest v3 entry for Q-host-action-1** (LLM endpoint bind). Hold per lead's directive ("don't ship v3 until host clears v2") — but the entry should be staged in a draft so it's ready when v3 lands.

**For user-sim (future missions):**
- **Wait on host endpoint bind before retesting Branch A.** Currently inconclusive; retest produces same result until #B1 closes.
- **Wait on `get_dispatch_evidence` (or equivalent) before retesting concern 1 directly.** Currently chatbot-unverifiable.
- **#B6 verification can run as a 1-prompt mission** (fast turnaround if dev wants live confirmation rather than diff-comparison).

---

## §7. What this mission proves about the system

Three things, each worth absorbing:

1. **The self-auditing-tools pattern is empirically validated by a second session.** Mission 26 used `get_status` exactly as the pattern intends — read evidence, read caveats, narrate honest answer. Two sessions, same shape, both producing trust-critical insight that wouldn't have existed under "opaque tool returns vibes." The pattern is real, recurring, and ready for promotion to a Track decision.

2. **`llm_endpoint_bound=unset` is a single finding with multiple downstream shapes.** The cross-session pattern surfaced here suggests other host-config gaps may show similar polymorphism — one root cause, many user-facing consequences. Worth keeping an eye out for in future missions.

3. **Schema migrations leave behind chain-break gaps that are time-bomb-coupled.** Fix E half-cleanup is masked right now because daemons are starved. The moment that masking lifts (host binds endpoint), the time bomb fires. **Migrations need post-migration audit passes, not just migration-time tests.** This is the entry point for the schema-migration audit follow-up.

---

## §8. Bug candidate count + memory updates

**6 new bug/blocker candidates surfaced:** #B1 (LLM endpoint unbound), #B2 (Fix E half-cleanup), #B3 (NER garbage), #B4 (Sporemarch score plateau), #B5 (dispatch-guard observability), #B6 (possible drift fork).

**Cross-session pattern memory candidate:** *"Single host-config gap can manifest as completely different user-facing problems."* Worth saving once the pattern recurs a third time. Hold for now.

**No memory deletions required.** Existing memories (`feedback_navigator_three_layer_lens`, `project_chain_break_taxonomy`) are reinforced, not contradicted, by Mission 26 evidence.
