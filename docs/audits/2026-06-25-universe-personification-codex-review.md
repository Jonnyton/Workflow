# Codex review — universe-personification

- **Date:** 2026-06-25
- **Reviewer:** Codex (cross-provider review; recommended gate for host-directed design)
- **Initial author:** Claude (Opus 4.8) session
- **Under review:** OpenSpec change `universe-personification`
- **PR:** #1372 (draft)

## Verdict: ADAPT

Direction right; **not build-ready for connector behavior**. The first-person host choice is fine. The core problem: security + host-memory boundaries were left partly **prompt-enforced**, which is not a real boundary.

## Context re-check

Directionally coherent with §1 ("summon a mind"), §3 (Tiny / personified intelligence), §7 (soul/org-chart), §9 (voice), §11.1 (T0/T1/T2 identity tiers). **But:** §3 defines SEVEN organs while the draft narrowed personification to "soul + brain + voice," muddying mind/organ/voice. It under-specified the brain anti-collision contract (research-impl ADOPT #3) and the frozen <5K-token tool-schema / trigger-language economics (ADOPT #6/#11): first-person embodiment in `control_station` is advisory MCP prompt behavior, not enforceable host identity isolation.

## Risks (verbatim)

- "Mind IS the personification = soul + brain + voice" drops goals, skills, hands, senses from the composed actor model.
- `control_station` embodiment can degrade tool selection if it expands an already-large behavioral prompt instead of staying compact trigger-language + view metadata.
- "Workflow surface only" cannot be hard-enforced by MCP instructions; Claude/ChatGPT may carry the role forward unless bounded by tests + phrasing.
- First-person persona content is exactly the shape host memories may absorb as a standing preference unless every view + write path carries anti-collision guards.
- Visitor privacy is unsafe if the voice/persona layer receives private-tier brain content and is merely instructed not to reveal it.
- Visitor identity is unresolved: unauthenticated Claude/ChatGPT users must default to T0 unless Workflow has a durable actor binding.
- "No neutral tool-only surface" may conflict with degraded-mode honesty and diagnostics unless failure/fallback speech is specified.

## Required adaptations (gate connector-behavior build)

1. **Rewrite the invariant** — personification = the named interaction PROJECTION of the WHOLE mind; voice expresses, soul governs, brain informs; goals/skills/hands/senses remain part of the mind. Do NOT define the mind as only soul+brain+voice.
2. **Anti-collision requirement** — MCP instructions/tool descriptions + every assembled view say not to save persona/work views into host memory; write paths reject profile-shaped / persona-dossier writes.
3. **Enforcement order** — identity/tier/org-chart filtering in brain assembly + action authorization BEFORE voice/persona rendering; the voice layer only styles already-authorized content.
4. **Visitor actor binding** — no Workflow OAuth → T0 anonymous; durable host/OAuth subject → T1; verified owner OAuth → T2/founder.
5. **Minimal/testable embodiment** — compact trigger-language, no large role-play block, no tool-schema sprawl; Claude/ChatGPT tool-selection regression tests.
6. **Fallback/degraded mode** — on tool failure or no active universe/persona, do NOT invent persona state or continue embodiment from memory; speak honestly.
7. **Add scenarios** — multi-universe owners; visitor private-content probing; host-memory collision; same-chat outside-Workflow non-hijack.

## Disposition

All 7 folded into the OpenSpec change (`proposal.md` / `design.md` / `specs/universe-personification/spec.md` / `tasks.md`) in the same commit as this artifact. PR #1372 remains **draft**; connector-behavior build gated until these land (now folded).
