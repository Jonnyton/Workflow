# Pair Convergence: #55 external-PR bridge ↔ #52 file_bug routing + CONTRIBUTORS.md + #48 ledger + canary spec + anti-spam invariants

**Date:** 2026-04-25
**Author:** navigator
**Pair:** dev-2's #55 external-PR bridge proposal (`docs/design-notes/2026-04-25-external-pr-bridge-proposal.md`) ↔ five substrate dependencies enumerated in lead's brief.
**Note on numbering:** "Task #55" refers to the design proposal (TaskList Task #55 completed). NOT to be confused with my navigator-side Task #55 in earlier framings.
**Purpose:** Phase D coverage. Verify cross-doc composition with the now-rich substrate; surface gaps.

---

## Stamp

**PAIR CONVERGES WITH ONE MATERIAL FLAG.** Four of five cross-checks pass cleanly. One material gap: **#55 assumes `kind="patch_request"` has been added to `_VALID_BUG_KINDS` by Task #52, but Task #52 landed without that addition.** The enum at `universe_server.py:12979` still reads `{"bug", "feature", "design"}` — `patch_request` is missing. This is a small dispatch gap (one frozenset entry + new directory + ID prefix), not a design flaw — but #55 cannot ship until the gap is closed.

Three substantive new opens surface from the pairing.

---

## 1. Per-substrate cross-check resolution

| Substrate | Resolution |
|---|---|
| **#52 file_bug kind routing (commit `1618285`)** | **MATERIAL FLAG.** #55 §1 says: "Once #52 lands, `kind='patch_request'` extends `_VALID_BUG_KINDS` (4-element set)." But the actual #52 landing extended the set to 3 elements (`bug`, `feature`, `design`) — patch_request is NOT in the enum. Verified directly at `universe_server.py:12979`: `_VALID_BUG_KINDS = frozenset({"bug", "feature", "design"})`. **Resolution path:** small follow-on dispatch adds `patch_request` to enum + creates `pages/patch-requests/` directory + adds `PR-` ID prefix to the kind→category map at line 12889 (today's map only has bug→BUG). The map structure already supports this; #55's §1 just over-anticipated when it would land. |
| **CONTRIBUTORS.md surface (committed `87e96bb`, AGENTS.md Hard Rule #10)** | **CONVERGES.** §5 explicitly says: "consistent with CONTRIBUTORS.md (committed `87e96bb`) shape — Co-Authored-By lines reference GitHub handles even before an actor identity link exists. The link upgrades the contribution from handle-only to actor+handle." That's exactly the right composition: `actor_id="anonymous" + actor_handle=<login>` until linked, then upgrade to actor+handle on opt-in via the new `wiki action=link_github_handle` verb. This **closes E17 (GitHub-handle missing case) from v1 vision** at the design layer. |
| **#48 contribution ledger** | **CONVERGES with one structural sharpening.** §6 closure table specifies first-merge-wins for `code_committed` event emission: "First emit only. Note in attribution-layer specs that `code_committed` is once-per-merge-cycle." This is the right semantics, but the attribution-layer-specs §1.3 (navigator) doesn't yet name the once-per-merge-cycle invariant. **Filing as [PENDING attribution-specs-v2]:** add to §1.3 trigger condition that `code_committed` fires exactly once per (PR-id, merge-event), with re-merges after force-push being noops. Small cross-doc clarification; not a design-doc gap but worth the explicit invariant in the navigator-side spec. |
| **canary→file_bug spec (cross-doc seam)** | **CONVERGES — both consume `_wiki_file_bug` cleanly without double-filing.** Dedup primitive at `universe_server.py:13157-13186` is the safety net: if a canary fires RED on the same surface a PR is filed against, the Jaccard similarity check catches the duplicate at filing time and routes to cosign rather than minting a new bug. **However:** the `tags=source:canary` vs. `tags=source:github_pr` differentiation means similar bugs from different sources DON'T currently cosign automatically — they'd land as separate filings unless titles + bodies are sufficiently similar. **Mitigation: rely on dedup primitive's similarity threshold (Jaccard ≥ 0.5) as-is.** If observed pain emerges (canary + PR for same bug land separately), revisit with explicit source-aware dedup. |
| **Anti-spam invariants** | **CONVERGES — opt-in via `patch-request` label is the auth gate.** PRs without the label generate no patch_request (no spam vector). The carve-outs (`docs-only`, `format-only`, `hotfix`, `dependabot/*`, `renovate/*`, `pre-commit-ci/*` + automation allowlist) prevent automated PR floods. **Composition with #66 evidence_refs:** the question was "PR body has no evidence_refs by default — how does feedback_provided fire?" Answer: **feedback_provided does NOT fire from a PR-bridge filing.** The PR is a `code_committed` source (surface 3), not a `feedback_provided` source (surface 5). Surface 5 fires only when a gate-series evaluator cites a wiki artifact in its decision. PR body content as opaque markdown doesn't auto-emit feedback events. Anti-spam invariant preserved: PR body content earns code_committed credit at merge (per surface 3), not feedback_provided credit at filing. |

**Net composition health:** 4 of 5 clean; 1 material gap (the enum extension) is a small dispatch follow-on, not a design issue. Bridge cannot ship without the enum addition; design otherwise sound.

---

## 2. Three substantive new opens from the pairing

1. **Carve-out → contribution-event policy.** §4 defines carve-outs (docs-only, format-only, hotfix, automation allowlist) that **skip patch_request creation entirely**. But what about `code_committed` events on merge for those PRs? A docs-only PR by a real human still merits design-credit; skipping the patch_request shouldn't skip the contribution-credit. **Recommendation:** decouple. patch_request creation skipped if carve-out matches; `code_committed` event STILL fires on merge regardless of carve-out (just without a wiki page binding it). The PR URL serves as `source_artifact_id` directly. **Implementation-time clarification.** Open Q for #55 v2 OR worth pinning before implementation to avoid the docs-only-author-loses-credit failure mode.

2. **Multi-repo federation deferred — but multi-org single-repo** (e.g., a fork's PR back to the original repo) **isn't named.** Q3 covers multi-repo (single namespace, repo recorded in tags). But what if user A opens a PR from `userA/workflow-fork#42` against `host/workflow#1500`? The `repository.full_name` field carries `host/workflow`; the PR author is `userA`. Tags record both. **Composition with #66 (TypedPatchNotes route_history):** TypedPatchNotes' route_history is for in-graph routing — it doesn't carry "this patch came from a fork." But the wiki page tags do. **Implementation-time concern:** verify the dedup primitive treats fork-PRs and direct-PRs against the same repo as eligible-for-cosign (same surface, different origin). If they're not currently treated as similar, the Jaccard check needs source-aware tuning. Filing as [PENDING fork-pr-dedup-test].

3. **Webhook receiver mounting on existing universe_server HTTP surface.** §2 says "endpoint path: `POST /webhooks/github` mounted on the existing universe_server HTTP surface." This implies universe_server gains a non-MCP HTTP route — currently the server is exclusively MCP. **Open Q:** does this require an HTTP route registration mechanism that universe_server doesn't currently surface? FastMCP supports custom endpoint mounts, but the existing universe_server doesn't use them yet. **Recommendation:** verify FastMCP's `add_route` or equivalent mechanism is available; if not, the receiver may need to live as a separate process (smaller blast radius anyway). Implementation-time concern; flag for [PENDING #55-impl-http-mount-mechanism].

---

## 3. Implementation-time constraints

To land in the dispatch task's verification list:

- **Enum extension dispatch** — small task: add `patch_request` to `_VALID_BUG_KINDS`, extend kind→category map at line 12889 (`patch_request: ("patch-requests", "PR")`), create `pages/patch-requests/` directory. Test: `_wiki_file_bug(kind="patch_request", ...)` lands in the right directory with `PR-NNN` ID. **MUST land before #55 implementation.**
- **HMAC-SHA256 signature verification** — webhook receiver verifies `X-Hub-Signature-256` header before payload processing. Reject unsigned/bad-sig with 401. Standard GitHub webhook pattern; secret in `$HOME/workflow-secrets.env`.
- **HMAC secret rotation** — secret rotation pattern not addressed in #55. Need: support multiple valid secrets during a rotation window (current + previous), so rotation is zero-downtime. Filing as [PENDING #55-impl-secret-rotation].
- **GUID-based replay protection** — bounded FIFO dedup table (N=1000). Test: same GUID delivered twice returns 200 + `duplicate_delivery` status second time.
- **Carve-out + contribution-event policy** — per §2 open #1, decouple carve-out skip from contribution-event emission. Test: docs-only PR merges → no patch_request, but `code_committed` event emitted with PR URL as source_artifact_id.
- **Author identification handle threading** — when `link_github_handle` opt-in flow lands (separate dispatch), retroactive backfill of historical PRs is out-of-scope for v1 (per #55 §5). Test: PR author opts in; future PRs from same handle emit code_committed with linked actor_id; past unlinked PRs still tagged with handle but actor_id="anonymous".
- **Action filter test coverage** — only the 5 specified actions (`opened`, `labeled`, `closed merged=true`, `closed merged=false`, `reopened`) trigger bridge logic; all others (`synchronize`, `assigned`, `review_requested`, etc.) no-op. Test each.
- **Cross-doc seam with rollback** — per pair-read #65 §2 (cross-doc seam between surgical rollback and canary→file_bug), the same composition concern may apply here: if a PR is auto-rolled-back via #57, does the wiki status update from `merged` to a rollback-aware state? **Recommendation: add `status: rolled_back` transition to #55 §6 closure table.** Filing as [PENDING #55-v2-rollback-status-transition].

---

## 4. Roadmap deltas

Two updates for v2 vision / roadmap:

1. **Phase D item 17 (External-PR bridge)** — designed. Implementation depends on the small enum-extension dispatch (1-line frozenset change + directory creation). Blocks on:
   - Enum extension dispatch (small, ~30 min).
   - `link_github_handle` MCP verb implementation (separate dispatch).
   - HTTP receiver mounting mechanism investigation.
2. **Cross-doc seam with rollback (Phase E item 24c)** — when surgical rollback lands, #55 §6 closure table needs a `status: rolled_back` transition for PRs whose merged commits are subsequently rolled back. Filing as [PENDING #55-v2-rollback-status-transition].

---

## 5. Closure of Phase A + Phase D + Phase E gate-substrate design

Per K (#65, surgical rollback) + L (#66, named-checkpoint) + M (this, #55), **three Phase substrates closed end-to-end:**

| Phase | Items closed |
|---|---|
| Phase A gate substrate | items 4a, 4b, 5a/b/c, 7 (per L); items 2 (impl), 6 (impl in flight) |
| Phase D economic loop | items 17 (external PR bridge — this), 19 (bounty calc — designed), 21-22 (negative events / rollback truth — designed via #57) |
| Phase E rollback substrate | items 23-25 (per K) |

**Remaining design slots:** Phase A items 1 (storage authority refactor — Task #69 just dispatched per lead) and 3 (lookup_canonical — Task #59 in flight). **All other Phase A/D/E primitives have landed designs.** The substrate is genuinely saturated.

---

## 6. References

- Audit target: `docs/design-notes/2026-04-25-external-pr-bridge-proposal.md` (#55, dev-2 — Task #50 completed).
- Substrate cross-checked:
  - `_wiki_file_bug` primitive at `universe_server.py:13102-13186` + kind routing at `:12889` + enum at `:12979`.
  - dev's #52 file_bug kind routing (commit `1618285`).
  - CONTRIBUTORS.md surface (commit `87e96bb`).
  - `docs/design-notes/2026-04-25-contribution-ledger-proposal.md` (#48 — surface 3 `code_committed` event).
  - `docs/design-notes/2026-04-25-canary-to-patch-request-spec.md` (canary spec — structural twin per #55 §1).
  - `docs/design-notes/2026-04-25-attribution-layer-specs.md` (navigator — surface 3 `code_committed` weight + emission).
  - `docs/design-notes/2026-04-25-typed-patch-notes-spec.md` (#66 — TypedPatchNotes evidence_refs check).
- Pair-reads completed: `docs/audits/2026-04-25-pair-{54-vs-56,50-vs-56,57-surgical-rollback,58-named-checkpoint}-convergence.md` + `docs/audits/2026-04-25-audit-53-gate-route-back-solo.md`.
- v2 vision Phase D phasing: `docs/design-notes/2026-04-25-self-evolving-platform-vision-v2.md` §6.
