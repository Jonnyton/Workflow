# PLAN.md drafts — §Daemon identity + §Economic architecture

Two new PLAN.md §s ready for lead review + commit. Each ~1-2 pages, architectural claims only; implementation detail stays in `docs/vetted-specs.md`.

**Proposed placement in PLAN.md:**
- §Daemon identity → insert immediately after §Multiplayer Daemon Platform (line ~149). Natural follow-on: that section already says "daemons are public, forkable, summonable agent identities defined by soul files" — §Daemon identity formalizes the identity primitive.
- §Economic architecture → insert immediately before §Uptime And Alarm Path (line ~296). Economics is a system-wide layer; sits well before the uptime concern.

---

## §Daemon identity

**Goal:** Daemons are persistent named entities with durable identity, not per-spawn anonymous workers. Hosts design specific daemons via the tray; summoning activates a named identity, not a generic runtime.

**Principle — identity is `(user_id, daemon_name, soul_version)`.** Every daemon belongs to a user. Each has a human-readable name and a `soul.md` file authored by the host. Souls carry personality, expertise, constraints, voice, disposition toward tools and methods. The soul file is the daemon's system prompt at summon time, subject to per-node soul-policy (below). Souls are persistent across restarts, editable, versioned.

**Authoring surface.** The host's system tray is the primary authoring UX for daemons — list active + inactive daemons, mouse-over to edit soul.md, create-new-daemon-by-writing-a-soul. Creating a soul creates an inactive daemon (exists, named, dormant); summoning activates it. No anonymous daemons by default — every daemon has a name and a soul. Per `project_daemon_souls_and_summoning`.

**Per-node soul-policy (4 shapes).** Nodes are authored with explicit policy for how the daemon's soul interacts with their node. Node authors choose one:
1. **`allow_host_soul`** — daemon runs with host soul unchanged. Node is soul-agnostic. Likely default for maximum claimer-liquidity.
2. **`append_node_header`** — host soul runs; node prepends a temporary node-specific instruction header. Host identity preserved, node context layered.
3. **`insist_node_soul`** — node provides its own soul; host soul is ignored. Anonymous-work pattern; node author controls persona entirely.
4. **`hybrid`** — host soul + node header + node-specific overrides. Node author defines the merge.

**Economic role.** Soul quality is an economic input. Node designers who stake gate bonuses want specialized daemons claiming their nodes — a well-tuned scientist daemon hits more gates than a generic worker. Hosts iterate souls to become valuable on specific node classes. "Alice's scientist daemon" becomes a known entity. Nodes that `insist_node_soul` level the playing field (anonymous work); nodes that `allow_host_soul` invite competition on identity-quality. See §Economic architecture for how soul-quality flows into payouts.

**cloud-droplet is the first default-souled daemon.** The self-host migration (2026-04-20) introduced `cloud-droplet` as an executor identity distinct from `host`. Under the daemon-identity model, cloud-droplet becomes a named default-souled daemon in the registry — not a distinct identity path. Migration plan: when daemon roster ships, register `cloud-droplet-1` with a minimal default soul.md and route the existing cloud-worker through the same summon lifecycle as any other daemon. Prevents a future rewrite of the cloud-worker surface.

**user-sim personas are the dogfood.** User-sim personas (Maya, Devin, Priya, etc., per `project_user_sim_persona_driven`) are already named-persona daemons in spirit — persistent characters with personality, passion projects, and self-directed exploration. When daemon-roster ships, those persona files become the first real soul.md files. Success criterion for the MVP: user-sim personas boot from `soul.md` without rewrite of the user-sim harness. That's how we know the primitive works before real users touch it.

**Extends / interacts with:**
- `§Multiplayer Daemon Platform` — formalizes the "daemons are public, forkable, summonable agent identities" claim with a concrete identity primitive.
- `project_daemons_are_multi_tenant_by_design` — identity is `(user, daemon_name, soul_version)`, not just `(user, daemon_id)`.
- `project_user_sim_persona_driven` — personas are proto-souls; the identity model generalizes them.

**Open architectural questions (decided during scoping):**
- Soul versioning: does editing the soul create a new version? Does old work retroactively reflect new soul? (Memory suggests immutable after publish, with new versions forking.)
- Soul marketplaces: can a host publish their soul for others to adopt or remix? (Probably yes, wiki-style, with attribution — ties into the economic-architecture attribution chain.)
- Anti-homogenization: if everyone clones "Alice's scientist," does gate-bonus race collapse? Platform may need diversity-weighting in claim matching.
- Default soul: what shape for users who want to run workflows without authoring one? Probably a minimal generic helper persona.
- Soul-spoofing: anti-spoof at claim time — cryptographic soul-fingerprint in claim metadata. Important once gate bonuses turn on; thin threat today.

Implementation-level specs live in `docs/vetted-specs.md` under the four daemon-souls deferred entries (roster + soul.md authoring surface, per-node soul_policy field, branch-contribution ledger, claim-time soul-fingerprint).

---

## §Economic architecture

**Goal:** A workflow platform where money flows to the people who created value — designers (permanent creators of nodes + branches), claimers (daemons that execute runs), attribution lineage (remix ancestors), bug reporters (design-participation), and real-world-outcome evaluators (external signals). The platform provides primitives; users compose distributions.

**Principle — designer and escrow-setter are distinct roles.**
- **Designer** (node/branch author): permanent immutable identity on the artifact itself. Attribution chain carries multi-generation lineage. Designer identity does not change when others run the work.
- **Escrow-setter** (requester/staker/poster): per-request role. Stakes money to tempt a daemon for one specific run. Each request is a new escrow with its own distribution rules.

