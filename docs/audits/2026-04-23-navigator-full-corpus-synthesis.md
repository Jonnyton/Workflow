---
title: Navigator full-corpus synthesis — sequencing + substrate + host-independence
date: 2026-04-23
author: navigator
scope: 6 plans, 4 drafts, 2 notes/concepts, 9 load-bearing bugs (003/005/011/017/019/021/022/023/024) + activity.log since 2026-04-16
status: pre-decision input for host
---

# Navigator full-corpus synthesis

Working artifact. The authoritative deliverable is the SendMessage reply to
lead containing (a)/(b)/(c)/(d). This doc is the scratchpad so I can cite it.

## Corpus integrity notes

- `pages/bugs/BUG-023-daemon-disk-full-...` has empty body (content.length=0) —
  title is in `wiki action=list` output but the file stores zero bytes. The bug
  can't actually be triaged from the wiki; the content survives only in
  cross-references (strategic-synthesis, morning P0 activity.log). That's
  itself a data-integrity issue worth calling out.
- Two largest plan pages truncate at 15K hard cap:
  - `strategic-synthesis-2026-04-24.md` is 21,483 chars — got 15,000.
  - `next-level-primitives-roadmap.md` is 20,609 chars — got 15,000.
  The `wiki action=read` tool exposes no offset/range param. This is ALSO a
  primitive gap: a chatbot reading these plans via MCP hits the same wall.
  I have the first ~70% of each; from cross-references (builder-notes,
  tier-1-investigation, activity.log, strategic-synthesis's first 15K
  content) I can reconstruct the intent of the tails with high confidence —
  but not the exact text.

## (a) Sequencing recommendation given full corpus

### What doesn't change

The three-lane parallel proposal (Lane 1 BUG-023 + Tier 1 routing + Lane 2
GHA auto-recovery, with Layer-3 design session + circuit-breaker as
separate lanes) remains correct in shape. The full corpus doesn't overturn
the shape; it **deepens** why each lane is load-bearing and **tightens**
the order within the "Immediately" set.

### What the corpus changes

**1. Tier 1 routing is more load-bearing than "first among equals."**

The tier-1-investigation-routing-resolver plan makes explicit what was
implicit in earlier conversations: BUG-019, BUG-021, BUG-022 are almost
certainly **one root-cause expressed as three symptoms** (conditional edge
resolver reading stale state OR closure-captured state OR mismatched END
sentinel normalization). The investigation is cheap (1-2 days, one dev)
and the finding either closes all three with one fix (Case A in the plan)
or at most two (Case B).

The strategic-synthesis plan ALSO makes explicit what next-level-primitives
#2 only hints: **"without working conditional termination, no iterative
agent pattern is viable, and iterative is the whole point of agent teams."**
Agent teams are the first real stress-test of routing. Scene-direction
(linear) and paper-writing (overwrite) don't exercise it. Every
downstream primitive in the roadmap — sub-branch invocation, per-node LLM
policy, eval primitives — sits on top of working routing.

