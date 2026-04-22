# Status

Live steering only. **Budget 4 KB / 60 lines.** Concerns/Work = one line each; Concerns host-managed; Work rows delete when landed; Next replaced each session. Forever rule = 24/7 uptime with zero hosts online (see AGENTS.md top-of-file).

## Concerns

- [2026-04-20] **Option 1 LIVE 01:50 UTC** 976ba1c. `tinyassets.io/mcp` → 200 canonical; `mcp.tinyassets.io/mcp` → 403 gated. Worker `tinyassets-mcp-proxy` deployed w/ CF Access headers. **Host: rotate Global API Key** (used in session + terminal history).
- [2026-04-22] **P0 resolved 01:03 UTC** — `/etc/workflow/env` mode regressed 600 root:workflow on 2026-04-21 07:22; unit runs as user=workflow → EnvironmentFile unreadable → compose crash-loop (67 restarts) → cloudflared down → `tinyassets.io/mcp` 502 for ~18h. Fix: `chmod 640`. Root cause of mode flip unknown — `deploy-prod.yml` or bootstrap path may be overwriting w/ 600; needs audit so this doesn't recur silently overnight again.
- [2026-04-20] `test_node_eval::test_record_and_get_stats_roundtrip` pre-existing flake. Passes in isolation, flaky in full suite. Surface, not block.
- [2026-04-17] 589e1fb REST changes need tests: `/votes/{id}/resolve` forced; `/votes/{id}/ballots` now `{"vote": ...}`.
- [2026-04-17] Privacy mode note landed: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`; 3 host Qs remain.
- [2026-04-18] `add_canon_from_path` sensitivity note landed: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`; 3 host asks remain.
- [2026-04-18] Claude.ai injection mitigation work blocked on host-Q batch: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`.
- [2026-04-18] `fantasy_daemon/author_server.py` alias risk: snapshot export, not sys.modules rebind; fix there if cross-alias drift appears.
- [2026-04-18] Full-platform architecture supersedes phased plan: `docs/design-notes/2026-04-18-full-platform-architecture.md` (migrate to PLAN.md candidate).
- [2026-04-19] Navigator follow-up: `docs/design-notes/2026-04-19-modularity-audit.md` flags `universe_server`, discovery, and `daemon_server` seams.

---

## Approved specs (navigator-vetted)

Full specs: `docs/vetted-specs.md` (H2 heading per spec). Dev reads there, never wiki. On land, delete row + H2 section together.

| Spec | Status |
|---|---|
| Structured JSON output for multi-output + typed prompt nodes | claimed:dev |
| Strict input_keys isolation for prompt_template nodes | in-progress:dev (uncommitted diff) |
| Expose conditional_edges on build_branch + patch_branch | dev-dispatchable |
| list_branches node_count double-counts graph.nodes + node_defs | dev-dispatchable (trivial) |
| describe_branch / get_branch surface related wiki pages | dev-dispatchable |
| Per-node llm_policy override | dev-dispatchable |
| In-flight run recovery surface — part 1 (document v1 contract) | dev-dispatchable |
| In-flight run recovery — part 2 (SqliteSaver-keyed resume) | **strategy-open:needs-host** |
| Concurrency budget + observability for fan-out nodes | dev-dispatchable |
| Loud sandbox-unavailable surface for dev/checker exec nodes | dev-dispatchable |
| Sub-branch invocation primitive | dev-dispatchable |
| Cross-run state query primitive | dev-dispatchable |
| Scheduled + event-triggered branch invocation | dev-dispatchable |
| Project-scope persistent memory primitive | dev-dispatchable |
| file_bug is the feature-request verb — docstring + optional kind field | dev-dispatchable |
| Prompt_template literal-brace escape + build-time missing-key validation | dev-dispatchable |

---

## Work

Claim by setting Status to `claimed:yourname`. Files is the collision boundary. All Row-X tasks live in `docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md`.

| Task | Files | Depends | Status |
|------|-------|---------|--------|
| Pushover priority=2 upgrade (Task #8) | `scripts/pushover_page.py` | delivery validated 2026-04-22 02:07 UTC | claimed:dev |
| Fire DR drill #3 via workflow_dispatch | `.github/workflows/dr-drill.yml` | #4 merged (4f936fe) | in-progress: run 24756582461 |
| Row F — 48h smoke + acceptance | `scripts/selfhost_smoke.py` | 48h green window | monitoring |
| HD-2 secrets.env password-manager backup | host-only action | — | pending:host |
| HD-4 Cloudflare Global Key rotation | host dashboard | — | pending:host |
| Mission 10 retest | user-sim | host scope call | claimed:user |
| #19 Memory-scope Stage 2c flag | — | 30d clean | monitoring |

---

## Next

1. **Host:** seed Pushover secrets (`PUSHOVER_USER_KEY`, `PUSHOVER_APP_TOKEN`) then lead fires one-shot validation RED.
2. **Host or lead-with-PAT:** fire DR drill #3 via `workflow_dispatch`. Needs GH token w/ `actions:write` scope (none in `$HOME/workflow-secrets.env`). Host dashboard click works too.
3. **In flight (dev):** Task #6 MCP tool-invocation canary — closes "handshake-green, tool-broken" gap. Task #5 actionlint hook+CI pending verifier. SHA256-pin followup queued behind #6.
4. **Stack live:** canonical `tinyassets.io/mcp` 200 + tools/list works (verified 01:09 UTC via MCP initialize); DO Droplet auto-restart + nightly backup + offsite GH Release + 6 timers. P0 RCA hardening landed: 0217175 (perm restore) + 19c2261 (Pushover paging) + a62ae30 (ENV-UNREADABLE 4-surface marker + auto-triage) + 4f936fe (DR drill exit-code propagation).
5. **Host-only remaining:** HD-2 secrets.env password-manager backup; HD-4 Global API Key rotation. Non-uptime-blocking but close for bus factor.
6. Subordinated: rename-end-state, #11 API asks, mission retests. Not blocking 24/7 uptime.
