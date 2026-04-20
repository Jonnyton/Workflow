# Self-Host Uptime Migration — Near-Term Execution Plan

**Date:** 2026-04-20 (post P0 outage + host directive)
**Author:** navigator
**Status:** Active exec plan. Draws mechanics from `docs/specs/2026-04-19-plan-b-selfhost-migration-playbook.md`; narrows scope to "make uptime independent of the host's computer in the near term."
**Lens:** 3-layer chain. Today the System layer is physically bound to one Windows machine in the host's home — its cloudflared tunnel, its MCP process, its LanceDB singleton, its disk-backed DBs. Host directive today: **"full uptime no longer dependent of this computer."** That is the scope.
**Navigator-owned decisions:** provider + secrets posture + Postgres + host-machine-role + first-ship data volume. Host directive: *"cant the navigator think long term and pick the cleanest design that always works for us having a website."* Criterion applied throughout: **always-works over ship-speed, cost-optimization, or elegance.** Navigator decides; lead ratifies; dispatch proceeds without host round-trip.

---

## 0. Canonical URL (2026-04-20 post host Option-A pick)

Three URLs, three roles. Named here once so every subsequent row + the docs-sweep follow-up land on the same shape.

| URL | Role | Notes |
|---|---|---|
| `https://tinyassets.io/mcp` | **User-facing canonical.** The URL that ships in Claude.ai connector configs, README, onboarding docs, and any tier-1 / tier-2 UX copy. | Served via a Cloudflare Worker at the apex that routes `/mcp*` → tunnel origin → daemon. Worker is an independent Cloudflare edge layer; predates Fly/Hetzner cutover. |
| `https://mcp.tinyassets.io/mcp` | **Direct tunnel origin.** Debugging + canary probing + anything that needs to bypass the Worker. | This is the cloudflared tunnel hostname that points at the daemon. The Worker forwards here internally; users don't reach this. Layer-1 canary probes BOTH so we can localize a regression to Worker vs tunnel vs daemon. |
| ~~`https://api.tinyassets.io/mcp`~~ | **NOT live. Do not resurrect.** | Referenced in older docs as the intended-canonical but never shipped (NXDOMAIN in the 2026-04-19 P0 event was exactly this: a record that had been briefly managed and then lost). Any doc containing `api.tinyassets.io` is stale and should be corrected during the docs-sweep follow-up (Row G). |

**Interaction rule.** If a future tunnel reconfig (Cloudflare dash work) touches either `tinyassets.io/mcp` or `mcp.tinyassets.io/mcp`, Hard Rule 10 fires — run `scripts/uptime_canary.py --once` post-change and confirm green BOTH routes before marking the change complete.

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

## 2. Provider pick: **Hetzner Cloud** (CX22, Debian 12, Docker Compose)

**Single pick, no option-buffet.** Host directive: *"pick the cleanest design that always works for us having a website."* Criterion = always-works (operational simplicity + proven uptime + low-oops-factor, scaled through the full-platform target without a second migration). Not cheapest, not trendiest, not most-familiar.

**Fallback-if-primary-goes-bad:** **Fly.io**. Engaged only on observed Hetzner regression (multi-day regional outage, pricing shock per plan-b §5.2 trigger shape). Otherwise stays.

### Why Hetzner, five bullets

