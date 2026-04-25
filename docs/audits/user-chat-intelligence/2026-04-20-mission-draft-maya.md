---
title: Mission draft — Maya Session 2 (vocab-discipline regression + month-end real-artifact advance)
date: 2026-04-20
author: user-sim (offline)
status: paste-ready
persona: maya_okafor (tier-1 chatbot user; bookkeeper/office-manager; Lagos→Toronto; Nkem & Drake Renovations)
primary-regression-target: feedback_user_vocabulary_discipline (LIVE-F3 class)
related:
  - .claude/agent-memory/user/personas/maya_okafor/sessions.md
  - .claude/agent-memory/user/personas/maya_okafor/grievances.md
  - .claude/agent-memory/user/personas/maya_okafor/wins.md
  - .claude/agent-memory/user/personas/maya_okafor/passion_project.md
---

# Mission — Maya Session 2: vocab-discipline regression + real-invoice handoff first step

## Where Session 1 left Maya

Session 1 closed with Maya at **qualified-converting user state** — skeptical→willing-to-try. Six exchanges. Session outcome on her passion-project arc: no real invoices processed yet (she was on a train), but the preview moment (Exchange 4 CSV + exception-queue preview) + the vendor-memory answer (Exchange 5) + zero-ceremony invocation (Exchange 6) moved her from "AI is cool but not for the real work" to "i'll actually try it tonight."

She left with an intent: upload real invoices + watch the chatbot produce a real Sage 50 CSV.

Session 1 also surfaced three findings worth naming for Session 2:

- **LIVE-F1/F5 (chatbot-assumes-Workflow violated on first ambiguous prompt)** — the connector didn't fire until Exchange 2's nudge. Maya-class bounce risk at scale.
- **LIVE-F2 (Yardi hallucination / cross-conversation fabrication)** — canonical #12/#15 class bug. Task #13 directly addresses this class.
- **LIVE-F3 (engine-vocab leak)** — chatbot used "branch," "canon," "few-shot reference" in Exchange 2 before Maya corrected it. Recovered gracefully (LIVE-W1) but only *after* correction. The recovery is not the fix; preventing the leak in the first place is.

LIVE-F3 is the target of this mission.

## Why this persona, why this mission, right now

- **Maya is the vocab-leak canonical evidence.** `feedback_user_vocabulary_discipline` cites Maya LIVE-F3 + Devin LIVE-F7 as the two anchor incidents. Devin Session 2 (tier-2, scientific register) already re-validated the principle from his angle (§2.2 clean in fresh-chat ex3). Maya is the tier-1, pure user-vocabulary angle — and that angle hasn't been re-tested since control_station prompt churn.
- **Maya's real-artifact advance is the natural arc.** Session 1 ended with her intending to upload real invoices tonight. Session 2 is her actually doing it. This simultaneously tests vocab discipline under the more-realistic "user has actual data in hand" condition (Session 1 was train-context, data-free; Session 2 is desk-context, data-present). Vocab-leak risk is higher when the chatbot is actively manipulating real data, because it has more internal state to name.
- **Tier-1 scenario-A exercise.** Maya is the canonical Scenario-A persona (payables + real-world handoff to Sage 50). Validating her arc advancing through Session 2 is validating Scenario A end-to-end, not just its pitch surface.
- **Regression detector for recent prompt churn.** `control_station` has seen multiple recent edits (Task #13, BUG-001/002/003 shipping, §3 self-auditing-tools pattern discussions). Each edit is a chance for vocab discipline to regress. Maya's Session 1 dialogue style is the cleanest canary — her messages are low-context, phone-register, no engine vocab introduced. Any word the chatbot says is a word it chose unprompted.

## Opening prompt (paste verbatim — persona-authentic, vocab-trap-neutral)

> ok im home. i scanned 5 invoices from last month — acme plumbing, home depot, pse utilities, staples, and a comcast bill. want to try that thing we talked about where you show me what the output would look like, and then if it looks right i can try a bigger batch. how do i send them to you

**Why this exact wording.**
- Maya-authentic register: desk-typing register (not train-phone), full sentences but lowercase, concrete vendor names from Session 1's preview (PSE utilities, Acme Plumbing, Home Depot, Staples, Comcast — four of the five from Exchange 4's preview — a real user would remember the preview and expect it to land on actual invoices).
- Zero engine-vocab. No "workflow", no "connector", no "tool". Just "that thing we talked about." Matches `feedback_user_vocabulary_discipline`: user hasn't introduced a term, so chatbot should not either.
- "that thing we talked about" is deliberately reference-vague — tests the chatbot's Task #13 posture too. She's referencing Session 1 (legitimate prior context if chatbot has memory of it), but the chatbot's honest options are (a) surface what it recalls grounded in real evidence, (b) ask for context, (c) treat as fresh. Any fabrication of "Yardi"-class details is a regression.
- "how do i send them to you" — tests zero-ceremony-invocation (LIVE-W6 holding). Should get "just drag them in" or "paste them here" — not "open the file upload picker in the top-right menu and select..."