Staking escrow does not make the setter the designer. Escrow is a temporary "money to tempt a daemon" layer bolted on top of the permanent artifact. The same node run by two different requesters can have two totally different distributions. This separation is load-bearing for the architecture; conflating the two collapses the economic model. Per `project_designer_royalties_and_bounties` §"Two distinct roles".

**Principle — escrow is open-ended by design.** Escrow-setters can express any distribution they want with the split primitives: cut-to-claimer-on-completion, cut-to-designer(s), gate-bonus pool, checkpoint partial-credit, real-world-outcome bonus, patronage, attribution-chain lineage cut, bounty-pool donation, platform-take. Platform provides a small template library for common patterns (standard / OSS-commons / patronage / real-world-outcome / quality-weighted) so non-crypto-native requesters don't design from scratch. Setter can always customize. Platform does NOT mandate one canonical pattern.

**Principle — designer guardrails are platform-provided, not per-escrow.** Designers can attach a few knobs to their own work to prevent unwanted free-riding:
- **Minimum-royalty flag**: the only hard floor. "This node cannot be posted with less than X% to the designer." Rejected at escrow-setup. Default 0% (free commons); designers opt in. Per-tier (paid-market / free-queue / host-internal) for public work that wants a paid-tier royalty without blocking free adoption.
- **Private / access-gated node**: only specific users can post escrow.
- **Unpublished node**: designer-workspace only.

Most designers who want broad adoption pick 0% default and earn via voluntary escrow cuts + attribution-chain decay on remix lineage. Designers who want to monetize directly set the floor.

**Principle — attribution chain is durable, multi-generation, decay-weighted.** Fork/remix/patch_branch preserves parent lineage. When Alice designs A, Bob remixes as B, Carol remixes as C, and C earns a real-world bonus, Carol + Bob + Alice each get a cut. Suggested decay: Carol 60%, Bob 25%, Alice 10%, remainder to platform/bounty-pool. Specific weights are a platform parameter, not per-user. Chatbots auto-attribute on remix; stripping the chain requires deliberate declaration, not silent silencing.

**Principle — real-world outcomes are one escrow-template, not the pattern.** `project_real_world_effect_engine` names real-world outcomes (paper published, MVP shipped, contract awarded) as the product soul. Setters who want to stake on external signals use the real-world-outcome Evaluator template. Setters who don't care about externalities stake on completion. Platform ships ~5 common outcome-type evaluators; setters can author custom ones. The distribution of released outcome-bonus is whatever the setter declared — "only finisher" or "split across all contributors weighted by navigator's fair-distribution calc" or anything else.

**Principle — bug reports are design participation.** `wiki action=file_bug` handles bugs, feature ideas, and design proposals — one channel, one vetting flow. Chatbots read repo + PLAN.md before filing. Navigator does two-pass vet (safety + strategy). Reshaped filings still credit original filer. Reporter earns bounty from the 50%-of-1%-platform-take pool when the fix ships + passes stability period. Optional `github_handle` attaches `Co-Authored-By` trailer on commits for public GitHub credit. Reporter gets money AND reputation.

**Platform treasury allocation — 50/50 of the 1% take.** Per `project_monetization_crypto_1pct` the platform takes 1% of all transactions. Half of that flows to the bug/feature bounty pool; half stays in treasury for infra + host succession + DAO runway. Pool grows with volume. Depletion semantics TBD (defer payout, pro-rate, or LIFO priority).

**Navigator as fair-distribution adjudicator.** Navigator is the only role that sees all contribution layers (dev/verifier/lead don't see the full economics tree). Two distinct adjudication classes:
- **Per-run payouts (setter-declared):** navigator applies the setter's declared rules to observed contribution data. If setter said "only finisher," no fair-weighting — route to finisher. If setter said "split across all contributors," fair-weight with observed step-counts, earned-fractions, attribution lineage.
- **Platform-set payouts (bug-bounty + navigator-reshape splits):** navigator adjudicates from platform defaults. 50%-of-1% bounty pool is platform's money; navigator routes by heuristics.

**Navigator's fairness biases:** over-credit earliest original author (attribution debt compounds with each generation); under-credit pure-relay work (shallow remixes that added nothing); weight novelty + structural contribution higher than surface-level edits; reshape-at-vet earns navigator a split-proportional to reshape-depth (no reshape = no navigator cut, full reshape = substantial cut).

**Extends / interacts with:**
- `project_monetization_crypto_1pct` — the 1% take is the funding source; this architecture adds the 50/50 split.
- `project_node_escrow_and_abandonment` — escrow structure now has designer-royalty + attribution-lineage slots on top of claimer-payment + gate-bonuses + checkpoint-partial-credit.
- `project_daemon_souls_and_summoning` — branch-level multi-daemon distribution extends naturally to designer-royalty distribution across author-lineage.
- `project_convergent_design_commons` — attribution chain makes "remix = collaboration" economically real, not just culturally.
- `project_real_world_effect_engine` — real-world-outcome staking is the direct economic incentive for the product soul.
- `project_bug_reports_are_design_participation` — the filer-reputation track navigator now maintains (`.agents/filer-reputation.json`) feeds this architecture.

**Open architectural questions (decided during scoping):**
- Exact decay function for multi-generation remix weights.
- Dispute resolution path for contested attributions.
- Stability-period duration for bug-bounty qualification (7d vs 30d vs per-class).
- Low-quality-report rate-limiting + reputation to prevent bounty-farming.
- Pool depletion semantics.
- Tax / legal implications of platform-initiated payouts (deferred until paid-market flag enables).

Implementation-level specs live in `docs/vetted-specs.md` under the five economic deferred entries (flexible escrow splits, minimum-royalty enforcement, attribution chain primitive, real-world outcome evaluator hook, bug-bounty tracking + GitHub attribution, fair-distribution calculator).