- **Proven uptime over the relevant timescale.** Hetzner Cloud has operated since 2018 with a documented ≥99.9% SLA. Fly.io has had multiple multi-hour all-region control-plane outages in 2024-2025 affecting `flyctl`, machine scheduling, and running apps simultaneously. For the forever rule ("user never sees an outage"), a boring Linux VM with a long clean uptime record beats an elegant orchestrator that goes hard-down a few times per year. Load-bearing factor.
- **Zero managed-runtime fate-sharing.** The daemon runs on a rented Linux box. If Hetzner's *control plane* has a bad day, the *running VM keeps serving* with its tunnel attached — only NEW provisioning breaks. Fly/Render/Railway all have documented modes where control-plane outage takes running apps down. A chatbot call reaching a Hetzner VM during a control-plane event is strictly more robust than reaching a managed runtime that just lost its scheduler.
- **Same box scales from MVP to full-platform target.** CX22 (€4/mo, 2 vCPU, 4 GB) handles near-term MVP; resize in-place to CX42 (€20/mo, 8 vCPU, 16 GB) covers thousands-concurrent + paid-market (`project_full_platform_target.md`). One-command upgrade, no migration event. No "we picked the MVP tool, now rewrite for scale" moment ever forced.
- **Zero lock-in; clean succession handoff.** Deployment is `Dockerfile` + `docker-compose.yml` + a shell script. Any successor admin (`project_host_independent_succession.md`) can lift the whole stack to a different Linux provider with `rsync` + a DNS flip. Fly/Render/AWS each embed proprietary tooling (fly.toml, IAM role graphs, Render service IDs) that outlive their usefulness as handoff friction. Hetzner + Docker Compose is the most portable shape that exists today.
- **Clean alignment with the rest of the architecture.** Supabase + Hetzner + Cloudflare-front is exactly the target shape in plan-b playbook §2, and matches `project_license_fully_open_commons.md` / OSS distribution posture (no provider terms constrain what we redistribute). Near-term migration and the documented plan-b migration path become the *same path* — plan-b becomes "we're already there" rather than "we'll execute if triggers fire." Eliminates a second architectural call later.

### Why not the alternatives — one sentence each

- **Fly.io:** ship-speed win goes to dev experience, not to the user's outage count. Track record penalty weighed more than the ~4h faster first-deploy.
- **GoDaddy VPS:** existing-vendor memory is real, but GoDaddy VPS is a tertiary product with no track record among shops running Docker services in production — "existing vendor" does not override "proven for the exact shape we need."
- **AWS Lightsail / EC2:** IAM surface adds ops complexity with no offsetting uptime win at our scale.
- **Cloudflare Workers:** would require rewriting SqliteSaver + LanceDB + local fs access (~4-6 dev-days refactor) before a single probe passes; rewrite cost exceeds the whole migration budget. Queue as a future architectural target if we ever hit Workers-scale traffic; not near-term.
- **Render / Railway:** same managed-runtime fate-sharing as Fly; adds a vendor without adding robustness.

---

## 3. Internal decisions that used to be host asks — pre-decided

Per host directive *"think long term and pick the cleanest design."* Navigator decides; no host round-trip. All four answers below are HIGH confidence unless noted; lead ratifies silently.

- **Secrets storage for prod:** env vars injected via Hetzner cloud-init + systemd `EnvironmentFile` pointing at `/etc/workflow/secrets.env` with `chmod 600` root-only read. One secret today (`CLOUDFLARE_TUNNEL_TOKEN`); vault integration is overkill at this count. Revisit when Supabase JWT + wallet keys land (post-Track A, ~2-3 secrets total). Rationale: file-on-box + ownership-restricted is standard Linux posture, no third-party dependency, easy to rotate by re-writing the file, survives all the secret-vault migration scenarios in plan-b.
- **Postgres:** Supabase managed. Already ratified as Q1 per v3 host-Q digest. No near-term change.
- **Host machine role post-cutover:** dev seat only. Host keeps the full local dev loop; prod is on Hetzner. Warm-fallback adds operational complexity (sync issues, split-brain risk) without measurable robustness win. Pure-off wastes a capable local dev environment. Standard one-person-project pattern.
- **Data on first box:** box starts empty. Universes are tier-2 per-host concept (`project_user_tiers.md`); the public MCP endpoint exists to serve catalog + paid-market + connector handshake, not per-user universe state. MEDIUM confidence — flagging in case this contradicts an unstated host model — but going with it. Any universe-migration scope that surfaces later is additive work, not a foundation change.

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

### Row D: Deploy to Hetzner

**Files:** `deploy/compose.yml` (new), `deploy/provision.sh` (new), `docs/ops/hetzner-deploy.md` (new).

