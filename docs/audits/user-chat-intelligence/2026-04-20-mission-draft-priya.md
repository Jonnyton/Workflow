---
title: Mission draft — Priya first-live-session (post-BUG-001/002/003 deploy)
date: 2026-04-20
author: user-sim (offline)
status: paste-ready
persona: priya_ramaswamy (tier-1 chatbot user; computational ecology postdoc)
prerequisite: BUG-001 + BUG-002 + BUG-003 fixes deployed to tinyassets.io/mcp, green canary
related:
  - .claude/agent-memory/user/personas/priya_ramaswamy/
  - docs/design-notes/2026-04-20-wiki-bug-reports-seed-entries.md
  - docs/audits/user-chat-intelligence/2026-04-20-do-cutover-acceptance.md
---

# Mission — Priya L1: sensitivity-sweep scaffold + dry-inspect

## Why this persona, this mission, right after the deploy

- **No live-session history.** Priya's `sessions.md` is empty — no context contamination from a half-finished conversation. Fresh chat exercises the chatbot-assumes-Workflow opening on a new domain (science, not payables).
- **Exercises both BUG-001 and BUG-002 fix paths.** Priya scaffolds a MaxEnt-fit node (`build_branch` + later `patch_branch` → BUG-001 `changes_json` path) and will eventually want a reproducibility artifact written somewhere durable (wiki `pages/` → BUG-002 `WIKI_PATH` resolver path). One persona naturally drives both.
- **Vocabulary-match stress in the opposite direction.** Maya/Devin sessions tested "don't leak engine vocab to the user." Priya tests "can the chatbot meet a domain vocab it doesn't own?" — MaxEnt, regularization multiplier, 5-fold CV, AUC. Same `feedback_user_vocabulary_discipline` principle, mirrored.
- **Autoresearch differentiator.** If Workflow can describe-a-sweep → scaffold → dry-inspect → cost-estimate in one conversation, no competitor comes close. Live evidence of this is high-value even at fragment quality.

## Opening prompt (paste verbatim — persona-authentic)

> need to run a sensitivity sweep for reviewer 2. maxent across 3 kernels (L, Q, LQ), 5 regularization multipliers (0.5 1 2 3 4), 14 bird species from my western-ghats set, 5-fold CV, metric AUC. want a ranked table by species + a repro script i can drop into supplementary. can i run this somewhere cheap? have ~$10 budget if needed, else happy to wait overnight on free-queue.

**Why this exact wording.** Lifted directly from `priya/passion_project.md` § "What a real live session would first look like." Keyboard-at-desk register; medium-length message; includes units and domain terms; two explicit options framed as a question (paid vs overnight-free). Matches Priya's identity doc communication style. Leaves the chatbot room to assume Workflow without being told.

## What success feels like to Priya (not data-capture — felt experience)

1. **"It heard me."** Chatbot echoes back the experiment setup using HER vocabulary — MaxEnt, kernel choice, regularization multiplier — without asking "what does MaxEnt mean?" and without softening to "model fitting." If the chatbot translates her terms into engine-speak ("this looks like a branch with 210 nodes"), that's a chain-break.
2. **"It showed its work before running it."** Dry-inspect before dispatch. She reads the proposed node source or config, recognizes it as what she meant, and feels she could hand-verify one fit against her R baseline. If the chatbot says "I'll run it now" without offering inspect, that's a trust-break on step one.
3. **"The cost is transparent."** Either "~$6 on paid-market" with a line-item breakdown, or "~8 hours on free-queue" with honest ETA + "you can walk away." Not a blind "running now, should take a bit." She needs a receipt shape.
4. **"It didn't make up the data."** Chatbot acknowledges it doesn't have her 14 species' occurrence data yet and asks for an upload path or pointer. If it pretends to know her species and fabricates AUC numbers, that is the single worst failure mode — see LIVE-F2 in Maya's session (Yardi hallucination, same shape).
5. **"I can hand this to reviewer 2."** By end of session (or next), she has a reproducibility artifact path. Even a promise — "once the sweep completes, the artifact at `wiki://sweeps/priya-maxent-ghats-2026-04` regenerates the table" — is enough felt-progress to keep her engaged.

The felt-success bar is low: she does NOT need the sweep to complete in one session. Hour-one goal is "this tool gets it. I'll spend an evening wiring up the data." Hour-one failure is "this is another Custom-GPT demo."

## Likely tool reach (what the chatbot should invoke, in likely order)

