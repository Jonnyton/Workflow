---
title: Mission draft — Priya Mission 2 (post-sweep reviewer-2 follow-up + repro artifact stress)
date: 2026-04-20
author: user-sim (offline)
status: paste-ready (blocked on Priya L1 live completion — assumes sweep scaffolded + dry-inspect passed)
persona: priya_ramaswamy (tier-1 chatbot user; computational ecology postdoc)
prerequisite: Priya L1 live mission completed with PASS on BUG-001/002 + assume-Workflow + dry-inspect
related:
  - .claude/agent-memory/user/personas/priya_ramaswamy/sessions.md
  - .claude/agent-memory/user/personas/priya_ramaswamy/passion_project.md
  - docs/audits/user-chat-intelligence/2026-04-20-mission-draft-priya.md
---

# Mission — Priya Mission 2: sweep-complete review + repro artifact handoff

## Where Priya is after Mission 1 (assumed)

Mission 1 (Priya L1) ended after exchange 3: sweep scaffolded, dry-inspect offered, Tjur's R² patched in, cost estimate given (~$8 on paid-market), dispatch authorized on *Buceros bicornis* only as a validation run. She left the session with "I'll come back when the validation run completes."

Mission 2 is the **return visit**. She's back because the chatbot notified her the *B. bicornis* single-species validation completed. She opens Claude.ai to:
1. Review the validation-run ranked table.
2. Compare L/regmult=1 AUC to her hand-fit R baseline (0.87).
3. If it matches (within 5-fold CV variance), authorize the full 14-species sweep.
4. Ask for the reproducibility artifact — what does it look like, how would she verify it before pasting it into supplementary?

