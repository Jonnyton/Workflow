# Design-Proposal Pattern — Convention Doc

**Date:** 2026-04-25
**Author:** dev-2
**Status:** Convention. Lead/host ratifies; future devs follow.
**Source:** Validated across 11 design docs in one autonomous run (Tasks #47/#48/#53/#54/#55/#56/#57/#58/#59/#66 + #67 v2 amend on #53). Memory at `.claude/agent-memory/dev-2/feedback_design_proposal_pattern.md` captures the abridged form; this doc is the canonical surface.

---

## 1. The 5-move pattern

When the lead routes a design-proposal task ("propose ONE schema / contract / primitive, justify, surface open questions"), apply this 5-move recipe in order:

### Move 1 — Investigate-first scope-message

Before drafting, read the audit / vision doc / dev's pair-work the proposal builds on. Pull concrete file paths + line numbers. Then send the lead a scope-message naming:
- The recommendation in 2-3 sentences.
- The top tradeoff axis that decides it.
- Rejected alternatives + why each fails.
- 5 open Q previews with recommended answers.

**Always wait for lead sign-off before drafting.** Lead's response routinely adds 2-3 substantive constraints — folding them in pre-draft saves 30-60 min of re-edit per doc.

**Example (this session):** Task #54 runner branch_version_id bridge initially recommended Option (a) dual-arg overload of `run_branch`. Lead's pre-draft note pivoted to navigator's §D sibling-action recommendation. Pivot honored cleanly; full draft adopted `run_branch_version` sibling action with explicit citation. Without the scope-message round, the v1 draft would have shipped the wrong shape, requiring a v2 amend later.

### Move 2 — Tradeoff analysis with rejections

In the proposal body: name 2-4 alternatives explicitly. Reject each with one-sentence reasoning. Use a tradeoff table only when 3+ axes meaningfully differ; tables with one obvious winner waste reader attention.

**Example:** Task #54 §1 surveyed three options before recommending the sibling-action winner — option (b) "explicit redirect verb" rejected because re-creating a def from snapshot defeats immutability; option (c) "extend canonical to also store def_id at bind" rejected because two-pointer drift is inevitable. Both rejections one-liner, the dual-arg-vs-sibling tradeoff got a 9-row table where axes diverged.

### Move 3 — Crisp single recommendation, justified

Pick ONE path. Don't offer a buffet. Show why the others fail in Move 2; show why THIS one wins in load-bearing detail.

**Example:** Task #56 sub-branch invocation had 4 sub-decisions (MCP exposure, branch_version_id pattern, failure propagation, pool starvation). Each got a single recommendation with explicit "rejecting alternative because…" reasoning. None of the 4 sub-decisions punted to "it depends."

### Move 4 — 5 honestly-open questions surfaced

Five is the typical count. Pad below with 3-4 if scope is small (#59 resolve_canonical = 3 open Qs); add a 6th-7th honestly-open if scope is large (#56 = 7).

Mark which Qs are CLOSED by lead's pre-draft notes vs TRULY open. Closed Qs still appear with the rationale (helps future readers); truly-open Qs name a recommendation + a reasonable counter-argument so the lead/host picks fast.

**Example:** Task #57 surgical rollback originally had cycle-detection as Q3 OPEN. Lead's pre-draft note promoted it to MUST-have requirement (depth ≤ 3 AND visited-set, not either-or). The promoted constraint surfaced in §3 as a hard requirement, NOT as an open question. Open-Qs section then noted: "Q3 cycle-detection-config-tunable max-depth: closed."

### Move 5 — SHIP after lead's quick approval round

After the full draft, message the verifier with:
- File path + line count.
- Required-sections checklist confirming all are present.
- Lead's pre-draft notes honored line-by-line.
- Convergence verified (sibling proposals + cited references).
- Gate-1 status (docs-only / tests-pass / ruff-clean as applicable).

Then immediately self-claim the next task in the standing queue. Don't idle between proposals; momentum compounds across docs in a series.

---

## 2. When to apply / when NOT to apply

### Apply when

- Bounded design proposal with multiple plausible answers (lead phrases task as "propose ONE / pick a recommended / sketch the design").
- Schema / contract / primitive design — the kind of work that becomes a follow-on dispatch for code.
- Multi-doc series where each cites siblings (this session's 11-doc run is the exemplar).

### Don't apply when

- Pure audit ("audit, survey, gap analysis") — use the audit-shape pattern from `feedback_audit_style_pattern.md` instead. Tables options without picking; declines to design.
- Pure code refactor — no design surface, no opens worth surfacing. Implementation discipline is different (test-coverage focus, not options-surfacing).
- Already-ratified primitive — if the design exists and just needs implementation, this pattern is overhead. Ship the impl.

The signal: does the brief say "propose ONE / pick a recommended / sketch the design"? If yes, this pattern. If brief says "audit / survey / gap analysis," use the other.

---

## 3. Cross-doc convergence patterns

When multiple proposals in the same series cite each other, **the convergence-loop sharpens output.** Cite predecessors AND successors:

- Predecessors = the audit / vision doc / sibling proposals this builds on.
- Successors = downstream consumers that will use this primitive.

Series cohesion comes from these cross-references, not from any monolithic spec. Each doc lands as a unit; the lead can commit individually or as a cluster.

**Pair-reads are a force multiplier.** When navigator/dev pair-reads a proposal mid-flight (this session's #62/#65 pair-reads on #59/#60/#66), they catch latent inconsistencies BEFORE verifier gate-1. Lead-routed pair-reads are the highest-leverage feedback channel for design work; protect them by responding fast to pair-read findings.

**Example (this session):**
- #47 §3 named the `resolve_canonical` read primitive → #59 implemented it.
- #48 §1.4 specified `feedback_provided` event shape → #66 §6 + #67 §9.3 made it consumable via typed `EvidenceRef`.
- #53 §3 cycle-detection magic-key → #66 §2 lifted to typed `route_history` field → #67 §9.2 documented the engine semantics-unchanged delta.
- #54 (committed `dc7d2cb`) sibling-action pattern → #56 §3 mirrored as `invoke_branch_version_spec` field.
- #57 closure-walk used `branch_versions.parent_version_id` (#54 schema) + `branch_definitions.fork_from` (existing migration).

11 docs, ~30 cross-citations, zero contradictions. The series cohered because every doc explicitly named what it built on AND what would consume it.

---

## 4. Output discipline

### What to keep terse

- Rejected alternatives — one sentence per rejection, no diagrams.
- Schema columns whose purpose is obvious from name.
- Migration steps that follow the standard 4-step additive pattern (Step 0 schema add → Step 1 backfill → Step 2 dual-write → Step 3 readers prefer new).

### What to expand

- Load-bearing decisions — show your reasoning, especially where a future reader might second-guess.
- Composition with siblings — explicitly verify non-impact OR document required updates.
- Validation rules — strict-at-construction OR strict-at-consume; name the discipline explicitly.
- Open questions with truly-open status — give recommendation + counter-argument so picker has both.

### Sweet spot: 150-300 lines

- **Below 150:** likely under-justified. The reader can't tell why this option won; second-guessing emerges.
- **Above 300:** likely over-designing. The proposal is doing implementation work the dispatch hasn't authorized; collapse the over-spec into "what this proposal does NOT cover" or split into a sibling proposal.

This session's distribution: #59 resolve_canonical 169 lines (smallest, focused MCP action); #56 sub-branch invocation 277 lines (largest, 4 sub-decisions). Median ~210. None hit 350+; none dropped below 150 except where scope was genuinely smaller.

---

## 5. Anti-patterns

### Scope creep into adjacent primitives

When a related primitive comes up mid-draft, the temptation is to absorb it. Resist; cite + cross-reference instead.

**Example:** Task #57 surgical rollback could have absorbed the canary-to-patch_request seam (since rollback re-uses canaries). Instead, §8 cited `docs/design-notes/2026-04-25-canary-to-patch-request-spec.md` (navigator's prior work) explicitly. Result: two coherent docs each scoped tightly, instead of one bloated proposal blurring two concerns.

### Buffet-of-options recommendations

Phrases like "we could do A, or B, or C — host decides" are scope failures unless the brief explicitly says "survey options." A design proposal picks ONE.

**Example:** Task #54's three rejected options + one chosen sibling-action winner. NOT "options A/B/C are each viable; lead picks." The proposal made the call; lead ratified or pushed back.

### Deferring everything to v2

Some opens MUST be answered to ship. Deferring all hard questions to "future v2" leaves the proposal toothless.

**Example:** Task #57 cycle-detection was OPEN in scope-message; lead promoted to MUST-have. Resulting proposal had a hard requirement instead of a deferred Q. v1 ship-ready, not "v2 will figure it out."

The discipline: each open Q has a recommendation + counter; truly-open Qs are bounded; load-bearing-must-answer Qs get pre-draft promotion to hard requirements.

---

## 6. Reusable section template

For any new design proposal, the 6-section shape works. Adjust per scope:

1. **Recommendation summary** (1 paragraph) — pick + top tradeoff axis. The brief's "what" answered in 3-5 sentences.
2. **Schema / shape / signature** (1-2 pages) — concrete DDL / dataclass / function signature with field-by-field rationale.
3. **Tradeoff table** (1 page) — compare picked option vs 2-3 rejected. Use rows = axes; columns = options. Skip if only 2 options or one obvious winner.
4. **Migration / implementation sketch** (1 page) — 3-4 step additive plan. Step 0: schema add. Step 1: backfill (if needed). Step 2: dual-write or reader cutover. Step 3: deprecate old path.
5. **Composition with sibling proposals** (1/2-1 page) — name 3-5 sibling proposals; verify non-impact OR document required updates.
6. **Open questions** (1/2 page) — 3-5 items. Each closed-by-lead-note OR truly-open with recommendation + counter.

Plus boilerplate front-matter (date / author / status / builds on / scope) and trailing references list. Total: 150-300 lines.

---

## 7. Open questions (meta — about the pattern itself)

1. **(Truly open) When does the pattern over-formalize?** Heavy convention discipline serves design proposals well, but light-touch primitives (e.g., a single-line schema column) might be over-served by the 5-move ceremony. Recommend: skip Move 1 scope-message for genuinely tiny work (~30-line proposals); but apply Moves 2-5 always.

2. **(Truly open) Pair-read scaling.** The 11-doc series benefited from navigator pair-reads at ~50% density. At 100% density, would lead-bandwidth bottleneck? Recommend: pair-read first 2 in any series for pattern-establishment, then sample 1 in 3 thereafter unless a doc is in a high-risk surface (auth, storage, schema migrations).

3. **(Truly open) Memory-vs-convention split.** This convention doc duplicates content from `feedback_design_proposal_pattern.md` memory. Recommend: memory is the project-internal-quick-reference; convention doc is the citable canonical. When they drift (because someone updates one), the more-recent one wins; quarterly sync to merge updates.

---

## 8. What this convention does NOT prescribe

- **No specific tools.** Whatever editor / linter / search tool gets the job done.
- **No specific verifier protocol.** Each session's verifier setup varies; the SHIP-handoff shape is the constant, not the verifier's gate-checks.
- **No specific lead-protocol details** (e.g., "always wait 5 minutes"). The lead-approval round is variable per lead's bandwidth.
- **No code-style rules** beyond what existing project conventions specify (CLAUDE.md, AGENTS.md). Design-proposal docs follow the same Markdown style as the rest of `docs/design-notes/`.

---

## 9. References

- Memory form (project-internal): `.claude/agent-memory/dev-2/feedback_design_proposal_pattern.md` — abridged version of this convention; quick reference during a design-proposal cycle.
- Sibling pattern: `.claude/agent-memory/dev-2/feedback_audit_style_pattern.md` — the audit-shape recipe; complementary, not overlapping. Use when scope says audit, not design.
- 11 design docs validating this convention (2026-04-25 autonomous run):
  - Task #47 — `docs/design-notes/2026-04-25-variant-canonicals-proposal.md` (208 lines).
  - Task #48 — `docs/design-notes/2026-04-25-contribution-ledger-proposal.md` (208 lines).
  - Task #53 — `docs/design-notes/2026-04-25-gate-route-back-verb-proposal.md` (originally 187, post-#67 amend 297 lines).
  - Task #54 — `docs/design-notes/2026-04-25-runner-version-id-bridge.md` (253 lines, committed `dc7d2cb`).
  - Task #55 — `docs/design-notes/2026-04-25-external-pr-bridge-proposal.md` (193 lines).
  - Task #56 — `docs/design-notes/2026-04-25-sub-branch-invocation-proposal.md` (277 lines).
  - Task #57 — `docs/design-notes/2026-04-25-surgical-rollback-proposal.md` (268 lines).
  - Task #58 — `docs/design-notes/2026-04-25-named-checkpoint-routing-proposal.md` (242 lines).
  - Task #59 — `docs/design-notes/2026-04-25-resolve-canonical-action-proposal.md` (169 lines).
  - Task #66 — `docs/design-notes/2026-04-25-typed-patch-notes-spec.md` (265 lines).
  - Task #67 — v2 amend on #53 (in-place §9 section).
- Companion conventions referenced:
  - `AGENTS.md` "Quality Gates" section (verification structure for SHIP-handoff).
  - `CLAUDE.md` codebase + user instructions.
- Companion principle (project memory): `project_user_builds_we_enable.md` — design proposals should respect the platform-builds-substrate, users-build-content division.