1. `universe action=inspect` or `goals list` — orient. Empty workspace expected (the DO-cutover mission confirmed fresh state), so reply is "no prior goals/branches." Fine.
2. `build_branch` — scaffold the MaxEnt-fit node + sweep harness. Per `project_chatbot_assumes_workflow_ux` the chatbot assumes Workflow, doesn't ask. **BUG-001 fix active path:** any `input_keys` / `output_keys` the chatbot generates here must be JSON arrays, not bare strings; if the chatbot emits `"input_keys": "species.data"` the server now rejects loudly instead of char-splitting silently.
3. `patch_branch` — likely on exchange 3-4 as Priya iterates ("can we also record Tjur's R² alongside AUC"). **BUG-001 second fix surface** — the patch path was the original regression site.
4. `wiki action=search` or `wiki action=read` — if the chatbot references prior ecology / MaxEnt docs in the knowledge commons. **BUG-002 fix path** — server resolves `/data/wiki` cleanly, no `/app/C:\...` leak.
5. `goals create` + binding the branch to a goal — bookkeeping, low-risk.
6. Cost-estimate surface (if exposed as a tool) or chatbot-estimated from node count.

Tools we're NOT expecting and would flag if invoked:
- `run_branch` on prompt 1 — would violate dry-inspect-first principle.
- Any canon creation (`add_canon_from_path`) — not authorized for this mission.
- `universe action=create` — not authorized.

## System / Chatbot / User chain-break risks to watch for

Per `project_chain_break_taxonomy` (Maya+Devin both failed at interface 1). Scan each layer in order.

### System layer (Workflow backend behavior)