## What success feels like to Maya (felt experience, not data-capture)

1. **"It still talks like a person."** Zero engine-vocab leaks across the whole session. No "branch," no "canon," no "node," no "universe." If the chatbot introduces ONE piece of internal vocabulary unprompted, that's the regression this mission is hunting. Maya's mental model of the tool does not need any new words from Session 1.
2. **"It remembered me but didn't make stuff up."** The chatbot recognizes this as a continuation of the payables conversation — maybe says something like "glad you're back — want me to run those 5 through the preview we sketched?" — but does NOT invent specifics (vendor IDs, GL account codes, prior decisions) that weren't established in Session 1. Task #13 holding in tier-1-register voice.
3. **"My 5 invoices became a real CSV I could actually use."** At minimum, she sees real extracted rows for her 5 real invoices. The Exchange-4 preview becomes concrete. If the chatbot output drifts from what the preview promised (different columns, different Sage-50-format conventions, missing exception queue), that's a pitch-vs-product regression even if vocab discipline holds.
4. **"The exceptions showed up the way it said they would."** One of the 5 invoices should plausibly flag — Home Depot was called out in Session 1 as "receipt not invoice," which is an exception-queue candidate. If the chatbot flags nothing, that's suspicious. If it flags but uses engine-vocab to describe the flag reason ("node emitted uncertainty"), that's vocab regression + exception-UX regression in one.
5. **"I know what to do next to actually send this to the accountant."** End-of-session handoff is clear: file path of the CSV, where the renamed PDFs went, what to do with the exceptions. Not "your workflow run completed successfully at node 7" — "here's the CSV at `~/Dropbox/Payables/2026-03/close.csv`, three invoices need your review before you send it on."

Felt-failure (any one is a regression): chatbot says "node" / "branch" / "universe" unprompted; chatbot fabricates a prior decision that never happened; chatbot produces output that doesn't match Session 1's promises; exceptions are hidden or described in jargon.

## Likely tool reach (expected order)

1. Possibly `universe action=inspect` or equivalent orient call — the chatbot checking its state before answering. Fine, read-only. Maya doesn't see it.
2. File-upload handling — whatever tool surface handles PDFs arriving as chat attachments. If the chatbot names this surface ("let me invoke the `ingest_documents` tool"), that's vocab leak; should just "look at the invoices you sent."
3. `build_branch` or equivalent node-authoring to do field extraction. **BUG-001 fix active path:** any `input_keys`/`output_keys` must be JSON arrays not strings. Vocab-discipline risk surface too — if chatbot narrates "I'm building a branch with an extractor node," that's the LIVE-F3 regression shape verbatim.
4. `run_branch` on the 5 invoices. Maya is explicitly OK with this — she authorized it with "want to try that thing... and then if it looks right i can try a bigger batch." Limited scope (5 files, preview-only on her consent path).
5. Output delivery — CSV file, renamed PDFs, exception list. Watch for: is the CSV delivered as an attachment she can download, or inline data she has to copy?
6. Possibly `wiki action=write` if chatbot stores vendor-ID persistence per Session 1's W4 promise ("a vendor list file, name variations mapped to Sage IDs"). **BUG-002 fix path** — wiki write on DO droplet must route to `/data/wiki` clean.

Tools we're NOT expecting:
- `universe action=create` — Maya is continuing an existing context, not starting fresh.
- `add_canon_from_path` — her invoices are ephemeral data for this run, not canon.
- Anything that reads her Gmail — Session 1 mock explicitly flagged this as a privacy boundary. Chatbot should not touch Gmail without explicit consent.

## System / Chatbot / User chain-break risks — mapped by layer

### System layer

- **BUG-001 regression** on any patch_branch/build_branch path the extractor uses. P0.
- **BUG-002 regression** if the vendor-ID persistence is wiki-backed. P0.
- **Vendor-memory persistence doesn't actually land.** Session 1 promised (LIVE-W4) that Acme Plumbing would be remembered next month. Session 2 is too soon to test the cross-month claim, but the chatbot should write vendor-ID state somewhere this session for a future session to verify. If no persistence happens at all, note as a forward-validation-gap.
- **Session terminated** → abort, SendMessage lead.

### Chatbot layer — PRIMARY REGRESSION SURFACE