Add: the priority-1 spec in next-level-primitives-roadmap (validated state
transitions, generalizing the BUG-015/016 win) — already landed per
2026-04-22T07:10Z activity log (#22 structured JSON multi-output). So the
**real** Immediately queue is not "Tier 1 + storage + goals" on equal
footing. It's:

  1. Tier 1 routing investigation (1-2 days, closes 3 bugs, unblocks all
     iterative patterns).
  2. Storage observability + rotation (BUG-023) — prerequisite for
     multi-user story, already burned one 18h outage.
  3. Goals reliability hardening — same P0 precedent, disk-I/O-error on
     `goals action=get` in session 2026-04-22.

That's the strategic-synthesis "Immediately" list verbatim, with Tier 1
first for the right reason (it unblocks the deepest downstream work),
storage second (it closes a known-to-page P0 class), and Goals third
(compounding leverage — Goals is the coordination substrate for every
downstream pillar).

**2. The "ship bundle now" decision is correctly scoped.**

The provider-stack RCA bundle (#2 Gemini/Groq registration + #3 debug
instrumentation + #5 context-bundle dedup/LIMIT 25) is the implementation
half of the 2026-04-21 prod-LLM-binding design note. Shipping it resolves
the live prod revert-loop (empty-prose codex-only, concordance burning
cycles at 02:17 UTC). BUG-024 confirms `_trim_to_budget` is a latent
ship-stopper — trimming list length not string bodies means any future
bundle-growth path regresses regardless of whether dedup+LIMIT 25 holds.
**Worth adding BUG-024 to the bundle or queueing it immediately after.**

Shipping the bundle is also Tier 1 routing's indirect enabler: a daemon
with zero reachable providers cannot execute agent teams even if the
routing resolver is perfect. Tier 1 routing needs live providers to
validate against. **So: ship the bundle BEFORE Tier 1 investigation
starts, not in parallel.** Bundle is ~hours. Tier 1 is 1-2 days. Clean
sequencing.

**3. Lane 2 (GHA auto-recovery) should move to Lane 3.**

Reading the full corpus shifts priority: Layer-3 typed records substrate
is a higher-value next piece than GHA auto-recovery. The strategic
synthesis's Pillar 3 Layer-3 (bugs, feature requests, goals, published
branches, gate events, attestations — server-owned IDs, explicit
lifecycle) is on the critical path for Pillar 2 (real-world gates). GHA
auto-recovery is a hardening tactic; it doesn't unblock the product.

Revised Lane structure this week:

  - **Lane 1 (bundle + Tier 1):** ship bundle now; Tier 1 investigation
    starts as soon as bundle green on prod. Same dev, sequential.
  - **Lane 2 (BUG-023 storage + triage):** separate dev, parallel.
    Acceptance: storage_inspect surface on `get_status`; soft/hard caps;
    rotation policy; one P0-class precedent closed.
  - **Lane 3 (Layer-3 design session):** lead+navigator+host. Output is a
    design note that commits to a storage backend for bugs/goals/gate
    events, NOT code. Design note becomes a wiki plan page after session.
  - **Lane 4 (GHA auto-recovery):** later in the week or next, depending
    on DO API token arrival.
  - **Lane 5 (pause-on-exhaustion circuit breaker):** separate lane, small
    scope. Activity log confirms "worker kept rolling through failed
    scenes faster than scene-boundary pause caught" — this is a real
    concurrency gap, not a conceptual one. Dev-claimable once Tier 1
    lands.

### Why this ordering earns its keep

The strategic-synthesis plan's load-bearing claim is:
**"The stack has to ship as a stack, not as individual features."** Every
primitive on the "what future chatbots need to build whatever they want"
list depends on the ones upstream. Fork-without-content-addressing is
moving targets. Content-addressing without reliable Goals is broken
references. Reliable Goals without gate events is LLM-judge drift. Gate
events without Layer-3 substrate is a wiki that breaks at 200 bugs
(literally — BUG-023 already saw a break at ~24 bugs).

So the sequencing is NOT "pick three good features and ship them." It's
"unblock the downstream stack by hardening upstream primitives in the
right order." Tier 1 routing unblocks iterative patterns (agent teams,
retry loops, review-revise). Bundle + BUG-023 unblock multi-user
reliability. Layer-3 design session unblocks gate events, which unblocks
the entire Pillar 2 real-world-gates proposition.

## (b) Callouts from drafts and bugs that change decision shape

### B1. BUG-024 is a latent ship-stopper — add to bundle

Confirmed reading the bug page itself: `_trim_to_budget` trims list length
but not string bodies; bundle stays at 48535 tokens after trim; every
subsequent scene sees identical over-budget bundle. The #5 fix
(characters-dedup + LIMIT 25) removes the specific 48535 cause but the
trim primitive remains broken for any future growth path. **Recommend:
add a small #6 to the bundle — fix trim to operate on bytes/tokens not
list length.** ~30 LOC + test. Keeps the trim honest.

### B2. BUG-023 data-integrity — the page exists but body is empty

The disk-full P0 is real (activity log + STATUS.md both confirm). But the
wiki page `pages/bugs/BUG-023-...md` has zero bytes. Unclear whether this
is the disk-full P0 itself truncating the file mid-write, or a separate
wiki storage bug. Either way: the bug can't actually be triaged from wiki
alone; the ref-from-strategic-synthesis is the only surviving record of
intent. **Recommend: re-author BUG-023 body before Lane 2 starts, so the
storage-lane dev has something to work from.** Cheap; lead or I can do
this in 5 minutes from STATUS.md Concerns text.

### B3. BUG-017 (bwrap) is silent about what sandbox alternative exists

