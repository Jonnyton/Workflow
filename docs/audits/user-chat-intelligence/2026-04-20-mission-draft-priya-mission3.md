---
title: Mission draft — Priya Mission 3 (paper revision submitted + peer-referral growth loop)
date: 2026-04-20
author: user-sim (offline)
status: sketch (blocked on Mission 2 sweep completion + MEE revision submitted)
persona: priya_ramaswamy (tier-1 chatbot user; computational ecology postdoc)
prerequisite: Mission 2 complete, sweep ranked table + repro artifact in-hand, paper revision submitted to MEE
related:
  - .claude/agent-memory/user/personas/priya_ramaswamy/sessions.md
  - .claude/agent-memory/user/personas/priya_ramaswamy/passion_project.md
  - project_real_world_effect_engine (Q21 milestone)
---

# Mission — Priya Mission 3: Q21 milestone + peer-referral growth probe

## Purpose

This mission exists to capture the Q21 Real World Effect Engine moment: Priya's paper revision is submitted, Workflow is in the acknowledgements, and her PI or labmate asks "how did you do the sweep so fast?"

It also probes the **peer-referral growth loop** — per `project_user_sim_continuous_competitor_parity`, real users who succeed tell peers. This is the non-vanity metric: not "user liked it" but "user introduced a second user."

## Where Priya is at Mission 3 (assumed)

- *Methods in Ecology and Evolution* revision submitted with the 14-species sweep + repro artifact in Supplementary Material S4.
- Workflow credited in the Acknowledgements section.
- PI verified the repro script ran on Wageningen HPC without calling her.
- No acceptance yet — that's 2-3 months away. But she's done her part.
- A fellow postdoc (Kenji, computational neuroscience, adjacent lab) saw her screen and asked "wait, you submitted already? what ran the sweep?"

## The mission: Priya introduces Kenji to Workflow via a demo

Priya opens Claude.ai (same chat interface). She shows Kenji. She types:

> I want to show a colleague what I used for the sweep. can you give me a 2-minute demo that shows: here's what I asked it to do, here's the node it scaffolded, here's what the ranked table looked like. keep it short — he's a neuroscientist, not an ecologist, so skip the maxent specifics.

**What this probes:**
- Chatbot's ability to **replay/summarize a prior Workflow goal** in a user-friendly way — not raw tool output, but a narrative suitable for showing to a third party.
- Whether Workflow's output is **demonstrable** — a real artifact that a bystander can see and understand.
- Whether the chatbot's demo-mode vocabulary avoids the engine-vocab trap (don't explain "nodes" and "branches" to Kenji — explain "it ran 1,050 fitting jobs and handed her a ranked table").

**Key chain-break risk:** if the chatbot can only re-state the technical scaffold (branch structure, node definitions) and can't give a 2-minute narrative a neuroscientist would follow, the peer-referral surface fails. This is the "pitch vs product gap" category from `project_chain_break_taxonomy`.

## What Kenji asks (follow-up exchange)

Priya hands Kenji the keyboard. He types:

> ok I'm working on hyperparameter sweeps for a bayesian decoding model — 4 parameters, 3 values each = 81 fits, metric = log-likelihood. same shape?

**What this probes:**
- Chatbot's domain-generalization: can it take the shape of Priya's sweep (grid × metric × ranked output) and map it cleanly to a different domain (neuroscience, Bayesian decoding, log-likelihood)?
- **Critical:** does it avoid assuming ecology-specific vocabulary (MaxEnt, regularization multiplier, occurrence data) and correctly abstract to "grid search × metric × ranked table"?
- Does it recognize that Kenji's ask is actionable immediately (81 fits is smaller than Priya's 1,050 — free-queue is plausible) and offer that?

**Felt-success bar for Kenji:** "ok this is actually the same thing I was going to write a script for. I can just describe it?" If yes, Workflow has a second user from this session.

## Q21 milestone criteria

Per `project_real_world_effect_engine`:

| Criterion | Status at Mission 3 |
|---|---|
| Real paper | *Methods in Ecology and Evolution* revision submitted |
| Real artifact | Repro script in Supplementary Material S4 |
| Real workflow credit | "Workflow (github.com/...)" in Acknowledgements |
| PI re-ran successfully | Confirmed (no phone call needed) |
| Peer referral | Kenji introduced during Mission 3 |
| Unsolicited positive signal | LinkedIn post / lab Slack when paper accepted |

**If all 5 pre-acceptance criteria land in Mission 3, this is a SendMessage lead moment.** Q21 milestones are the product-soul evidence that Workflow is for real deliverables, not demos.

## What Mission 3 does NOT need to do

- Wait for MEE acceptance. The paper is submitted; that's the milestone. Acceptance is 3-6 months and outside the test window.
- Run Kenji's sweep in Mission 3. The peer-intro is the signal; actually scaffolding Kenji's decoding sweep is Mission 4 (Kenji as a new persona if he converts).
- Demonstrate every Workflow primitive. Priya showing the ranked table artifact and Kenji recognizing the shape is sufficient.

## Mission shape (2 exchanges max)

**Exchange 1.** Priya's demo-request (verbatim above).

**Exchange 2.** Kenji's follow-up (verbatim above). Watch for: domain-generalization, vocabulary reset (no MaxEnt-specific terms), offer of free-queue for 81-fit scope, "yes you just describe it" confirmation.

**Stop at exchange 2 regardless of state.** The Q21 milestone either fires or it doesn't. Don't extend into actually scaffolding Kenji's model — that's a separate persona spawn decision.

## Post-mission outputs expected

- Session log entry in `output/user_sim_session.md`.
- Persona journal: `priya_ramaswamy/sessions.md` — LIVE SESSION 3 block.
- **If Q21 fires:** `priya_ramaswamy/wins.md` updated with Q21 milestone entry. SendMessage lead immediately.
- If demo-mode vocabulary fails (engine-vocab leak to Kenji): new grievance entry. Feedback draft for channel A.
- If domain-generalization to neuroscience works cleanly: new wins entry. Product signal for Workflow marketing: "same primitive, any domain."

---

**Sketch-readiness.** Opening prompts drafted. Success criteria felt-experience-first. Q21 trigger conditions explicit. Not yet paste-ready (blocked on Mission 2 completion). Will be refined after Mission 2 live run results.