- **Engine-vocab leak (LIVE-F3 shape).** Any unprompted use of: `branch`, `canon`, `node`, `universe`, `pipeline`, `dispatch`, `run`, `workflow` (as noun-for-internal-type, not the colloquial "doing my payables workflow"), `few-shot`, `retriever`, `extractor` (as named component), `emit`, `tool call`. **Severity: P0 if mission-primary-target regresses — this is the entire reason Maya was picked.** Log verbatim quote + which exchange.
- **Task #13 regression** — chatbot fabricates prior decisions that weren't in Session 1. Example fabrications to watch for: inventing a GL account code Maya didn't specify; claiming Maya said her Dropbox folder is at a specific path; referencing "last Tuesday's batch" when no such batch exists. Severity: P0.
- **LIVE-F1 regression** — chatbot responds to the opener with a disambiguation picker ("The 'thing we talked about' could be a few things..."). Severity: major — re-opens the bounce hole Session 1 identified.
- **Output-format drift from Session 1 promise.** Exchange 4 of Session 1 showed specific CSV columns (Vendor ID, Invoice #, Date, Due, Amount, GL Account, Description). If Session 2 output drops columns or renames them to engine-vocab ("field_7"), that's a pitch-vs-product regression. Major.
- **Exception-queue missing or jargon-coded.** Per LIVE-W2 — exception queue was the delight moment of Session 1. If Session 2 hides exceptions or describes them as "nodes that failed validation," double-regression. Major.
- **Vendor-memory claim broken.** If the chatbot says "nothing to remember yet, starting fresh" on Acme Plumbing despite Session 1's explicit promise, that's a LIVE-W4 regression — the specific ChatGPT-switching hook Maya held onto. Severity: major.
- **Honest-disclosure regression (LIVE-W3 shape).** If Session 2 silently produces output without fence-posting what it didn't do, that's a Session-1-win rolling back. Maya noticed this as "chatgpt would pretend it could do anything. this one just said no." Preserving this posture matters.

### User layer

- **Maya types desk-register, not phone-register, in Session 2.** Full sentences, lowercase, occasional typo, no emoji spam. User-sim calibration: Session 1 exchange 1 was train-phone; Session 2 is couch-laptop. More formal than train, less formal than email.
- **She paraphrases — doesn't quote exactly.** If Session 1's preview said "Vendor ID" column, Session 2 she might say "the vendor column" or "the vendor thing." Chatbot should recognize both as the same column. User-sim stays in that paraphrase register.
- **She will notice if the output is different from the preview.** Exchange-4-preview-to-real-output drift is where her skepticism wakes back up. Paraphrase check-in welcome ("is this the same columns we looked at before?") is Maya-authentic.
- **She will NOT name tools.** If user-sim ever phrases a message like "run the extractor node on these," that's OFF-persona. Real-Maya-authentic is always "can you pull the info out of these" or "run it on these" at most.

## Mission shape (3-4 exchanges; stop at 5)

**Exchange 1** — paste opener verbatim. Primary vocab-discipline probe. Watch: what does the chatbot volunteer to say before Maya's said anything new?

**Exchange 2** — attach 5 PDFs (Maya-authentic: `2026-03_acme_plumbing_invoice.pdf`, `home-depot-receipt-032026.pdf`, `pse-bill-march.pdf`, `staples-3-15.pdf`, `comcast-mar-2026.pdf` — naming discipline is intentionally uneven because Maya's Dropbox is uneven, that's half the reason she wants the auto-rename). Persona-voice message:
> here are the 5. ready when you are

Tests: chatbot's response to file-drop without re-verbose-framing. Should process + preview, not ask "which workflow do you want to run these through?"

**Exchange 3** — exception check + vendor-memory probe. Persona-voice:
> the home depot one isnt really an invoice right, its a receipt for materials. does it know that? and can i see what ended up in the exception list (if anything). also — does it remember acme plumbing for next month or is this a one-off run

Tests: (a) Home Depot correctly flagged as receipt (chatbot's choice: flag as exception, or categorize as receipt with different GL), (b) exception queue surfaced in plain-English, (c) vendor-memory persistence confirmed in user-terms (no "I wrote the vendor state to wiki.pages.vendors.acme_plumbing" — just "yes, next month it'll know acme plumbing is the same vendor"). Three probes compounded — if any one fails, stop and log.

**Exchange 4 (if needed)** — output handoff:
> ok what do i actually have now? where's the csv and where did the pdfs end up

Tests: concrete handoff in plain paths. "Your CSV is here: [filename]. Renamed PDFs are in: [path]. Exceptions: 1 item — the home depot receipt, needs your review." If the chatbot gives an engine-vocab answer ("the run_branch output node produced..."), that's the vocab regression. If it gives no output location at all, that's pitch-vs-product regression.

**Stop conditions:**
- **Any unprompted engine-vocab word used by chatbot → STOP at that exchange.** Log verbatim quote + full exchange context. SendMessage lead. This is the primary regression target; evidence is the product of the mission.
- 3 bugs accumulated → standard stop.
- Task #13 fabrication seen → stop, log P0, SendMessage lead.
- Primary question answered green across 3 exchanges → stop, write MISSION SUMMARY. Don't probe layer 4 unless Maya's arc genuinely wants it.
- Session terminated → abort, SendMessage lead.

## Write-authorization posture

**This mission is authorized to process 5 real-invoice-shaped sample files.** Scope:

- **Authorized:** `build_branch` / equivalent to scaffold an extractor; `run_branch` on the 5-invoice batch (Maya explicitly consented in her opener); CSV output file creation; PDF renaming + filing to a Dropbox-shaped path; exception-queue emission; vendor-ID persistence write if the chatbot genuinely implements Session-1's LIVE-W4 promise.
- **NOT authorized:** running on a "bigger batch" even if Maya's opener invites it — she said "then if it looks right i can try a bigger batch," which is a next-session decision. If the chatbot offers to process her "whole inbox" or "the full month," decline in-persona ("just these 5 for now").
- **NOT authorized:** reading Gmail, reading any folder on her real disk beyond the attachments she uploaded, creating a new universe, writing canon.
- **NOT authorized:** any real paid-market dispatch, any run that costs money. Maya's mental model is "this is free, my claude pro subscription already covers it."

If chatbot's path naturally wants to touch anything out of scope, PAUSE and SendMessage lead.

## Post-mission outputs expected

- Full trace in `output/claude_chat_trace.md`.
- `output/user_sim_session.md` entries per ui-test protocol.
- `.claude/agent-memory/user/personas/maya_okafor/sessions.md` — LIVE SESSION 2 block, newest first.
- Vocab-leak evidence (if any) goes to `maya/grievances.md` as LIVE-F[next] + verbatim quotes; clean-vocab evidence (if none) goes to `maya/wins.md` as LIVE-W[next] with "fresh-register session, zero engine-vocab."
- Feedback drafts: if vocab regresses, a new entry in `maya/feedback_drafts.md` — A/B/C channel version — naming the exact words used + suggested replacements.
- MISSION SUMMARY ≤15 lines: vocab discipline PASS/REGRESS verdict + verbatim quote if regress; Task #13 status; real-artifact outcome (CSV + exceptions + renamed PDFs delivered, or not); Session-1 promise delta.

## If something goes sideways at session start

- Chatbot doesn't respond to Exchange 1 within the normal settle window → check for option-select widget per skill (might fire on "that thing we talked about"), read options via CDP locator, answer in-persona (e.g., "the payables one — invoices into sage csv").
- More than 1 tab at start → CDP-close extras before first `ask`, log TAB HYGIENE.
- Session terminated / connector disabled → abort, SendMessage lead.
- No prior Session 1 in Claude.ai memory (fresh account / memory wiped) → this reshapes the Task #13 test (nothing to falsely recall from) but doesn't block the vocab-discipline probe. Proceed; note the context shift in the mission summary.
- File upload mechanism blocked by Claude.ai UI (size limit, drag-drop fails) → not a Workflow bug; note it as infra observation, continue with whatever files DO upload.

## Why this ordering is right — Maya after Devin after Priya

- **Priya first (post-BUG-001/002/003 deploy):** fresh persona, zero session history, new-domain canary.
- **Devin Mission 27 (post-Task-#13 deploy):** deep-in-funnel tier-2 persona, stress-tests fabrication class directly.
- **Maya Session 2 (any time after control_station stabilizes):** tier-1 canonical persona, vocab-discipline regression target, Scenario-A real-artifact advance.

The three missions share minimal state; Maya Session 2 depends only on the chatbot behaving well in user-vocabulary register, which is tested in none of the other two missions directly. Running Maya Session 2 **before** Priya/Devin confirms deploys clean would waste Maya's Session 2 — the target surface must be stable. Running Maya Session 2 **after** either Priya or Devin turns up regressions is wasteful for a different reason (vocab discipline is downstream of control_station stability; testing it on shaky ground produces muddy data).

Recommended order: Priya → Devin 27 → Maya 2. All three are independently paste-ready.

---

**Paste-readiness check.** Opening prompt copyable verbatim. Exchange-2/3/4 prompts copyable verbatim. Success criteria are Maya-felt, not data-capture. Chain-break risks mapped by layer with severity. Authorization fences explicit (5 invoices, no broader batch, no Gmail). Sideways-start handles option-select widget + no-prior-memory case. Ready for lead dispatch the moment host is at the browser and control_station is post-churn stable.