The bug page says "If bubblewrap is the intended sandbox mechanism, the
host needs `kernel.unprivileged_userns_clone=1` (Linux) or equivalent; or
the daemon should fall back to a different sandbox (docker, firecracker,
or plain subprocess with resource limits)." The DO Droplet is Linux; this
kernel sysctl may or may not be settable without a reboot. **Worth a
cheap probe** before BUG-017 lands on any dev queue — if the sysctl is
un-settable, the fix scope changes from "turn it on" to "ship a fallback
sandbox," which is a much bigger task. This might be a 2-minute host
action that unlocks BUG-017 entirely, OR it might justify designing a
docker-exec-based fallback from scratch.

### B4. BUG-005 (sub-branch invocation) is load-bearing for Pillar 3 Layer-4

Reading strategic-synthesis against BUG-005: the Goals engine story
depends on composable branches. Sub-branch invocation is how "a
literature-review workflow invokes a source-triage sub-workflow"
actually works. Today every workflow is monolithic (22-node agent_team_20
flattened everything into one graph). **Without BUG-005, the canonical
starter branch model doesn't compose.** This pushes BUG-005 up the
priority stack for Phase 1 substrate (which strategic-synthesis has as
primitive #4 in the missing tail). Should ship AFTER Tier 1 routing (so
sub-branches can use conditional routing internally) but BEFORE
`publish_version` rollouts get deep.

### B5. BUG-011 (durable execution) deserves its own decision pass

The bug page correctly notes: "Temporal-style durable execution is the
2026 industry standard (OpenAI uses it for Codex in production) so this
is no longer an exotic requirement." Next-level-primitives #7 frames
this as a durability cluster ([[BUG-009]] scheduled invocation +
[[BUG-010]] project-scope memory + [[BUG-011]] durable execution), not
urgent for agent-teams stress testing but prerequisite for real
production use. Strategic-synthesis is more forceful: "A run from today
may be cited by a gate event two years from now. Content-addressed
`branch_version_id` is load-bearing for attribution survival."

So durability is a Pillar-2 prerequisite, not a Pillar-3 nice-to-have.
This is a substrate decision, not a feature. **Recommend: add
"durability substrate — what backend for in-flight run state?" to the
Layer-3 design session agenda.** Candidates: LangGraph checkpointer
extended (SQLite already in hard rules), Temporal, plain Postgres with
event-sourcing. Each has different operational surface.

### B6. The vetted-specs queue is deeper than STATUS.md shows

