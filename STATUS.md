# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; Concerns host-managed; Work rows delete when landed; Next replaced each session. Forever rule = 24/7 uptime with zero hosts online (see AGENTS.md top-of-file).

## Concerns

- [2026-04-20] **Option 1 LIVE 01:50 UTC** 976ba1c. `tinyassets.io/mcp` → 200 canonical; `mcp.tinyassets.io/mcp` → 403 gated. Worker `tinyassets-mcp-proxy` deployed w/ CF Access headers. **Host: rotate Global API Key** (used in session + terminal history).
- [2026-04-20] `test_node_eval::test_record_and_get_stats_roundtrip` pre-existing flake. Passes in isolation, flaky in full suite. Surface, not block.
- [2026-04-17] 589e1fb REST changes need tests: `/votes/{id}/resolve` forced; `/votes/{id}/ballots` now `{"vote": ...}`.
- [2026-04-17] Privacy mode note landed: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`; 3 host Qs remain.
- [2026-04-18] `add_canon_from_path` sensitivity note landed: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`; 3 host asks remain.
- [2026-04-18] Claude.ai injection mitigation work blocked on host-Q batch: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`.
- [2026-04-18] `fantasy_daemon/author_server.py` alias risk: snapshot export, not sys.modules rebind; fix there if cross-alias drift appears.
- [2026-04-18] Full-platform architecture supersedes phased plan: `docs/design-notes/2026-04-18-full-platform-architecture.md` (migrate to PLAN.md candidate).
- [2026-04-19] Navigator follow-up: `docs/design-notes/2026-04-19-modularity-audit.md` flags `universe_server`, discovery, and `daemon_server` seams.

---

## Work

Claim by setting Status to `claimed:yourname`. Files is the collision boundary. All Row-X tasks live in `docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Row D — DO deploy (unstick prod) | SSH to DO Droplet; seed GH secrets | host-ops | pending:host |
| Row F — 48h smoke + acceptance | `scripts/selfhost_smoke.py` | Row D | pending |
| Row G — canonical-URL docs sweep | specs/audits/SUCCESSION/ui-test | Row F green | pending |
| Row J — state backup | `deploy/backup.sh`; systemd timer | Row D | pending |
| Row K — log aggregation | `deploy/compose.yml` log-sidecar | Row D | pending |
| Layer-2 canary script | `scripts/uptime_canary_layer2.py` + `uptime_alarm.py` SOFT_YELLOW | — | pending |
| Mission 10 retest | user-sim | host scope call | claimed:user |
| #19 Memory-scope Stage 2c flag | — | 30d clean | monitoring |

---

## Next

1. **Host-ops (blocking):** (a) SSH to DO Droplet + run `docker compose pull && up -d` to unstick prod — BUG-002 fix is in origin but CI never deployed (Hetzner secrets were absent; now fixed via Task #20). (b) Seed `DO_DROPLET_HOST` / `DO_SSH_USER` / `DO_SSH_KEY` as GH repo secrets to unblock CI auto-deploy. (c) Rotate Cloudflare Global API Key (exposed in terminal history this session).
2. **Option 1 cutover LIVE** (976ba1c, 3b8c216) — `tinyassets.io/mcp` → 200; `mcp.tinyassets.io` → 403 Access-gated. Three-check green confirmed.
3. **Mission queue** when host at visible browser: Priya L1 → Devin M27 → Maya S2.
4. **Layer-2 canary script** — dev-claimable; spec in `docs/design-notes/2026-04-19-layer2-canary-scope.md §2.6` (SOFT_YELLOW exit=8, 2-consecutive alarm).
5. Subordinated: rename-end-state, #11 API asks, Row N verifier gates. Not blocking 24/7 uptime.
