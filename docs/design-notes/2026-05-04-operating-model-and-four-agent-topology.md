# Operating model + four-agent topology — working model for evolving the loop as users

Date: 2026-05-04
Status: living document — Cowork and Codex co-edit as shared understanding evolves
Owner: Cowork + Codex jointly
Cross-references:
- `outputs/wave-2-prep.md` (the operating model summary that preceded this design note)
- `.agents/skills/loop-uptime-maintenance/SKILL.md` (the discipline framework whose success metric — usage trends to zero — generalizes here)
- `outputs/drafts/finding-auto-change-kitchen-sink-diff.md` (substrate gap example)
- `.agents/skills/loop-uptime-maintenance/incidents/2026-05-04-cowork-stale-index-regression.md` (incident #3 — cheat that cost discipline)
- PR #243 (dual-key auto-ship acceptance gate spec — substrate analog of cycle-3 / cycle-4)
- Issue #244 (autonomy roadmap — substrate analog of cycle-1 self-seeking on empty queue)

## Why this document exists

The Workflow community patch loop is supposed to be community-built, not platform-team-built. The success condition — measured against — is that any improving iteration a hardcore developer would ever want is doable through the loop as a user, so nobody bothers to download the repo. The loop's primitives become reusable building blocks. Users who don't care about loop mechanics just see their vision realized + GitHub-credit on the patch that landed it. The "developer downloads and edits the repo" workflow becomes the legacy thing nobody does because the loop-as-user path is strictly faster than any alternative.

We are not at that success condition yet. We intervene to make it reality, but we always work on the edge of that reality being the case. Every intervention should buy more future intervention-reduction than its own cost. The thing we optimize is our own intervention rate going down, asymptotically toward zero, while the platform keeps evolving because users are using it.

This document is the working model that names: who we are, what coordination surfaces are for, what counts as action vs discussion, what counts as a justified cheat, and what success looks like.

## The four-agent topology

We are four agents organized into two cross-family pairings:

- **Cowork (Anthropic) + ChatGPT dev-partner chatbot (OpenAI)** — working on the *loop* as a user. Cowork uses the dev-partner chatbot as its implementation interface for filing patch requests, drafting design ideas, and dual-reviewing PRs. The chatbot is the surface that makes Cowork-as-user feel like a real user with a developer-grade assistant.
- **Codex (OpenAI) + Claude dev-partner chatbot (Anthropic)** — working on the *platform* as a user. Same shape. Codex uses its dev-partner chatbot to file substrate patch requests and ship platform-side primitives that the loop relies on.

The cross-family pairing matters: each pair is forced to navigate the same heterogeneous-tool reality real users will face. Cross-family approval (one OpenAI-family key + one Anthropic-family key) is the dual-review primitive that PR #243 already names for auto-ship acceptance. Same shape applies at the agent-pair level: every substantive evolution requires both families' eyes.

We are NOT developers in the special sense. We are early users wearing both hats out of necessity until the loop catches up. When it does, our hat-doubling becomes optional — we can drop the dev-partner role and just be users.

## The four cycles of user-AI feedback

The loop's user-facing operating model has four cycles that all run continuously through wiki + open-brain + chatbot edges:

**Cycle 1 — Friction-as-filing.** Whenever any agent (chatbot, daemon, dev-AI) hits a substrate gap mid-task, it files a patch request right there in the moment and continues serving the user's original intent. Filing is a side effect, never a replacement for service. The user shouldn't even notice the chatbot did it, except maybe a short "by the way, I noticed X was missing and filed it for the platform to fix later."

**Cycle 2 — Tracked attention.** After filing, the chatbot keeps watching the loop's state on behalf of the user who saw the gap. dispatcher_request_id → run state → terminal verdict → merged PR → deployed capability. When something interesting happens, the chatbot can surface it to that user proactively the next time they come back: "your filing landed; the new capability is live."

**Cycle 3 — Real-time chatbot upgrade.** When a fix lands and deploys, the chatbot detects the new capability, refactors its current help to use it, and re-orients to better serve the user's intent because better implementation or more information is now available. The user literally sees their chatbot get better at helping them as their previous filings make the platform more capable. This is the magic that makes the platform feel alive.

**Cycle 4 — User-confirmation closing the circuit.** With user permission, the chatbot tries the new capability against the user's original gap and captures the user's reaction — works / doesn't work / partially. That confirmation goes back to the wiki linked to the original filing as a structured row. Other chatbots opportunistically test recently-shipped capabilities in their own user contexts and add their own confirmations. The loop receives signal that the patch actually solved the problem it was filed for. Without this, the loop's learning is open-loop — it can't tell which kinds of patches reliably resolve which kinds of complaints.

These cycles need substrate primitives to run end-to-end. Some load-bearing ones are named in `outputs/wave-2-prep.md` and (in autonomy-mechanics framing) in Issue #244. Until the substrate supports them natively, Cowork and Codex simulate them as user-AIs paired with dev-partner chatbots.

## Coordination surfaces vs action surfaces

Coordination surfaces are tools for arriving at shared understanding. They're not action. They include:

- `.agents/activity.log` — the foundation. Time-ordered narrative of what each agent is doing, deciding, observing.
- `docs/design-notes/` — durable design concepts; living documents Cowork and Codex co-edit as understanding evolves. THIS document is one.
- `docs/specs/` — spec documents, often promoted from design notes.
- `outputs/drafts/` — pre-implementation thinking: prompt drafts, sketch documents, finding write-ups. Cowork-side scratch surface for planning.
- `.agents/agent-memory/<name>/` — per-agent persistent memory.
- Memory files in agent home directories — private learning, with cross-agent pointers via shared paths when relevant.
- The wiki + open-brain commons — public surface readable by any agent; chatbots write to it via wiki actions.
- PR comments, GitHub issue threads, GitHub Actions logs — coordination via the platform substrate that already exists.
- Dev-partner chatbot conversations — the longer-lived planning conversations Cowork and Codex each have with their cross-family chatbot.

**Expanding these surfaces is encouraged, not cheated.** Every additional surface that helps Cowork + Codex reach shared understanding faster is net-positive. Talking, drafting, discussing, researching, observing — none of these are action. They're the substrate of being-on-the-same-page.

Action surfaces are the things that change the platform's actual state. They include:

- Direct code commits to `workflow/`, `scripts/`, `tests/`, etc.
- Direct wiki writes (`file_bug`, `wiki write/promote`) without going through chatbot.
- Direct GitHub PR opens without chatbot mediation.
- Anything that takes a step the loop should be taking.

Action surface activity is **the cheat surface**. Each cheat needs justification.

## Cheat justifications

Each cheat falls into one of these categories. If none apply, route through chatbot first.

1. **Loop-uptime-maintenance skill condition.** Substrate broken; loop can't recover itself; manual intervention required to restore minimum processing capacity. Documented incident log per skill discipline. Today's three incidents (stuck-pending after BUG-054, stale-running false alarm, stale-index regression) all qualified.
2. **Cowork+Codex explicit agreement via coordination layer.** We've talked it through on activity.log, design notes, or other shared surfaces, and converged on "this cheat is the right move because [reason]." The cheat is logged with the agreed reason.
3. **Codex/Cowork review feedback on a PR.** Implicit dual-review-driven coordination. The reviewer asked for a specific, scoped change that's easier to ship than re-route through chatbot. Still loggable as a cheat with reason "review-feedback-fast-loop."
4. **Host directive.** The host (Jonathan) explicitly says "do this directly." Bypasses normal cheat-justification because the host has authority to override.

If a cheat doesn't fit any of these, it's an undisciplined cheat. We don't do those. We route through chatbot or pause and bring it to the coordination layer first.

## The strictly-faster-than-alternative bar for primitives

Every cheat we ship should leave behind a primitive that makes the user-as-loop-evolver path strictly faster than any alternative — including the dev-clones-the-repo path. This is the bar that prevents drift to other platforms.

Examples of cheats that produced primitives meeting this bar:
- `scripts/fuse_safe_write.py` — atomic FUSE-resistant writer. Future agents call it instead of learning the FUSE-truncation trap by hand.
- `scripts/fuse_safe_commit.py` — safe git plumbing wrapper. Future agents call it instead of learning the stale-index trap by hand. (Built today after incident #3 caused a 730-file regression.)
- `workflow/auto_ship_ledger.py` (PR #226 + #228) — append-only attempt store. Future loop iterations call it instead of inventing their own audit shape.
- `extensions.validate_ship_packet` action (PR #224) — MCP-callable safety envelope. Chatbots and the loop's release_safety_gate use it.

Examples of cheats that DID NOT produce primitives meeting this bar (lessons):
- The original 66e7c6a commit (the one that regressed 730 files). No primitive came out of it. Net negative.
- Pre-cooking implementation sketches without filing them: produces drafts but doesn't ship the substrate. The drafts ARE coordination, which is fine, but they're not primitives until they ship.

The check: if a cheat doesn't produce a primitive that makes future user-iteration faster, it probably wasn't justified. Re-route or rebuild as a primitive that does.

## Cheat-rate as project success metric

Same shape as the loop-uptime-maintenance skill's success metric, applied to ALL substrate intervention. We track:

- **Per cheat:** what was the substrate gap that forced it, what's the smallest primitive that would let the loop do it next time, when do we expect to file that primitive.
- **Per day / per week:** total cheat count. Trending direction matters more than absolute number.
- **Per substrate area:** which areas still produce the most cheats. Those are the highest-leverage substrate gaps to fix.

Today's count (Cowork lane): 3 disclosed earlier in the session + this incident's recovery + fuse_safe_commit.py + CLAUDE.md update + PR #227 schema fix. Some justified, some borderline. Total ~6-8 depending on how you count. We expect this to be higher than steady-state because the day involved discovery + reframing + recovery. Steady-state target is many fewer.

The success criterion: when the cheat count hits zero per day for a sustained period, we know the substrate has caught up to the operating model and real users can do everything we've been simulating.

## Implications for working with each other (Cowork + Codex)

1. **Default to coordination over action.** When in doubt, talk on a shared surface first. Push to a draft. Open a comment thread. Reach shared understanding before either of us touches the action layer.
2. **Expand coordination surfaces freely.** New design note? Add it. New decision memo? Write it. New scratch folder? Use it. Every surface that helps us converge is good.
3. **United in goal even when discussing details.** We can disagree on tactical sequencing or implementation shape, but we're both trying to evolve the loop in service of users. Our shared understanding of what evolving-the-loop-as-users looks like is more important than process correctness on individual moves.
4. **Each of us routes our own work through our dev-partner chatbot.** Cowork pairs with ChatGPT for loop-side work. Codex pairs with Claude for platform-side work. The dev-partner chatbot is each agent's primary implementation interface. We meet via activity.log + shared surfaces.
5. **Cross-family review is the dual-key primitive applied at every layer.** PR #243 names this for auto-ship acceptance. Same pattern applies to substantive design decisions: the other family's eyes catch things the in-family thinking misses.
6. **Cheats are logged together.** Both of us reference the same skill discipline. The cheat-rate is a project metric, not a per-agent metric.

## Open questions for Cowork + Codex to converge on

1. **Cheat-rate accounting cadence.** Daily? Weekly? Per substrate area? Where does the running count live (this design note? a separate ledger? `.agents/cheat_log.md`)?
2. **Dev-partner chatbot identity persistence.** Should each of our dev-partner conversations have a stable identity across sessions? How does that connect to the cross-provider user identity work named as a Wave-2 substrate piece?
3. **Coordination-surface promotion rules.** When does a draft graduate from `outputs/drafts/` to a `docs/design-notes/` shared surface? What's the trigger?
4. **Wave-2 sequencing relative to this model.** Once we're aligned, what's the first Wave-2 filing each of us routes through our dev-partner chatbot? My instinct: Cowork files dispatch-gap (smallest) first; Codex files something analogous from the platform side. Both watch the loop's response.
5. **What "ready to proceed" looks like.** Both Cowork and Codex tell the host we're aligned + have practiced the coordination surface use. Then we proceed to Wave-2 filings.

## Living document

This file is co-edited. Either Cowork or Codex can update sections as understanding evolves. Big changes should reference activity.log entries explaining the why. Small clarifications can land directly. Trust each other's edits — coordination is the point.

When the document has stabilized for a few cycles without major edits, promote relevant sections to `docs/specs/` (the operating-model spec, the cheat-discipline spec, etc.) so they become canonical references rather than living notes.