STATUS.md Approved specs table lists 12 dev-dispatchable + 10 deferred.
But the next-level-primitives-roadmap and the wiki plan pages reveal
multiple specs that are already ratified but not yet in that table:

  - `dry_inspect_node` / `preview_change` (implied by chatbot-builder-behaviors + Priya L1 mission draft)
  - `recursion_limit_override` on `run_branch` (tier-1-investigation Step 6)
  - `storage_inspect` tool (strategic-synthesis Immediately #2)
  - Layer-3 typed-record surface (storage-engine decision)
  - `publish_version` on branches (strategic-synthesis Phase 1 substrate)
  - `canonical_branch` marker on Goals (strategic-synthesis Pillar 1)
  - `fork_from` lineage on branches (strategic-synthesis Pillar 1)
  - Gate event spec + ingestion surface (strategic-synthesis Pillar 2)
  - Gate-based leaderboard (strategic-synthesis primitive #6)

These are not yet navigator-vetted formal specs; they live in plan pages
but haven't been dispatched. **Recommend**: after the bundle ships, spend
one navigator cycle promoting these from plan-page mentions to formally
vetted specs in `docs/vetted-specs.md`. Dev can't claim what isn't listed.

### B7. Chatbot-builder-behaviors page is the canonical onboarding doc — already shipped

Excellent discovery: the `chatbot-builder-behaviors` wiki page already
captures much of what I've been drafting as memory additions. It tells
every chatbot session on this project: read PLAN.md first, don't
re-discover bugs, don't silently work around, file primitive gaps via
file_bug, don't reorganize unprompted, don't apologize for environment
blockage. **This is the Tier-1 chatbot behavior contract in living
form.** When I draft the 3-primitive proposal (dry_inspect_node,
previous_run_context, estimate_cost), the right surface is probably a
wiki plan page, not a docs/design-note — so it's discoverable via
`wiki action=list` without having to read GitHub.

### B8. Workflow-patterns (draft) has the "common paper shape" skeleton

The paper-shape (frame → audit → gather → filter/engage → draft →
calibrate/ground → critique → format → END) is probably what "Produce a
research paper" Goal abstractly is. Important for Pillar 1: when Goals
become first-class, the **intent spec** field the strategic-synthesis
describes needs to be richer than prose. The common-shape pattern
suggests Goals should include a skeleton/template hint, not just an
I/O schema. When building `frame_position → calibrate_claims →
format_for_publication`-shape workflows, the chatbot can pattern-match
against known shapes instead of freestyling. This is cheap to surface
and would make forkable branches much more discoverable.

### B9. Activity.log shows Task #13 LANDED (Rule 11 shared-account directive)

Commit `a7f5f74` is the control_station Rule 11 shared-account directive.
Devin M27 mission draft's primary Task-#13-bait probe is now unblocked.
This is a dispatch-order-matters update for the user-chat intelligence
arc: Devin M27 can run as soon as host is at the browser. Priya L1 is
still the correct first mission per draft ordering, but Devin M27 is no
longer blocked.

### B10. Bundle + provider fix reframes the whole "daemon paused" question

Activity log 2026-04-23T20:30Z confirms daemon was HARD-STOPPED (workflow-worker
Exited 137, `.pause` file in place). My earlier read of prod `get_status`
showing concordance-B55 draft activity at 02:17 UTC must mean one of:
(a) daemon restarted somehow (systemd? someone ran docker compose up?),
(b) the activity_log_tail is historical lag,
(c) a separate non-worker container is emitting draft events.

Looking more carefully at get_status.evidence.last_n_calls timestamps:
the 02:17 UTC events DO look fresher than the 20:20 UTC ones, not
historical lag. If the worker was truly Exited 137 at 20:30 UTC yesterday,
something restarted it — and since host's directive was explicitly "leave
paused until optimization review complete," that's a DIVERGENCE from
host intent. **Worth surfacing clearly before any persona dispatch.**
This may be the single most urgent production concern right now — if
something is auto-restarting the worker without human approval, the
daemon is effectively unsupervised despite the pause directive. I'd
prioritize `ssh droplet docker ps` verification before anything else.

## (c) Host-independence architecture — where it fits

This is the most important of the four questions, and the framing
matters. Host wants "never need host to restore the system." That's a
**strong** formulation — not just "can survive a host vacation" but
"doesn't need host at all for recovery." Full host-independence is
achieved when:

1. Any incident can be mitigated autonomously OR via a human
   non-host-specific (CI operator, on-call rotation, even a future OSS
   contributor with proper auth).
2. No secret, credential, or piece of state lives only on host's
   personal machine.
3. Recovery runbooks are executable by a non-host.

### The architecture question: where does host-independence LIVE?

**It doesn't land cleanly in any one of Pillars 1-3.** Host-independence
is a cross-cutting invariant like the three pillars, but at a different
architectural level — it operates on the *operational substrate*, not
the *product substrate*. I'd call it a fourth cross-cutting concern
alongside the three pillars, specifically:

**Pillar 0 — Operational independence.** Every operational surface
(recovery, deploy, secrets, paging, incident response, config mutation,
credential rotation) is host-independent either intrinsically or via a
host-independent twin.

Why Pillar 0 not Pillar 4: it's the precondition for Pillars 1-3. A
platform whose restoration requires host-machine access cannot
realistically serve thousands of DAU, regardless of how good its Goals
substrate or its gate events are. Pillar 0 precedes; Pillars 1-3 layer
on top.

### Concrete landing points across the stack

Now the specific architectural-layer question: where does
host-independence show up in the pillar structure? Four places, mapping
to the four substrate layers from strategic-synthesis Pillar 3:

**Layer 1 (personal context, per-user, private):**
*No host-independence concern.* Each user's personal memory is their
own problem. Per-user lockouts aren't platform-level outages.

**Layer 2 (per-universe scratchpad, narrative wiki):**
Host-independence means: **every wiki can be read and written by
any-tier user without host being online**. Today's tinyassets.io/mcp
is host-independent at the read surface (DO Droplet serves wiki
directly), but WRITE surface depends on whether the daemon has
reachable providers for any write-adjacent LLM call. This is mostly
already there — one more reason to prioritize the provider-stack bundle.

**Layer 3 (cross-universe structured records — bugs, goals, gate
events, branches, attestations):**
*This is the primary host-independence surface.* The strategic-synthesis
proposes Layer-3 specifically as "server-owned IDs, explicit lifecycle,
typed records." If Layer-3 lives on the DO Droplet with multi-user auth
(ideally, OAuth per strategic-synthesis's Pillar 3 federation story),
then bugs can be filed, gate events attested, branches published, and
goals coordinated **without host at all**. The current "file_bug verb
+ pages/bugs/ directory" is a Layer-2-shaped version of Layer-3 work.
It works but it's not durable against concurrent writers from multiple
users — and that's exactly the point.

**Layer 4 (global canonical — PLAN.md-shape docs, architecture
principles, canonical pattern library):**
Git repo with PR workflow is already host-independent by construction
(GitHub does the hosting). The question is whether PRs can be reviewed
and merged without host — which is the DAO governance question
(`project_dao_evolution_weighted_votes`: "MVP = sole host, no DAO. Real
currency cutover adds human co-op + minimal multisig."). Layer 4
host-independence is a governance question, not a substrate question.

### The Layer-3 substrate decision IS the load-bearing host-independence decision

**This is my strongest claim.** The single architectural decision that
most advances host-independence is: what storage backend, access
control, and auth model does Layer-3 use?

Candidates:
- **Postgres + OAuth + server-side ID issuance.** Standard, boring,
  well-understood. Migrates cleanly from single-host MVP to
  multi-region later.
- **SQLite-per-user + wiki-federation.** Aligns with the already-
  running wiki pattern. Lower ops burden. Harder concurrent-write story.
- **Git-repo-as-Layer-3.** Every bug/gate-event is a commit. Free
  federation, free auth (GitHub), free audit log. Harder to index,
  harder real-time queries.

**Strong recommendation: decide this in the Layer-3 design session.**
Don't predecide. The pillar structure plus the host-independence
requirement plus the rate-of-growth projections (1000s of DAU) narrows
the candidates but doesn't pick one.

### Other host-independence landing points

Beyond Pillar 0, there are three specific operational surfaces that need
explicit host-independent treatment:

**1. GH Actions workflow configs (already partial).** Deploy-prod.yml,
dr-drill.yml, actionlint.yml, secrets rotation. Every deploy path
should be CI-driven, not host-machine-driven. Already mostly there;
the remaining gaps are (a) host-only secrets (DO API token — Task #4
pending), (b) SSH keys (Bitwarden-vault-backed, mostly done).

**2. Pager paths.** Pushover landed 2026-04-22 priority=2 validated.
This is operational independence — pages reach a human via SMS even
if host's desktop is off.

**3. Incident-response typed records (new — surfaced by this sweep).**
When a P0 happens, today the record lives in `docs/audits/` +
activity.log + STATUS.md Concerns. That's Layer 2 for a Layer-3-shaped
artifact. At swarm scale, incident records need first-class typed
storage: incident_id, when, what, who-paged, what-mitigated, what's-still-open,
postmortem-status. Specifically: an on-call engineer who isn't host
should be able to list open incidents via MCP, claim one, update
status, ping a different human. That's a Layer-3 typed-record class
— another candidate for the Layer-3 design session agenda.

### Summary for (c)

Host-independence is a fourth cross-cutting concern ("Pillar 0 —
Operational independence") on equal footing with the three product
pillars. The PRIMARY technical landing point is the Layer-3 substrate
decision in strategic-synthesis Pillar 3. The SECONDARY landing points
are CI-driven operations (GH Actions for deploy/rotation), pager paths
(Pushover already solved), and a new Layer-3 typed-record class for
incident response (surfaced by this sweep). Lock it in as an architectural
invariant: **"every operational surface is host-independent or has a
host-independent twin."**

## (d) Things lead should know that nobody asked about

**D1. The wiki read truncation cap (15000 chars) is itself a primitive gap.**
Any chatbot trying to read the strategic-synthesis plan via MCP hits
the same 15K wall I hit. A new chatbot orientating via
`wiki action=read page=pages/plans/strategic-synthesis-2026-04-24.md`
gets 70% of the load-bearing strategy doc and no indication that the
rest exists. The `total_chars` field is returned but most chatbots won't
notice. Either: (a) bump the cap, (b) add a range/offset param, or
(c) auto-paginate in the tool-response. BUG-adjacent. Low-urgency but
systematically reduces chatbot effectiveness on the most important
pages.

**D2. BUG-023 has empty body.** As noted in B2 above. The fact that the
disk-full bug itself has a zero-byte body is darkly funny. Re-authoring
it should happen before the Lane 2 storage dev starts.

**D3. Daemon state possibly divergent from host directive.** As noted
in B10. The prod `get_status` activity_log shows scene generation
activity that post-dates the explicit "daemon LEFT PAUSED" directive.
Either (a) something auto-restarts the worker in defiance of `.pause`,
(b) the probe is showing stale data, (c) a non-worker component is
also doing scene work. Needs `ssh droplet docker ps` before ANY
persona mission — dispatching a chatbot into a broken-loop daemon
produces muddy signal.

**D4. Post-Tier-1, the test harness claim is worth revisiting.**
The tier-1-investigation plan's Step 5 says "Tests land in the
regression suite. Any future change to the routing resolver has to
pass..." That's right, but there's a subtlety: Symptom 2 (BUG-022) is
an integration test against a live agent_team branch, not a unit test.
The plan names `agent_team_3node_v4` on branch `97c377f181fa` as the
integration target. **Worth adding to the dev brief:** the fix is not
done until `run_branch` on that specific branch with the specified
brief produces terminal ESCALATE + run status `completed` (not
`failed`). Integration-test-as-acceptance-criterion.

**D5. STATUS.md Concerns line for Stage 2c memory-scope monitoring
has been "30d clean + Stage-1 assertion firing zero times" since
2026-04-16.** That's a 7-day old entry; we're now at 2026-04-23. Worth
checking whether the 30d clock started from 2b landing (2026-04-16) or
from Stage-2c-monitoring-begin — if from 2b landing, the 2c flag flip
is at 2026-05-16. Low-priority steering signal but worth knowing.

**D6. There's a pattern worth formalizing from reading the corpus.**
Three times in the roadmap pages, the language is "a well-framed bug
surfaces the missing primitive, not the requested fix" (BUG-015/016/018
all shipped with *better* primitives than filed). The chatbot-builder-
behaviors page embeds this as an explicit rule ("file a primitive-gap,
not a bug — name the primitive"). This pattern is already load-bearing
to the project's bug economics. **Worth promoting to a named
principle** in PLAN.md's Cross-Cutting Principles section:
"**File primitives, not patches.** When reporting a bug, frame the
missing primitive that any future domain on this engine would want,
not the local workaround." Cheap addition. Already implicit.

**D7. One missing mission from the user-chat intelligence dispatch
sequence.** The current sequence (Priya L1 → Devin M27 → Maya S2 → Priya
M2 → Priya M3) is a tier-1 funnel. It doesn't cover **tier-2
daemon-hosting**. A Devin-shaped mission specifically exercising
"install the daemon tray, bind a soul.md, host a named daemon, accept
first paid request" would validate the daemon-hosting proposition
against actual flow friction. Currently Devin Session 2 + M27 are both
tier-2 in identity but neither exercises the hosting bind workflow.
Worth a Devin Mission 28 draft (not urgent; after M27 lands).

**D8. The "chatbot-builder-behaviors" page is the canonical onboarding
doc — promote it aggressively.** Right now it's a wiki plan page. Every
chatbot session hitting `wiki action=list` sees it in the plans list.
But a chatbot coming fresh through the `control_station` prompt doesn't
necessarily know to `wiki action=read` it. The control_station prompt
should mention this page explicitly as a required read when working on
anything build-branch-adjacent. Cheap fix; high-leverage. Makes future
sessions (including future-me) arrive with the right model.

**D9. Bug-count observation.** 24 filed bugs across roughly 4 weeks of
agent-teams stress testing. Six resolved, three shipped with better
primitives than requested. That's ~25% "better-than-filed" rate, which
is high — suggests the pattern of "file primitive-gap, dev ships
primitive-aware fix" is well-established and the navigator-vet gate is
earning its keep. Worth tracking as a project metric going forward:
"what fraction of shipped fixes exceeded filed scope?"

**D10. A specific risk in the "ship as a stack" framing.** Strategic-
synthesis argues the whole substrate has to ship together because
each primitive depends on the ones upstream. That's correct as
architecture but risky as product — it implies a long runway before
any of Pillar 2/3 is usable. The risk: host/team work in silence on
substrate for N weeks while the visible product stagnates. **Mitigation:
the "Phase 0 — through Tier 1 landing" period in the distribution
sequencing IS the substrate runway.** That's intentional. As long as
Phase 0 is genuinely cheap (README + positioning + v0.1.0 tag) and
Tier 1 ships in 1-2 days, the substrate runway is short enough that
the stack-as-stack framing doesn't starve the product.
