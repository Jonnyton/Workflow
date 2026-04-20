# Self-Host Uptime Migration — Near-Term Execution Plan

**Date:** 2026-04-20 (post P0 outage + host directive)
**Author:** navigator
**Status:** Active exec plan. Draws mechanics from `docs/specs/2026-04-19-plan-b-selfhost-migration-playbook.md`; narrows scope to "make uptime independent of the host's computer in the near term."
**Lens:** 3-layer chain. Today the System layer is physically bound to one Windows machine in the host's home — its cloudflared tunnel, its MCP process, its LanceDB singleton, its disk-backed DBs. Host directive today: **"full uptime no longer dependent of this computer."** That is the scope.

---

## 1. Scope — what "near-term" means precisely

**IN SCOPE:** the minimum surface that, when moved off the host machine, means the host's computer can be powered off for 48 hours without any surface going red.

That surface is exactly two things:
1. **The MCP daemon process** (`workflow/daemon_server.py` + `workflow/universe_server.py`, served via `fastmcp` on streamable-http transport).
2. **The cloudflared tunnel origin** that terminates `mcp.tinyassets.io/mcp` + `tinyassets.io/` and forwards to (1).

Every other uptime surface is already independent of the host machine:

| Surface | Status today | Migration need |
|---|---|---|
| Tier-3 OSS `git clone` | GitHub-hosted | None |
| Tier-3 CI / nightly smoke GHA | GitHub-hosted | None |
| Web landing (future) | Cloudflare Pages / GoDaddy W+M | None today; plan-b migrates to Hetzner later |
| **MCP daemon (tier-1 + tier-2 chatbot path)** | **Host machine** | **THIS PLAN** |
| **cloudflared tunnel origin** | **Host machine** | **THIS PLAN** |
| Uptime canary (Layer 1) | Windows Task Scheduler on host | Probes from OUTSIDE — should continue from host for now; later add GHA independent vantage point |
| Uptime canary (Layer 2) | Shared CDP browser on host | Remains host-bound by necessity (user-sim needs browser); NOT in scope |
| Future Supabase/Postgres | Supabase managed | None |
| Future paid-market | Supabase-backed | None |

