# Purpose

- Purpose: restore exact-original Scorched Tanks browser playability without substituting the fallback/remake.
- Provider: codex-gpt5-desktop.
- Branch: codex/scorched-tanks-browser-pwa-live-main.
- Base ref: origin/main at session start; branch is currently divergent and must be reconciled before PR.
- STATUS row: Scorched AROS exact-original proof.
- Worktree: C:\Users\Jonathan\Projects\Workflow-scorched-pwa-live (legacy pre-`wf-` name; do not use `Workflow-scorched-pwa-live-main`).
- PR expectation: draft PR #162 until exact original reaches gameplay, mouse input fires, a shot hits a tank, visible state changes, sound is verified, and opposite-provider review returns approve/adapt.
- Ship condition: exact original game is playable through the browser/user path with cited media provenance and compatibility proof.
- Abandon/defer condition: no legal/free firmware path can reach gameplay; leave host-supplied licensed Kickstart path and AROS blocker documented.
- Memory refs: none found in `.claude/agent-memory/` or `.agents/activity.log` for Scorched as of 2026-05-02.
- Related implication refs: `STATUS.md` Scorched concern, `docs/design-notes/2026-04-30-exact-classic-game-browser-runtime.md`, `docs/design-notes/2026-05-01-classic-game-endpoint-delivery.md`, `WebSite/site/static/play/scorched-tanks/SOURCES.md`, `WebSite/site/static/play/scorched-tanks/compatibility.json`, `output/online-research/`, `WebSite/site/output/sae-smoke/`, `WebSite/site/output/ejs-puae/`.
- Pickup hints: do not claim success from title screens, Workbench, nonblank canvas, or fallback game; v1.77/v1.85/v1.90 and v0.95 all still fail under bundled/latest AROS, older AMOS-for-Windows AROS reset-loops under SAE, and a v1.77 `amos.library` DF1 shim still fails. `node output\online-research\verify-scorched-launcher-routing.mjs` now verifies hosted/user Kickstart routing only; it is not gameplay proof.