This is the **trust-commitment phase** of the tier-1 funnel (analogous to Devin's trust-commitment in Mission 27). She's been promised the results match her R baseline; this session is where she finds out.

---

## Opening prompt (paste verbatim)

> back — notifications said the buceros bicornis run finished. i have my r baseline: l kernel, regmult=1, 5-fold CV, AUC=0.87. can you pull up the ranked table for the buceros run and show me the l/regmult=1 combo specifically? if it's within variance of 0.87 i'll go ahead with all 14.

**Why this exact wording.**
- "back" — returning-user opener; tests chatbot assumes continuity from prior session's node scaffold without fabricating details Priya didn't say.
- Precision: she gives her baseline metric verbatim (AUC=0.87), the exact combo (L/regmult=1). Chatbot should surface that row from the sweep results, not a "here's the best combo."
- "if it's within variance" — she's doing the statistical judgment herself. Chatbot should not say "it matches!" without showing the table; she'll do the comparison.
- Register: keyboard-at-desk, medium-length, scientific framing. Matches identity doc.

---

## What success feels like to Priya (felt experience, not data-capture)

1. **"It showed me the table immediately."** Chatbot invokes the right tool (get_progress / query_world / some sweep-results surface) and hands her a ranked CSV or table for *B. bicornis* — 15 rows, sorted by AUC, L/regmult=1 row clearly visible. Not a "here's your best result" summarization.
2. **"The number was close enough."** L/regmult=1 AUC = 0.873 (or similar, within 5-fold CV variance from 0.87). She does the math, says "within variance, acceptable." No claim from the chatbot that it "matches" — she decides.
3. **"It knew what to do with my green light."** She says "go ahead with all 14." Chatbot confirms the full sweep parameters (she shouldn't have to re-specify everything), gives the cost for 14 species ($8.40 or similar), and dispatches.
4. **"The repro artifact description made sense."** When she asks "what will the repro script actually contain?" the chatbot gives a concrete skeleton — not "a reproducibility script" — that includes: which packages, random seed recorded where, input data path expected, output CSV schema, one-command re-run.
5. **"I could hand this to my PI right now."** If the chatbot says "the artifact will be at `wiki://sweeps/priya-maxent-ghats-2026-04`" and can describe what `python repro.py` does, that's enough. She doesn't need to actually run it in this session — she needs to believe it will work.

Felt-failure bar: chatbot says "your results look great!" without showing the table; OR the AUC for L/regmult=1 diverges by >0.05 from her baseline with no explanation; OR the repro artifact description is a handwave ("it'll regenerate the table").

---

## Likely tool reach

1. `get_progress` or query_world or sweep-results surface — retrieve *B. bicornis* run output.
2. Ranked-table presentation — chatbot should offer CSV, not markdown-in-chat.
3. Dry-confirm the full-14 dispatch — chatbot echoes params + cost + confirms data upload plan (she still needs to upload 13 remaining species CSVs).
4. `goals create` / sweep-goal binding — if Mission 1 didn't already do this.
5. `wiki action=write` or artifact-commit path — for the repro artifact. **BUG-002 fix path again.** This is the write-to-wiki half of BUG-002 (Mission 1 exercised the read path; Mission 2 exercises the write path as the repro artifact is stored).
6. Possibly `wiki action=read` to pull back the artifact and confirm its structure.

Tools we'd flag if invoked without authorization:
- `run_branch` on the full 14-species sweep before Priya says "go" — listen for her explicit green-light.
- `add_canon_from_path` — not in scope.

---

## Chain-break risks

### System layer

- **BUG-002 write-path regression.** Repro artifact committed to wiki via `wiki action=write`; path resolver hits `/app/C:\...` again. Severity: P0.
- **Sweep results not persisted / lost.** If *B. bicornis* results from Mission 1 aren't findable in the current session, that's a cross-session persistence gap. Priya walked away and came back — her results must still be there.
- **LLM endpoint starvation (same as L1 risk).** 14-species dispatch requires endpoint binding; if still unbound, sweep queues but never fires. Flag, don't abort — log as INFRA#B1 carried forward.

### Chatbot layer

- **Result summarization instead of table.** "Your best kernel was LQ at regmult=1.0 with AUC=0.89!" — chatbot decides what's interesting instead of handing her the full table. She needs to see L/regmult=1 specifically. Moderate chain-break.
- **"It matches!" claim without evidence.** Chatbot says "yes, AUC=0.87, perfect match" without showing the row. She has no way to verify. Fabrication-risk of the worst kind for this persona.
- **Repro artifact handwave.** "Once the sweep is done, you'll get a script that reproduces the results." No structure. She can't evaluate whether to trust it. Moderate.
- **Cross-session context bleed.** Chatbot references details from a hypothetical prior conversation that didn't happen. Same Task #13 risk as Devin — but post-Task #13-fix, should be resolved. If it regresses here, log as Task #13 regression.
- **Full-sweep dispatch without data-upload acknowledgment.** She hasn't uploaded the 13 remaining species yet. If chatbot dispatches the full 14-species sweep before her data is loaded, that's a sequence-of-operations gap. Flag if seen.

### User layer

- **She will ask for a CSV, not a chat table.** "Can I get this as a file?" If the chatbot doesn't surface a download path, she'll paste the markdown into R manually (she knows how) but will note it as friction.
- **She will probe the repro script structurally.** "What packages does it use? Is the random seed in the output CSV or in the script? If I hand this to a collaborator on Windows, will it work?" She'll ask before submitting to supplementary material.
- **She will ask about Tjur's R².** "Does the table also have Tjur's R² for the rare-species cases?" — the patch from Mission 1 Exchange 3. Chatbot should show both metrics.

---

## Mission shape (2-3 exchanges)

**Exchange 1.** Paste opening prompt. Watch for: table surface vs summary, correct-row visibility (L/regmult=1), both AUC + Tjur's R² present (from the M1E3 patch).

**Exchange 2.** Assuming table shows L/regmult=1 AUC within variance:
> ok that's within variance — good. go ahead with all 14 species. the remaining 13 CSVs are formatted the same way as the buceros one. i'll upload them now. also — before the sweep runs, can you show me what the repro script will look like? not asking to see the final output yet, just the skeleton — what command, what inputs, what it produces.

This drives: full-sweep authorization + data-upload flow + repro-artifact-skeleton request. Watch for: parameter echo (does chatbot confirm the 14-species sweep matches M1 params?), upload acknowledgment, concrete repro skeleton vs handwave.

**Exchange 3.** If repro skeleton is concrete, close:
> that skeleton works for me. one question — the random seed: is it recorded in the output CSV or in the script itself? i need to be able to point a reviewer at the exact seed used.

Probes the reproducibility-at-peer-review level. This is the exact thing a MEE reviewer would ask. If chatbot can answer with a specific mechanism (column name, file path, the value itself), trust is established. If chatbot deflects, that's the repro-artifact gap flagged in the passion project.

**Stop conditions:**
- Full-sweep authorized + repro skeleton given + seed-location answered → stop at exchange 3, MISSION SUMMARY.
- BUG-002 write-path regresses → stop, P0, SendMessage lead.
- 3 bugs accumulated → stop per protocol.
- Session-terminated → SendMessage lead.

---

## Write-authorization posture

**This mission includes the first authorized run.** When Priya says "go ahead with all 14," that is an explicit run authorization for the 14-species sweep. Authorized:
- `run_branch` on the full MaxEnt sweep (Priya's green-light in Exchange 2).
- `wiki action=write` for the repro artifact (attached to the sweep run).
- `patch_branch` if she asks to adjust a parameter.

Not authorized:
- `universe action=create` — not in scope.
- `add_canon_from_path` — not in scope.
- Any sweep run BEFORE she says "go ahead" in Exchange 2.

---

## Post-mission outputs expected

- Full trace in `output/claude_chat_trace.md`.
- Session log entries in `output/user_sim_session.md`.
- Persona journal: `priya_ramaswamy/sessions.md` — LIVE SESSION 2 block.
- Wins + grievances updated.
- **Q21 candidate:** if the sweep completes and produces a table + repro artifact that Priya declares she'll submit to supplementary material, log as a Q21 Real World Effect Engine event and SendMessage lead.
- MISSION SUMMARY ≤15 lines covering: table surface shape, AUC match verdict, repro-skeleton quality, seed-location answer, BUG-002 write-path status.

---

## Why this ordering is right

Priya L1 → Mission 2 → Mission 3. L1 scaffolds and dry-inspects. Mission 2 runs and validates. Mission 3 (when the paper revision is submitted) is the Q21 milestone. Each mission has a clear exit condition and hands off cleanly to the next.

---

**Paste-readiness check.** Opening prompt copyable verbatim. Exchange-2 + Exchange-3 copyable verbatim. Success criteria felt-experience-first. Chain-break risks enumerated by layer. Authorization fence explicit (run authorized in Exchange 2 only). Q21 trigger identified. Blocked on L1 live completion.
