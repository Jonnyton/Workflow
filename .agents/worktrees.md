# Worktrees

## 2026-05-02

- Created purpose record for `C:\Users\Jonathan\Projects\Workflow-scorched-pwa-live`; branch `codex/scorched-tanks-browser-pwa-live-main`; provider `codex-gpt5-desktop`; lane `Scorched AROS exact-original proof`; current state `IN-FLIGHT`, draft PR #162 only until exact-original gameplay proof and opposite-provider review.
- 2011 AMOS-for-Windows AROS browser-SAE rerun used ROM hash suffix `9557fd50`; v1.77 A500/A1200 and v0.95 A500 reset-looped before gameplay.
- v1.77 `amos.library` DF1 shim still failed: low-memory A500 reports not enough memory; A500 1 MB chip + 2 MB fast raises `0x0100000F`.
- Launcher routing harness added: default `auto` probes hosted licensed Kickstart then falls back to AROS on 404; strict hosted mode fails loudly when absent; provisioned hosted ROM injects without AROS fetch. This proves the capability primitive only, not Scorched gameplay.