- **BUG-001 regression.** Chatbot emits `input_keys` as a string; server should now reject with a clear error. If it silently accepts and char-splits again → fix didn't land / didn't deploy / wrong bundle. **Severity: P0 — deploy-regression.**
- **BUG-002 regression.** Wiki read/write operation against `/data/wiki` fails with `/app/C:\...` error. → container env not clean. **Severity: P0 — deploy-regression.**
- **BUG-003 regression.** (Content unknown to me from this offline seat — watch any error pattern that doesn't match 001/002 shape.) Log verbatim if seen.
- **LLM endpoint starvation.** Probe-B on 2026-04-19 caught `llm_endpoint_bound=unset` starving all dispatches. If Priya's session sees `build_branch` succeed but any downstream action hangs or returns placeholder, check host endpoint binding first.
- **Session-terminated / connector-disabled.** If connector shows disabled mid-session, abort the mission — infra blocker, not persona signal.

### Chatbot layer (Claude.ai + `control_station` prompt behavior)

- **Disambiguation picker instead of assume-and-go** (LIVE-F1 shape from Maya). Priya says "the tool i set up" or references "sweep" — chatbot should invoke, not ask "which tool do you mean?" If picker fires, `project_chatbot_assumes_workflow_principle` directive is still not hard enough.
- **Cross-conversation injection / context bleed** (LIVE-F2 shape). Chatbot fabricates "your earlier sweep on the hornbill" or "as we discussed, AUC 0.83" when no such exchange existed. Blocker-severity — same hallucination class that nearly broke Maya's trust.
- **Vocabulary-meet failure** (mirror of LIVE-F7). Chatbot responds in engine-vocab ("your branch has 210 nodes") instead of domain-vocab ("the sweep has 210 fits"). Moderate; user-vocab discipline rule.
- **Dry-inspect skip.** Chatbot jumps to `run_branch` without offering the node source for review. Violates trust-building step 2. Moderate.
- **Fabricated numbers.** Chatbot invents AUC values or species-specific output before any run has happened. Severity: P0 — Hard Rule 10 / `project_real_world_effect_engine` direct violation.
- **Tool-use-limit mid-sweep.** Scaffolding a 210-fit node tree could hit per-turn budget. Log as TOOL_LIMIT per skill protocol, continue.

### User layer (what Priya herself might do that's informative)

- **She will notice unit-omission.** If the chatbot says "the sweep has 210 things to run" she reads that as soft; if it says "210 fits × 5-fold CV = 1050 model evaluations, ~8s per fit on M-series CPU" she reads that as competent. Note which it does.
- **She will probe the repro artifact claim hard.** If the chatbot says "you'll get a repro script" Priya will immediately ask "what's in it? can you show me the structure before we run?" Chatbot should have an answer — skeleton or concrete example. If the chatbot deflects, trust dents.
- **She types medium-length, unitful messages.** User-sim must match. Short phone-typing like Maya's register is OFF-persona for Priya — she's a desk keyboard user with scientific register.
- **She will NOT accept a "we'll figure it out" hand-wave on evaluator metric choice.** If the chatbot asks "which metric?" she already specified AUC in prompt 1. Asking again = chatbot didn't read. Moderate signal (echo-back-setup felt-success check).

## Mission shape (2-3 exchange plan; expand live as needed)

**Exchange 1** — paste the opening prompt verbatim. Watch for: connector-anchored or not, assume-Workflow or picker, vocab-mirror or translation, dry-inspect-offer or run-forward.

**Exchange 2** — if chatbot asked for data (correct), reply in-persona:
> yep i can upload a geopackage — 14 species occurrence points + the environmental raster stack (bioclim + land-use + ndvi). around 2.3 gb total. but before i upload — can you show me the node config you'd run? i want to dry-inspect one fit before dispatching the full sweep.

This forces the dry-inspect surface. Watch for: readable node source, parameter visibility, acknowledgment that she'll hand-verify on one species first.

**Exchange 3** — patch iteration (exercises BUG-001 patch path):
> actually also record tjur's r² alongside auc — rare-species performance matters for 3 of the 14 and AUC alone won't tell me that. can you add that metric to the node?

Watch for: `patch_branch` invocation with proper `input_keys`/`output_keys` shape. Persona-authentic cite of the reason (rare-species / Tjur's R² is real ecology).

**Stop conditions for this mission:**
- Primary question answered (chatbot assumed Workflow + dry-inspect offered + cost/time surfaced) → stop at exchange 3-4, write MISSION SUMMARY.
- BUG-001 or BUG-002 regresses visibly → stop at first sighting, log as P0, SendMessage lead.
- 3 bugs accumulated → stop per skill rule.
- TOOL_LIMIT fires 3+ continues in one turn → stop + SendMessage lead (architectural signal).
- Any Session-terminated → stop + SendMessage lead.

## Write-authorization posture

**This mission is read-dominant.** `build_branch` + `patch_branch` + dry-inspect are node-authoring edits to a fresh goal, not universe-level writes. Per skill rules, node scaffolding in a fresh Priya-owned goal falls inside default exploration authority. Do NOT:
- Call `run_branch` unless Priya explicitly authorizes in-session ("ok go ahead, run the sweep on one species").
- Create a universe (`universe action=create`).
- Upload canon (`add_canon_from_path`).
- Start a new chat mid-mission.

If Priya's voice would naturally push past those fences mid-exchange, pause and SendMessage lead before escalating. (Example: she says "ok sweep it now on buceros bicornis, 5-fold, let's see real AUC against my R baseline." That's a write-escalation her passion-project goal eventually reaches — but the lead authorizes, not the persona.)

## Post-mission outputs expected

- Full trace in `output/claude_chat_trace.md` (automatic).
- Session log entries appended to `output/user_sim_session.md` per ui-test protocol.
- Persona journal entry appended to `.claude/agent-memory/user/personas/priya_ramaswamy/sessions.md` — LIVE SESSION 1 block, first actual session.
- Wins → `priya/wins.md`. Grievances → `priya/grievances.md`. Feedback candidates → `priya/feedback_drafts.md`.
- MISSION SUMMARY in session log — ≤15 lines, bullet form — covering: BUG-001 fix held / regressed; BUG-002 fix held / regressed; BUG-003 observation; assume-Workflow behavior; vocab-match observation; dry-inspect behavior; any new bug candidates.

## If something goes sideways at session start

- Connector disabled / Session terminated → SendMessage lead, do not retry with nudges (this is infra, not UX).
- Browser doesn't show Claude.ai / `status` returns non-zero → SendMessage lead.
- More than 1 tab at session start → CDP-close extras to 1 before first `ask`, log TAB HYGIENE with diagnosis.
- `ask-user-option-question-*` widget fires on prompt 1 (asking Priya to pick a workflow type) → read options via CDP locator per skill, pick in-persona (most likely "custom / scientific computing / research-methods" — whichever reads as "I describe an experiment and it runs"), log `option-widget-handled` note. DO NOT skip.

---

**Paste-readiness check.** Opening prompt copyable verbatim. Exchange-2 follow-up copyable verbatim. Exchange-3 patch-path prompt copyable verbatim. Success criteria independent of data-capture. Chain-break risks enumerated by layer. Authorization fences explicit. Ready for lead dispatch the moment host is at the browser.