**Scope:**
- Provision a Hetzner Cloud CX22 (Debian 12, Falkenstein or Nuremberg region — both have long clean track records; first-draft picks whichever has lower latency to tinyassets.io's Cloudflare edge).
- Run `scripts/provision.sh` (new): installs Docker + Compose, creates `/etc/workflow/secrets.env` with `chmod 600`, fetches the daemon image + cloudflared image, sets up systemd unit files for both.
- `docker compose up -d` brings up the daemon + tunnel sidecar containers; healthcheck confirms `localhost:8001/mcp` responds.
- DNS: `mcp.tinyassets.io` CNAME points at the Hetzner box's tunnel (NOT the host's tunnel). Host machine's tunnel removed from the Cloudflare Zero-Trust config to prevent dual-origin routing.
- Secrets: `CLOUDFLARE_TUNNEL_TOKEN` written once to `/etc/workflow/secrets.env`; systemd `EnvironmentFile` pulls it on service start.

**Relationship to Row E (Worker):** Row D lands the direct-tunnel-origin side (`mcp.tinyassets.io/mcp`). The user-facing canonical `tinyassets.io/mcp` is fronted by an independent Cloudflare Worker (Row E) that forwards to this origin. Worker + tunnel origin are independent layers — either can be updated without the other. The Worker ships BEFORE the Hetzner cutover (it routes to the current tunnel origin regardless of whether that origin is the host machine or the Hetzner box); Hetzner cutover just changes which origin the Worker reaches.

**Acceptance:** Host machine powered off for 1 hour → `mcp.tinyassets.io/mcp` still green via Layer-1 canary. User-facing `tinyassets.io/mcp` also green (Worker + new origin path). That's the pass gate.

**Effort:** ~1-1.5 dev-days. Hetzner provisioning + Docker Compose + Cloudflare tunnel binding + DNS flip + post-flip Hard Rule 10 probe on BOTH URLs.

**Blocks:** Row F (trial).

### Row E: Cloudflare Worker — restore `tinyassets.io/mcp` as canonical

**Files:** `deploy/cloudflare-worker/worker.js` (new), `deploy/cloudflare-worker/wrangler.toml` (new), `deploy/cloudflare-worker/README.md` (new).

**Scope:**
- Cloudflare Worker attached to `tinyassets.io/*` zone routes, matching route pattern `tinyassets.io/mcp*`.
- Worker forwards matching requests to `https://mcp.tinyassets.io/mcp...` preserving method, headers, streaming body, and trailing path segments (so that `/mcp/anything/nested` routes cleanly if FastMCP ever adds sub-routes).
- Non-`/mcp*` requests at apex pass through unchanged (landing HTML served by the daemon's own `@mcp.custom_route("/")` or any future GoDaddy/Pages route — Worker doesn't intercept them).
- Streaming HTTP transport support: the Worker must proxy `Content-Type: text/event-stream` and chunked-transfer bodies correctly. FastMCP's streamable-http transport depends on long-lived streaming responses; naïve `fetch(...).then(r => new Response(r))` works in Workers for this.
- `wrangler.toml` declares the route + environment variables + Worker name (recommend `workflow-mcp-router`).
- README: one-command deploy via `wrangler deploy`; secret setup (none needed for MVP — tunnel origin is public; revisit when Supabase JWT lands); rollback procedure (remove route binding = apex serves whatever was behind it before).

**Independence from Row D:** Row E ships NOW (post-Row-A, no dependency on Row D). While the host machine is still serving `mcp.tinyassets.io`, the Worker restores `tinyassets.io/mcp` as canonical immediately. When Row D cuts over to Hetzner, the Worker's target (`mcp.tinyassets.io/mcp`) points at the new origin automatically — no Worker redeploy needed. This sequencing gets the user-facing canonical URL back online FAST without gating on the full self-host migration.

**Acceptance:**
1. `curl -X POST https://tinyassets.io/mcp -H 'content-type: application/json' -d '<initialize payload>'` returns a valid MCP initialize response.
2. Response equivalence to `https://mcp.tinyassets.io/mcp` — same JSON-RPC result shape, same tools available on `tools/list`.
3. Streaming transport works end-to-end: an MCP session over Claude.ai using `tinyassets.io/mcp` connector URL completes a tool call (e.g., `get_status`) without disconnection.
4. Layer-1 canary adds a probe against `tinyassets.io/mcp` (in addition to the existing `mcp.tinyassets.io/mcp` probe) and both return green for 10 min.
5. Hard Rule 10 satisfied post-deploy.

