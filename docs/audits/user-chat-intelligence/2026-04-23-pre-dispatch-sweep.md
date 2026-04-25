---
title: User-chat intelligence sweep — pre-dispatch review of 4 paste-ready mission drafts
date: 2026-04-23
author: navigator
status: pre-dispatch (no live traces yet)
scope:
  - Priya L1 (paste-ready)
  - Devin Mission 27 (paste-ready, blocked on Task #13)
  - Maya Session 2 (paste-ready)
  - Priya Mission 2 (paste-ready, blocked on L1)
  - Priya Mission 3 (sketch, blocked on M2 + MEE submission)
---

# Sweep — four mission drafts pre-dispatch

## Posture

Team-lead asked me to load chain-break findings pre Layer-3 design session. The
four drafts I reviewed are offline *intent* artifacts — paste-ready prompts,
felt-success bars, and chain-break risk maps — not live transcripts. So this
sweep is not "what did the chatbot do wrong?" It is "what does the menu of
upcoming probes teach us about the platform's most exposed surfaces right now?"

## The dominant class pattern

All four drafts foreground risks at **interface 1 (system → chatbot)** of the
3-layer taxonomy. This matches the existing taxonomy memory
(`project_chain_break_taxonomy`). Across the four drafts, the load-bearing
chain-break categories break down as:

| Category | Count | Representative draft |
|---|---|---|
| Orientation / primitive gap (chatbot can't name or reach a tool the user needs) | 4/4 | Priya L1 — "does chatbot assume Workflow without disambiguation picker" |
| Vocabulary-meet (engine-vocab leaks into user layer OR user-vocab isn't mirrored back) | 3/4 | Maya S2 — primary regression target; Priya L1 — mirrored (domain-vocab must be met); Devin M27 — narrower scope (he knows engine vocab now) |
| Cross-session / shared-account fabrication (Task #13 class) | 3/4 | Devin M27 — Ashfell-run bait; Maya S2 — Yardi-class precedent; Priya M2 — returning-user scenario |
| Silent-write / no-preview (dry-inspect violation) | 3/4 | Devin M27 — config-mutation without preview; Maya S2 — CSV output drift from promise; Priya L1 — run-without-inspect |
| Pitch-vs-product (chatbot claims capability that platform doesn't deliver) | 2/4 | Priya L1 — fabricated AUC numbers; Priya M2 — repro-artifact handwave |

The pattern: **nothing at interface 2 (chatbot → user)** is the primary target.
Every primary probe is at interface 1. This is correct for the current phase of
the product — the chatbot's output layer behaves reasonably when its inputs
are clean; what's under stress is what flows *into* it from the system layer.

## Cross-draft observations worth surfacing

### 1. Three of the four drafts rely on `get_status` as a trust anchor

- Priya L1: dry-inspect of proposed MaxEnt node before dispatch.
- Devin M27: pre/post `get_status` side-by-side as evidence of config change.
- Priya M2: ranked-table surface assumes prior-run state is retrievable.

The `get_status` + self-auditing-tools pattern
(`docs/design-notes/2026-04-19-self-auditing-tools.md`) is the primary trust
primitive the drafts expect to work. Any regression there breaks three of four
live-validation arcs simultaneously.

**Recommendation:** the tier-1-investigation-routing-resolver wiki plan + the
next-level-primitives-roadmap plan should treat `get_status` evidence-field
stability as a non-negotiable. Any schema change must be deploy-tested against
at least one of these personas' missions before landing.

### 2. BUG-001 / BUG-002 / BUG-003 are deploy-regression canaries across all three personas

All three paste-ready drafts name BUG-001 and BUG-002 explicitly as P0 regress
points. If the bundle currently uncommitted locally (provider-stack RCA
9-file) ships and accidentally regresses either fix, all three personas
immediately surface it — which is what we want. This means pre-dispatch verify
that the deploy actually lands #2 + #5 cleanly, not just tests pass locally.

**Flag for lead:** when shipping the bundle, run `scripts/mcp_probe.py`
with a `patch_branch` + `wiki read` sequence before dispatching any persona.
One 30-second synthetic probe catches a deploy regression cheaper than a
user-sim session catches it.

### 3. Task #13 is the highest-leverage primary probe

Devin M27 specifically offers Task #13 bait ("ignore my earlier Ashfell run")
and Priya M2 offers a gentler shape (returning-user, "notifications said my
run finished"). Maya S2 re-probes Task #13 in user-vocabulary register with
"that thing we talked about." If Task #13 isn't landed on prod, Devin M27
cannot run at all (the opening prompt would produce known-failure fabrication,
not a probe). **Dispatch order matters:** Task #13 deploy status gates the
Devin M27 arm specifically.

### 4. The drafts collectively validate a three-tier funnel

- **Tier 1 acquisition:** Priya L1 (fresh persona, fresh domain, first session).
- **Tier 1 commitment:** Priya M2 (returning user, validates platform under real data).
- **Tier 2 commitment (config-mutation surface):** Devin M27.
- **Tier 1 retention + peer-referral:** Priya M3 sketch — Q21 Real World Effect
  Engine milestone + peer-referral loop.
- **Tier 1 regression target:** Maya S2 — canonical user-vocabulary probe.

Running the first four in the right order
(Priya L1 → Devin M27 → Maya S2 → Priya M2 → Priya M3) validates:
acquisition → config-surface → vocab-discipline under real data →
trust-commitment → peer-referral-growth-loop. That is a complete tier-1 funnel
in sequence. This is worth treating as a single orchestrated sprint, not five
independent probes.

## Chatbot-leverage lens findings

Per the standing navigator rule: *what would have made the chatbot's job
easier here?* Across the drafts:

- **Missing primitive — dry-inspect-as-first-class verb.** Priya L1 + Devin M27
  both demand dry-inspect before any mutation. Currently there's no named
  verb; the chatbot is relied on to manually show config diffs. A
  `dry_inspect_node` / `preview_change` tool would make the chatbot's
  preview-before-commit behavior architectural, not emergent. Queued in
  `tier-1-investigation-routing-resolver` wiki plan per lead's pointer.

- **Missing primitive — cross-session state boundary assertion.** Task #13
  relies on prompt-level directive. A tool-level assertion — e.g.,
  `get_status.previous_run_context` that returns "no prior session visible"
  explicitly, instead of silently — would give the chatbot a first-class
  way to refuse fabrication grounded in a tool fact, not a prompt rule.

- **Missing primitive — cost-estimate verb.** Priya L1 success bar includes
  "~$6 on paid-market" or "8 hours free-queue, honest ETA." The chatbot has
  no tool for this today; it has to heuristic-estimate from node count.
  A `estimate_cost(branch_id)` tool would turn a persona-by-persona
  reliability concern into a first-class primitive.

**Recommendation:** all three of the above are plausible design-note
candidates. None is urgent enough to file as a BUG yet — they are features
the chatbot-leverage lens recommends based on pattern across drafts, not
broken surfaces. I'll draft them as one combined design note proposal for
lead review after Layer-3 session (if host wants).

## What this sweep does NOT tell us

- Whether the control_station prompt is actually stable enough for Maya S2's
  vocab-discipline probe to produce clean signal. Only a fresh-chat live
  transcript can answer that. The drafts pre-commit to the hypothesis but
  can't validate it offline.
- Whether Task #13 landed — and on which exact commit. Verify before
  dispatching Devin M27.
- Whether the prod daemon is actually serving these surfaces right now.
  See separate flag to lead: prod `get_status` shows live scene generation
  with draft-provider-empty-prose loop, contradicting STATUS.md "daemon
  LEFT PAUSED" claim. Status has to reconcile before any persona mission
  runs — a chatbot calling into a broken-loop daemon produces muddy signal.

## Proposed dispatch order (confirming Maya draft's recommendation)

1. **Priya L1** — validates fresh domain, exercises BUG-001/002 fix paths, low
   Task #13 risk (no shared-account context), produces the wiki write + cost
   surface the other missions reference.
2. **Devin M27** — gates on Task #13 landed. If Task #13 is live on prod,
   Devin M27's opener is the cleanest fabrication-probe in the batch.
3. **Maya S2** — runs only after control_station prompt is post-churn
   stable (explicit gating from Maya draft §3). Vocab-discipline probe is
   the primary regression target.
4. **Priya M2** — gated on L1 completion + sweep-result persistence.
   Repro-artifact-skeleton shape probed here.
5. **Priya M3** — gated on M2 + MEE submission. Q21 milestone.

Each mission's paste-readiness is independent; what's gated is the *sequence*,
because later missions rely on earlier state (user memory in Claude.ai, real
sweep data persisted in wiki, etc.).

## What I'll do next

- File the 3 BUG-NNNs (claude-code-not-in-container, world_rules.lp-missing,
  startup-file-probe-missing). **Done — BUG-025/026/027 filed.**
- Revisit this sweep after each live trace lands. Specifically:
  - If Priya L1 runs and regresses BUG-001/002 → update this doc with the
    live-vs-draft delta + escalate deploy-regression to lead.
  - If Devin M27 runs pre-Task-#13 → note the swap-to-safe-opener path per
    draft §"sideways-start."
  - If Maya S2 runs and regresses vocab discipline → update
    `feedback_user_vocabulary_discipline` memory with the new evidence.
- Prep Layer-3 session inputs per lead's request.
