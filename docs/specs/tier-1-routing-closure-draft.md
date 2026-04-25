# Tier-1 Routing Investigation — Closing Paragraph (Draft)

**Date:** 2026-04-25
**Target:** Closing paragraph for the live wiki page `tier-1-investigation-routing-resolver`. Migrates to wiki via `wiki action=write` once the cloud daemon redeploy lands (STATUS Task #32 wiki migration).
**Scope:** Closing paragraph only. Body updates are navigator's domain.

---

## Closing Paragraph

The Tier-1 routing investigation remains the highest-leverage upstream primitive in the active queue. Per the `2026-04-23` navigator full-corpus synthesis, BUG-019, BUG-021, and BUG-022 are almost certainly one root cause expressed as three symptoms — the conditional-edge resolver reading stale state, capturing closure-bound state at compile time, or mismatching the `END` sentinel during normalization. A single 1-2 day investigation closes all three at once (Case A) or two of three (Case B); either resolution unblocks every downstream iterative pattern the platform depends on, including agent teams, retry loops, and review-revise cycles. Without working conditional termination, no iterative agent pattern is viable, and iterative is the whole point of agent teams.

The investigation has now received external validation. On 2026-04-25, an outside technical user (Mark, see `MARK-W1` in `.claude/agent-memory/user/personas/mark/wins.md`) independently surfaced this same routing concern by reading the engine architecture — without prompting, without prior context, and without being directed to the internal investigation page. He reached the same conclusion the internal engineering track had already reached. This cross-domain validation is strong empirical evidence that the concern is load-bearing enough to be discoverable by the platform's target user, not an internal artifact, and that the architecture is transparent enough for a tier-2 AI-developer to read critically. Mark's finding is cited here as external corroboration that the routing resolver is the correct primitive to harden first. The investigation is sequenced after the provider-stack RCA bundle (a daemon with zero reachable providers cannot validate routing fixes) and before sub-branch invocation work (BUG-005), since sub-branches will compose conditional routing internally.