**OUT OF SCOPE (deferred to full plan-b):**
- Moving the web app, GitHub Action targets, catalog mirror, convergence tools, or any primary persistence layer. Today we have none of these; the plan-b playbook covers them when they exist.
- Moving Supabase-hosted state (doesn't exist yet; being built under Track A).
- DR / multi-region / high-availability beyond "one remote host is up."

The goal is tight: **one remote Linux box runs the MCP daemon + the cloudflared origin. Host machine becomes replaceable.**

---

## 2. Provider options — cost / complexity / time-to-live

Host picks one; every option lands at roughly the same functional endpoint. Estimates assume one small box serving a single-digit-user MVP.

| Option | Monthly cost | Complexity | Time-to-live | Strengths | Weaknesses |
|---|---|---|---|---|---|
| **Fly.io** (Q7 in v3 host-Q digest, still unresolved) | ~$5-15 (shared-cpu-1x, 256MB + scale up) | Low — `fly launch` + Dockerfile; deploy ≤10 min | 1-2 dev-days | Already referenced in `docs/design-notes/2026-04-18-full-platform-architecture.md`. Simple deploy. Global region placement. | Shared-fate with broader Fly.io reliability (Fly has had multi-hour outages 2025). Machines tier is fine for MVP; scale-up adds cost. |
| **Hetzner Cloud** (CX11, 2 GB) | ~€4/mo (~$5) | Medium — provision box, Docker/systemd setup, Cloudflare Origin CA install | 1.5-2 dev-days | Cheapest per-dollar by 3-5×. EU jurisdiction (arguable pro for privacy). Plan-b playbook default. | Host has to maintain the OS (patch cadence, fail2ban, systemd). Ops-burden goes up ~2-4 hrs/month. No managed-Postgres option. |
| **GoDaddy VPS** | ~$7-25 depending on plan | Medium | 2 dev-days | Host already owns the account + has the billing relationship (`project_godaddy_hosting.md`). Consolidates vendors. | GoDaddy VPS is not load-tested for our shape; historically slower admin UIs; not the kind of service GoDaddy brands around. |
| **AWS Lightsail / EC2 t4g.nano** | ~$3-6 (ARM Graviton small instance) | Medium-high — IAM complexity on top of box admin | 2 dev-days | Mature tooling; lots of deployment automation options. | IAM learning curve. AWS billing surprises. |
| **Cloudflare Workers + Durable Objects** | ~$5/mo (Workers Paid) + minimal compute | High — requires refactoring MCP to Workers runtime (no fs access, no long-lived connections the way we use them today) | 4-6 dev-days | Same vendor as tunnel → removes the `api.tinyassets.io` class of DNS-coupling bug entirely. Globally distributed. | Our daemon uses SqliteSaver + LanceDB singletons + local fs access — all incompatible with Workers without significant rewrite. |
| **Managed Render / Railway** | ~$7-20/mo | Low | 1-2 dev-days | Similar to Fly.io — docker-deploy-a-service shape. Managed TLS. | Another vendor dependency; less host-controllable than Hetzner; pricing less predictable. |

### Navigator recommendation: **Fly.io**, with Hetzner as the pre-validated fallback.

**Reasoning:**
1. **Time-to-live is the dominant factor for "near-term."** Fly.io's `fly launch` path with a Dockerfile goes from zero to public URL in under an hour of wall time. Hetzner adds ~4-6 hours of OS admin per deploy the first time. If host directive is "near-term," Fly wins on ship speed.
2. **Our existing design docs already assume Fly.io** — `docs/design-notes/2026-04-18-full-platform-architecture.md` §3.2 references Fly for the gateway. Migration of assumption from "future Fly.io" to "current Fly.io" is smaller than adopting a new vendor.
3. **Host directive on GoDaddy memory** (`project_godaddy_hosting.md`) is *"prefer existing infra over new vendors"*. Fly is not existing infra for us today, but it has already been named as a design assumption; Hetzner has been named only as a plan-b fallback. Fly is a smaller cognitive hop than Hetzner.
4. **Plan-b migration path remains viable.** If Fly.io's pricing or reliability disappoints, move to Hetzner per plan-b playbook §5.2 — that's a well-mapped path; we don't lose optionality.
5. **Cost is a rounding error at current scale.** Fly.io $5-15/mo vs Hetzner $5/mo is not the decision axis; dev time to ship is. At 10k+ DAU the equation flips (per plan-b §6.5 cost-tier math) — then migrate to Hetzner.

**Anti-recommendation: Cloudflare Workers.** The rewrite cost (SqliteSaver, LanceDB, local fs) is 4-6 dev-days of refactor — more than the whole near-term migration. Queue Workers as a future architectural target if we ever hit Workers-scale traffic; do NOT put it on the near-term path.

**If host prefers Hetzner anyway,** the plan shape is identical — only the deploy target in §4 Work row 4 changes.

---

## 3. Host asks (keep to 5 max)

For next host check-in. All five are decisions host must make; navigator can pre-answer all but Q-uptime-1 (MEDIUM confidence).

| # | Question | Pre-answer | Confidence |
|---|---|---|---|
| **Q-uptime-1** | **Provider pick: Fly.io, Hetzner, GoDaddy VPS, or other?** | Fly.io per §2. Near-term ship-speed dominates; plan-b remains Hetzner. | MEDIUM (host-directed; navigator lens says Fly but GoDaddy existing-infra preference could flip this) |
| **Q-uptime-2** | **Secrets storage posture for prod:** env vars in the provider's dashboard (default), or a dedicated vault (1Password / Bitwarden / HashiCorp)? | Env vars in provider dashboard for near-term. One secret today (`CLOUDFLARE_TUNNEL_TOKEN`); vault is overkill at 1 secret. Revisit when Supabase JWT + wallet keys land (post-Track A). | HIGH |
| **Q-uptime-3** | **Supabase managed vs self-hosted Postgres?** (Forward-links to Q1 in v3 digest which resolved "Supabase canonical" but didn't specify managed-vs-OSS-Postgres-self-hosted.) | Supabase managed for near-term + all of first-draft. Plan-b §5.1 covers migration-to-self-hosted if Supabase ever goes. Deferring this decision costs nothing today. | HIGH |
| **Q-uptime-4** | **What role does the host's computer retain?** Four options: (a) pure off — box on provider is canonical; (b) dev seat only — host runs daemon locally for development, prod is on provider; (c) warm fallback — host daemon is a manual failover target; (d) cold fallback — host keeps the code + config but doesn't run. | (b) dev seat only. Warm fallback (c) adds operational complexity with little benefit at current scale; (d) pure-off (a) wastes the capable local dev loop. (b) matches how most one-person projects run. | HIGH |
| **Q-uptime-5** | **Data volume for first ship:** do universes + canon DBs ship with the first box, or does the box start empty + universes migrate gradually? | Box starts empty for near-term — universes are per-host tier-2 concept anyway (per `project_user_tiers.md`), and the public MCP endpoint serves the catalog + paid-market, not per-user universe state. This one matters: if host disagrees, it changes the data migration scope. | MEDIUM (worth flagging — host may have a different mental model of what lives on the public box) |

**Recommended host time budget: ~2 minutes.** Q-uptime-2/3/4 are ratify-by-lead if host is time-constrained; Q-uptime-1 and Q-uptime-5 deserve host attention.

---

## 4. Shippable-now work (no host input needed) — Work-table rows

Five rows. All dispatchable immediately against the current main. Zero provider-specific code in rows 1-3; provider-specific in rows 4-5.

### Row A: Containerize the daemon

**Files:** `Dockerfile` (new at repo root), `.dockerignore` (new), `docs/ops/docker-notes.md` (new).

**Scope:**
- Multi-stage Dockerfile: Python 3.11 base, `pip install -e .`, install cloudflared binary, expose port 8001, entrypoint = `python -m workflow.daemon_server` or equivalent.
- `.dockerignore` excludes `.venv/`, `__pycache__/`, `output/`, `*.db`, `node_modules/`, `.git/`, `packaging/` (the Windows tray plugin doesn't ship in the server image).
- Short ops-notes doc explaining build + local test.

**Acceptance:** `docker build -t workflow-daemon . && docker run -p 8001:8001 workflow-daemon` serves `/mcp` locally; `curl -X POST localhost:8001/mcp` gets a valid MCP initialize response.

**Effort:** ~0.5 dev-day. First draft; iterations expected.

**Blocks:** Row D (deploy) depends on this.

### Row B: Extract hardcoded host-machine paths

**Files:** audit + refactor any `C:\Users\...` / `C:\\Users\\...` / `Path(os.environ["USERPROFILE"])` / similar absolute-path assumptions in `workflow/` server code. Suspect surfaces per grep: `workflow/daemon_server.py`, `workflow/universe_server.py`, `workflow/storage/__init__.py`, anywhere LanceDB or SqliteSaver construct paths.

**Scope:**
- Audit: grep for literal `C:\` and `USERPROFILE` across `workflow/` (exclude tests + packaging + scripts). Expect: LanceDB default path, universe_base path, any sqlite path.
- Refactor to env-driven: `WORKFLOW_DATA_DIR` (default `~/.workflow` on Unix, `%APPDATA%\Workflow` on Windows). All on-disk state roots through this variable.
- Docstring: document the env var in `workflow/daemon_server.py` module docstring + `AGENTS.md` if warranted.

**Acceptance:** `WORKFLOW_DATA_DIR=/tmp/test_data python -m workflow.daemon_server` starts cleanly on a Linux host with no `C:\` paths touched in the success path. Existing Windows-host behavior unchanged when the env var is unset (defaults resolve to the current Windows path).

**Effort:** ~0.5-1 dev-day. Surface area unknown until audit; estimate widens if LanceDB / FAISS / etc. deeply encode Windows paths.

**Blocks:** Row D (deploy).

### Row C: Tunnel config shape — provider-agnostic

**Files:** `deploy/cloudflared.yml` (new template), `deploy/cloudflared-README.md` (new), `scripts/run-tunnel.sh` (new).

**Scope:**
- Template cloudflared config parameterized by `$TUNNEL_TOKEN` + `$ORIGIN_PORT`. No hardcoded tunnel names, no hardcoded hostnames.
- Runbook: how to create a new tunnel + bind it to `mcp.tinyassets.io` (leans on the godaddy-ops skill's Cloudflare gotchas).
- Shell script that runs `cloudflared tunnel --config deploy/cloudflared.yml run` — suitable for systemd/Docker entrypoint.

**Acceptance:** A dev (or future provider) can clone the repo, set `TUNNEL_TOKEN` + `ORIGIN_PORT` env, run `scripts/run-tunnel.sh`, and a tunnel lives on the public URL. No Windows-specific steps.

**Effort:** ~0.25-0.5 dev-day.

**Blocks:** Row D (deploy).

### Row D: Deploy to provider (provider-specific — reveals after Q-uptime-1)

**Files:** (Fly.io case) `fly.toml` (new), `docs/ops/fly-deploy.md` (new). (Hetzner case) `deploy/compose.yml` + `deploy/provision.sh`.

**Scope:**
- One-shot bring-up: box exists, daemon running, tunnel attached, `mcp.tinyassets.io/mcp` returns a successful initialize from the remote daemon (not the host machine's).
- DNS: `mcp.tinyassets.io` CNAME points at the provider's tunnel (NOT the host's tunnel). Host machine's tunnel removed from the Cloudflare zero-trust config to prevent dual-origin routing.
- Secrets: `TUNNEL_TOKEN` injected via provider dashboard (per Q-uptime-2).

**Acceptance:** Host machine powered off for 1 hour → `mcp.tinyassets.io/mcp` still green via Layer-1 canary. That's the pass gate.

**Effort:** Fly.io ~0.5-1 dev-day. Hetzner ~1-1.5 dev-days. GoDaddy VPS ~1-1.5 dev-days.

**Blocks:** Row E.

### Row E: Migration smoke script + 48-hour-offline acceptance

**Files:** `scripts/selfhost_smoke.py` (new), `tests/smoke/test_selfhost_parity.py` (new under tier-3 smoke directory).

**Scope:**
- `selfhost_smoke.py` hits `mcp.tinyassets.io/mcp` + a known list of tool calls (`get_status`, `tools/list`, any critical cold-path). Fail-loud on any regression vs the same calls against localhost.
- Integration test asserts parity: same tool set, same public-tool-output shape, same success behavior.
- Runs in the nightly tier-3 GHA (once that's live) against the remote box.

**Acceptance (48-hour trial):**
1. After Row D lands, host powers down their local daemon.
2. Layer-1 canary runs every 2 min for 48 hours against `mcp.tinyassets.io/mcp`.
3. Zero Layer-1 reds in the trailing 48 hours.
4. `selfhost_smoke.py` green at hour 1, hour 24, hour 47.
5. Hard Rule 10 satisfied: no post-change DNS or provider reconfig blips went undetected.

**Effort:** ~0.25 dev-day for the script + test. Acceptance is 48h wall time + canary monitoring, ~0 dev-hours active.

**Blocks:** nothing. Row E is the closer.

---

## 5. Sequencing + timeline

**Assumes Fly.io pick.** Hetzner pick adds ~0.5-1 dev-day in Row D.

| Phase | Sequence | Dev-days | Wall-time |
|---|---|---|---|
| **P1 — Shippable-now (no host input)** | Rows A + B + C in parallel across 1 dev, or A/B/C parallel across 2 devs | ~1.5-2 dev-days serial; ~1 dev-day with 2 devs | 1-2 calendar days |
| **P2 — Host answers Q-uptime-1 to -5** | Host decision surface | ~15 min host time | opportunistic |
| **P3 — Provider deploy (Row D)** | After A+B+C land + Q-uptime-1 answered | ~0.5-1 dev-day | 1 calendar day |
| **P4 — Migration smoke + 48h offline trial (Row E)** | After D lands | ~0.25 dev-day active + 48h wall | 3 calendar days |
| **Total dispatch-to-cutover** | | **~2-3 dev-days active** | **5-7 calendar days** |

**Realistic range:** 5-7 days if host pick arrives within 24h. 10 days if host prefers Hetzner (more OS admin) or if Row B surfaces unexpected Windows-path surface area.

**Critical path observation:** Rows A, B, C are all independent of host input. Dev can start all three today. Dispatch doesn't need to wait on the host-Q digest answer — only Row D (deploy) blocks on Q-uptime-1.

---

## 6. Day 1 after cutover — acceptance criteria

The migration is "done" when all five hold simultaneously for a 48-hour window:

1. **Layer-1 canary green for 48 consecutive hours** against `mcp.tinyassets.io/mcp`. Zero `exit != 0` probes. (Post-canary-ships; gate blocks if canary not live yet.)
2. **`selfhost_smoke.py` green at hour 1, 24, 47.** No tool output regressions from the remote box vs local prod baseline (captured one week before cutover).
3. **Host machine powered off or hibernated for ≥48 hours** without a single user-visible outage on `mcp.tinyassets.io/mcp`.
4. **Hard Rule 10 satisfied:** any provider-dashboard DNS change or tunnel reconfig during the 48h window ran `scripts/uptime_canary.py --once` post-change and confirmed green.
5. **Succession runbook updated** — `SUCCESSION.md` §5 references the provider box as the current authoritative origin, with a link to Row C's cloudflared config template for rebuild-from-scratch.

If all five hold, **the host's computer is officially replaceable.** The forever rule's "system is always up without us" has gained an important piece: "without this specific machine" is now provably true.

---

## 7. Risks + mitigations

| Risk | Mitigation |
|---|---|
| Row B (path extraction) surfaces undocumented Windows assumptions in LanceDB or a vendored dep | Start Row B audit in parallel with A; if surface area exceeds 1 dev-day, scope creep flag → re-estimate before committing. |
| Fly.io pricing surprises at idle vs. provisioned | Near-term is pre-launch; scale-out phase (post-10k DAU) triggers plan-b §5.2 migration to Hetzner. Budget annotation in row D acceptance. |
| Tunnel auth regression during provider-swap | Row D includes Layer-1 canary probe immediately post-deploy + Hard Rule 10 post-change discipline. |
| Host local dev setup breaks after path-extraction refactor | Row B acceptance requires Windows-host behavior unchanged when `WORKFLOW_DATA_DIR` is unset. Regression test in tests/smoke/ covers both Unix + Windows default resolution. |
| Remote box starts empty but user-sim uses universes from host-local disk | Q-uptime-5 answer resolves this up front. If host disagrees with "box starts empty," plan adds a data-seeding row. |
| 48h offline trial during host travel / real use | Trial period can be any 48 consecutive hours; host picks a low-stakes window. Do NOT gate acceptance on trial completion — acceptance is "when 48h clean has happened," not "immediately." |

---

## 8. What this plan does NOT decide

- **Full plan-b migration (Supabase → Hetzner / everything OSS-self-host).** That's `docs/specs/2026-04-19-plan-b-selfhost-migration-playbook.md` — executes when triggers fire per playbook §1. Near-term plan deliberately NOT that.
- **Multi-region / HA / load-test-at-scale.** Track J (per `docs/design-notes/2026-04-18-full-platform-architecture.md` §10) — pre-launch scale validation, not near-term.
- **CI/CD pipeline for the remote box.** First-ship uses manual `fly deploy` or `rsync + docker compose up`. Automated deploy on push → later improvement.
- **Custom-domain TLS from the provider's origin** (beyond the Cloudflare-Origin-CA relationship). Existing Cloudflare CA cert (15-year validity per plan-b §3.5.3) fronts the provider; no new cert work.
- **Secrets migration for wallet / paid-market.** Those don't exist yet; Track A ships first, then wallet secrets join the Q-uptime-2 posture.
- **Dev → prod promotion flow.** Out of scope; today's question is "can host's computer be offline." Multi-env plumbing comes when there's a reason for staging.

---

## 9. Follow-up — merge into plan-b

After near-term ships + 48h trial green:

1. Update `docs/specs/2026-04-19-plan-b-selfhost-migration-playbook.md` §2 target architecture row "Gateway" to reflect the **actual** deployment (Fly.io or Hetzner) as current state rather than future assumption.
2. Add §3.5 "Pre-migration readiness — daemon/tunnel portability" as a warm path; Rows A+B+C artifacts from this plan ARE that warm path.
3. Cancel the host-machine-as-primary assumption anywhere it persists in docs (grep TBD).

Navigator owns the merge; ~0.25 nav-day after the 48h trial closes.

---

## 10. Summary for dispatcher

- **Scope:** MCP daemon + tunnel origin off the host machine. Near-term, not full plan-b.
- **Provider recommendation:** Fly.io. Fallback: Hetzner. Anti-recommendation: Cloudflare Workers (rewrite cost too high).
- **5 host asks, ~2 min host time:** provider pick (MEDIUM), secrets (HIGH), Postgres pick (HIGH), host-machine role (HIGH), starting data volume (MEDIUM).
- **5 shippable-now Work rows:** containerize (0.5d), extract paths (0.5-1d), tunnel config (0.25-0.5d), deploy (0.5-1d, host-answer-gated), smoke + trial (0.25d + 48h wall). Rows A-C dispatchable immediately; Row D waits on Q-uptime-1.
- **Total active dev:** ~2-3 dev-days. Calendar 5-7 days to 48h-offline acceptance.
- **Cutover gate:** host's computer offline for 48 consecutive hours, zero canary reds. That's the real acceptance.

Go.
