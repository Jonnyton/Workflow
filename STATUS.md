# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; Concerns host-managed; Work rows delete when landed; Next replaced each session. Forever rule = 24/7 uptime with zero hosts online (see AGENTS.md top-of-file).

## Concerns

- [2026-04-14] Sporemarch fix (b): verify multi-scene overshoot + dispatch-guard retention in next user-sim.
- [2026-04-17] Echoes drift-drafted Scene 1/2/3 still in `output/echoes_of_the_cosmos/story.db`; retest fresh universe vs resume.
- [2026-04-17] 589e1fb REST changes need tests: `/votes/{id}/resolve` forced; `/votes/{id}/ballots` now `{"vote": ...}`.
- [2026-04-17] Privacy mode note landed: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`; 3 host Qs remain.
- [2026-04-18] `add_canon_from_path` sensitivity note landed: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`; 3 host asks remain.
- [2026-04-18] Claude.ai injection note landed: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`; task #15 still blocked.
- [2026-04-18] `fantasy_daemon/author_server.py` alias risk: snapshot export, not sys.modules rebind; fix there if cross-alias drift appears.
- [2026-04-18] Full-platform architecture supersedes phased plan: `docs/design-notes/2026-04-18-full-platform-architecture.md`.
- [2026-04-19] Navigator follow-up: `docs/design-notes/2026-04-19-modularity-audit.md` flags `universe_server`, discovery, and `daemon_server` seams.

---

## Work

Claim by setting Status to `claimed:yourname`. Files is the collision boundary. All Row-X tasks live in `docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Row E deploy — Worker push | CF dash: Workers + route tinyassets.io/mcp* | — | claimed:claude-code |
| Row H — cloud canary + GH-Issue alarm | `.github/workflows/uptime-canary.yml`; `scripts/uptime_canary.py` | — | claimed:claude-code |
| Row I — GHCR image registry | `.github/workflows/build-image.yml` | — | pending |
| Row N — host-indep admin (bills/DNS/secrets) | `docs/ops/host-independence-runbook.md`; `scripts/emergency_dns_flip.py`; `.github/workflows/secrets-expiry-check.yml` | — | pending |
| Row D — Hetzner deploy | `deploy/compose.yml`; systemd units | Row I | pending |
| Row F — 48h smoke + acceptance | `scripts/selfhost_smoke.py` | Row D | pending |
| Row G — canonical-URL docs sweep | specs/audits/SUCCESSION/ui-test | Row F green | pending |
| Row J — state backup | `deploy/backup.sh`; systemd timer | Row D | pending |
| Row K — log aggregation | `deploy/compose.yml` log-sidecar | Row D | pending |
| Row L — auto-restart + watchdog | systemd unit; `scripts/watchdog.py` | Row D | pending |
| Row M — CI deploy pipeline | `.github/workflows/deploy-prod.yml` | Row D, I | pending |
| Mission 10 retest | user-sim | host scope call | claimed:user |
| #19 Memory-scope Stage 2c flag | — | 30d clean | monitoring |

---

## Next

1. **Row E dashboard deploy** (claude-code in flight) → canary both URLs → P0 closes for real.
2. **Row H** (claude-code, queued) — cloud canary + GH-Issue alarm sink. Hard block on 48h acceptance.
3. **Row I + Row N are dispatchable NOW to any provider** — no deps, repo-only scripts + workflows. Codex welcome to claim either.
4. **Row D** unblocks J/K/L/M (the Hetzner-resident rows). Needs Row B + Row I done; Row B landed `e254048`, Row I pending.
5. Subordinated: rename-end-state (post-daemon-economy), #11 API asks, mission retests. Not blocking 24/7 uptime goal.