**Effort:** ~0.5 dev-day. Worker is small (≤50 LOC), wrangler setup is standard, testing is single-run local + live smoke.

**Blocks:** nothing hard. Enables: Row F (trial can now exercise the user-facing canonical), Row G (docs sweep) once Worker stable.

### Row F: Migration smoke script + 48-hour-offline acceptance

**Files:** `scripts/selfhost_smoke.py` (new), `tests/smoke/test_selfhost_parity.py` (new under tier-3 smoke directory).

**Scope:**
- `selfhost_smoke.py` hits BOTH `tinyassets.io/mcp` (user-facing canonical via Worker) AND `mcp.tinyassets.io/mcp` (direct tunnel) + a known list of tool calls (`get_status`, `tools/list`, any critical cold-path). Fail-loud on any regression vs localhost baseline. Parity assertion: both URLs return equivalent tool sets + equivalent `get_status` structure.
- Integration test asserts parity: same tool set, same public-tool-output shape, same success behavior.
- Runs in the nightly tier-3 GHA (once that's live) against both URLs.

**Acceptance (48-hour trial):**
1. After Row D + Row E land, host powers down their local daemon.
2. Layer-1 canary runs every 2 min for 48 hours against BOTH `tinyassets.io/mcp` and `mcp.tinyassets.io/mcp`.
3. Zero Layer-1 reds in the trailing 48 hours on either URL.
4. `selfhost_smoke.py` green at hour 1, hour 24, hour 47.
5. Hard Rule 10 satisfied: no post-change DNS, Worker, or provider reconfig blips went undetected.

**Effort:** ~0.25 dev-day for the script + test. Acceptance is 48h wall time + canary monitoring, ~0 dev-hours active.

**Blocks:** Row G (sweep fires on clean trial).

### Row G (follow-up, do NOT execute now): Canonical-URL docs sweep

**Files:** grep + update. Expected surfaces include `docs/specs/*`, `docs/audits/*`, `SUCCESSION.md`, `.claude/skills/ui-test/*`, `docs/ops/*`, any `.md` referencing `api.tinyassets.io/mcp` or referencing `mcp.tinyassets.io/mcp` as user-facing (vs debug-only).

**Scope:**
- Replace every user-facing reference to `mcp.tinyassets.io/mcp` OR `api.tinyassets.io/mcp` with `tinyassets.io/mcp` (canonical per §0). EXCEPTIONS stay as `mcp.tinyassets.io/mcp`: canary probe config, debugging runbooks, architecture docs explicitly describing the tunnel layer.
- Add a one-line reminder near each canonical reference about the three-URL shape from §0 if the surface is contributor-facing (specs + skills); user-facing surfaces (README, onboarding) get the canonical only.
- **No flip-flops after this sweep.** The URL architecture is locked: apex canonical via Worker, subdomain debug-only via tunnel. Future changes require explicit exec-plan amendment.

**Trigger:** fires only after Row F acceptance closes (48h trial green). Do not run preemptively — the sweep on not-yet-stable routing creates docs that lie if the Worker has to be rolled back.

**Effort:** ~0.5-1 dev-day depending on surface size. Mechanical grep + replace + review.

**Blocks:** nothing. Sweep is the final closer for the post-P0 URL-architecture arc.

---

## 5. Sequencing + timeline

Provider pick is locked (Hetzner). Worker (Row E) ships independently of Hetzner cutover. No host round-trip in the critical path.

| Phase | Sequence | Dev-days | Wall-time |
|---|---|---|---|
| **P1 — Rows A + B + C** | Parallel across 1-2 devs (A + C independent; B serial) | ~1.5-2 dev-days serial, ~1 dev-day with 2 devs | 1-2 calendar days |
| **P1b — Row E (Worker, parallel)** | Independent of A/B/C; dispatchable post-Row-A | ~0.5 dev-day | 1 calendar day (overlapping P1) |
| **P2 — Row D (Hetzner deploy)** | After A + B + C land | ~1-1.5 dev-days | 1-2 calendar days |
| **P3 — Row F (smoke + 48h offline trial)** | After D + E both land | ~0.25 dev-day active + 48h wall | 3 calendar days |
| **P4 — Row G (canonical-URL docs sweep)** | After P3 acceptance closes clean | ~0.5-1 dev-day | 1 calendar day |
| **Total dispatch to sweep closed** | | **~3.75-5.25 dev-days active** | **6-9 calendar days** |

**Realistic range:** 6-9 days in normal conditions (was 5-7 pre-Worker — Row E + Row G add ~1-1.5 dev-days of work net, but Worker-before-Hetzner means user-facing canonical restores earlier in the arc). 10-12 days if Row B surfaces more Windows-path surface area than audit predicts.

**Critical path observation:** the whole plan is dispatchable immediately. Row A + Row C parallel-ship on two devs; Row B serial behind whichever finishes second; Row E (Worker) dispatches post-Row-A independently. Row D goes as soon as A/B/C all land. Row F is the trial closer. Row G is the final sweep.

**User-facing canonical restores on Row E ship, NOT on Row D / F.** Once the Worker is live, `tinyassets.io/mcp` works regardless of whether the tunnel origin is the host machine or the Hetzner box. This is the near-term uptime win: the canonical URL is restored within ~1-2 days of dispatch, while the fuller host-machine-independence trial takes 6-9 days to close.

---

## 6. Day 1 after cutover — acceptance criteria

The migration is "done" when all five hold simultaneously for a 48-hour window:

1. **Layer-1 canary green for 48 consecutive hours against BOTH URLs** — `tinyassets.io/mcp` (user-facing canonical via Worker) AND `mcp.tinyassets.io/mcp` (direct tunnel origin). Zero `exit != 0` probes on either. (Post-canary-ships; gate blocks if canary not live yet.)
2. **`selfhost_smoke.py` green at hour 1, 24, 47.** No tool output regressions from the remote box vs local prod baseline (captured one week before cutover). Parity asserted between canonical + direct-origin URLs.
3. **Host machine powered off or hibernated for ≥48 hours** without a single user-visible outage on `tinyassets.io/mcp`.
4. **Hard Rule 10 satisfied:** any Cloudflare Worker, DNS, or provider-dashboard reconfig during the 48h window ran `scripts/uptime_canary.py --once` post-change against BOTH URLs and confirmed green.
5. **Succession runbook updated** — `SUCCESSION.md` §5 references the provider box as the current authoritative origin, with a link to Row C's cloudflared config template for rebuild-from-scratch.

If all five hold, **the host's computer is officially replaceable.** The forever rule's "system is always up without us" has gained an important piece: "without this specific machine" is now provably true.

---

## 7. Risks + mitigations

| Risk | Mitigation |
|---|---|
| Row B (path extraction) surfaces undocumented Windows assumptions in LanceDB or a vendored dep | Start Row B audit in parallel with A; if surface area exceeds 1 dev-day, scope creep flag → re-estimate before committing. |
| Hetzner regional outage during near-term operation | Per plan-b §5.2 fallback trigger: move to Fly.io if Hetzner sustained outage > 24h or repeated <99% availability for 3 months. Fallback shape documented; not engaged until observed. |
| Tunnel auth regression during provider-swap | Row D includes Layer-1 canary probe immediately post-deploy + Hard Rule 10 post-change discipline. |
| Host local dev setup breaks after path-extraction refactor | Row B acceptance requires Windows-host behavior unchanged when `WORKFLOW_DATA_DIR` is unset. Regression test in tests/smoke/ covers both Unix + Windows default resolution. |
| Remote box starts empty but user-sim actually needs a universe | Box-starts-empty decision made in §3. If evidence surfaces post-deploy that a universe IS needed public-side, add a one-off data-seeding commit — additive, not re-architecture. |
| 48h offline trial during host travel / real use | Trial period can be any 48 consecutive hours; host picks a low-stakes window. Do NOT gate acceptance on trial completion — acceptance is "when 48h clean has happened," not "immediately." |
| OS patch cadence adds ~2-4 ops-hours/month | Accepted cost. Plan-b §6.6 documents this tradeoff; the always-works criterion weighed OS maintenance below control-plane-fate-sharing. Host runs `apt upgrade` + reboot on a monthly cron or delegates per SUCCESSION.md. |

---

## 8. What this plan does NOT decide

- **Full plan-b migration (Supabase → Hetzner / everything OSS-self-host).** That's `docs/specs/2026-04-19-plan-b-selfhost-migration-playbook.md` — executes when triggers fire per playbook §1. Near-term plan deliberately NOT that.
- **Multi-region / HA / load-test-at-scale.** Track J (per `docs/design-notes/2026-04-18-full-platform-architecture.md` §10) — pre-launch scale validation, not near-term.
- **CI/CD pipeline for the remote box.** First-ship uses manual `rsync + docker compose pull + up -d` to the Hetzner box. Automated deploy on push → later improvement.
- **Custom-domain TLS from the provider's origin** (beyond the Cloudflare-Origin-CA relationship). Existing Cloudflare CA cert (15-year validity per plan-b §3.5.3) fronts the provider; no new cert work.
- **Secrets migration for wallet / paid-market.** Those don't exist yet; Track A ships first, then wallet secrets join the Q-uptime-2 posture.
- **Dev → prod promotion flow.** Out of scope; today's question is "can host's computer be offline." Multi-env plumbing comes when there's a reason for staging.

---

## 9. Follow-up — merge into plan-b

After near-term ships + 48h trial green:

1. Update `docs/specs/2026-04-19-plan-b-selfhost-migration-playbook.md` §2 target architecture row "Gateway" to reflect Hetzner as current state rather than future assumption. Plan-b is now primarily about Supabase-escape scenarios (§5.1) rather than Gateway-escape; the near-term plan collapsed "plan-b for Gateway" into "current state for Gateway."
2. Add §3.5 "Pre-migration readiness — daemon/tunnel portability" as a warm path; Rows A+B+C artifacts from this plan ARE that warm path.
3. Cancel the host-machine-as-primary assumption anywhere it persists in docs (grep TBD).

Navigator owns the merge; ~0.25 nav-day after the 48h trial closes.

---

## 10. Summary for dispatcher

- **Scope:** MCP daemon + tunnel origin off the host machine. Near-term, not full plan-b.
- **Provider:** **Hetzner Cloud CX22 (Debian 12, Docker Compose).** Single pick, no host round-trip. Fallback: Fly.io (only on observed primary regression). Anti: Cloudflare Workers (rewrite cost too high).
- **Internal decisions pre-made (§3):** secrets = systemd EnvironmentFile; Postgres = Supabase managed; host machine = dev seat only; first box = empty.
- **Canonical URL architecture (§0):** user-facing `tinyassets.io/mcp` via Cloudflare Worker; debug `mcp.tinyassets.io/mcp` via tunnel direct; `api.tinyassets.io/mcp` never live, don't resurrect.
- **7 Work rows, all dispatchable immediately — no host input blocks dispatch:** containerize (0.5d), extract paths (0.5-1d), tunnel config (0.25-0.5d), Hetzner deploy (1-1.5d), Cloudflare Worker (0.5d independent of deploy), smoke + 48h trial (0.25d + wall), docs sweep follow-up (0.5-1d post-trial). Rows A + C parallel; B serial; E (Worker) parallel post-A; D after A/B/C; F after D+E; G after F.
- **Total active dev:** ~3.75-5.25 dev-days. Calendar 6-9 days to sweep closed; **user-facing canonical URL restores on Row E ship (~1-2 days from dispatch).**
- **Cutover gate:** host's computer offline for 48 consecutive hours, zero canary reds on BOTH canonical + direct-origin URLs. That's the real acceptance.

Go.
