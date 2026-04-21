---
title: DNS + tunnel single-entry cutover runbook
date: 2026-04-20
author: navigator
directive: host-directive-2026-04-20 — retire mcp.tinyassets.io/mcp; canonical = tinyassets.io/mcp only
status: ACTIVE — Option 1 (CF Access service token) ratified 2026-04-20
---

# DNS + Tunnel Single-Entry Cutover Runbook

Retire `mcp.tinyassets.io` as a publicly *reachable* surface while preserving it as
internal tunnel-routing plumbing. After this runbook completes, `tinyassets.io/mcp`
is the sole public entry point; direct connections to `mcp.tinyassets.io` are blocked
by Cloudflare Access (HTTP 403).

**Why.** Extra public URL = extra attack surface. The 2026-04-19 P0 (`api.tinyassets.io`
appearing then disappearing during a tunnel reshuffle) demonstrated that secondary DNS
records create ambiguity and silent-fail risks.
PLAN.md design decision: System Shape § "Single canonical public entry point."

**Architecture constraint.** `deploy/cloudflare-worker/worker.js:31` uses
`mcp.tinyassets.io` as the tunnel origin for Worker subrequests — deleting the CNAME
would break the Worker. The CNAME stays; public access is blocked via Cloudflare Access.
Options analysis: `docs/design-notes/2026-04-20-single-entry-execution-options.md`.

---

## Pre-cutover: establish baseline

Run this first. If it fails, do NOT proceed — fix the canonical URL first.

```
POST https://tinyassets.io/mcp
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"runbook-probe","version":"1.0"}}}
```

Expected: HTTP 200, JSON response with `result.serverInfo`. Any other result = canonical URL broken; stop.

Script equivalent (run from any machine with curl):

```bash
curl -s -X POST https://tinyassets.io/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"runbook-probe","version":"1.0"}}}' \
  | python3 -m json.tool
```

Or use the repo canary:

```bash
python scripts/mcp_public_canary.py
```

Save the output — this is your green baseline before the cutover.

---

## Step 1: Create the Cloudflare Access application for `mcp.tinyassets.io`

This step gates the tunnel-routing hostname so only the Worker can reach it.
The CNAME is NOT deleted — it stays as internal plumbing.

**1a. Create a Service Token**

Cloudflare dashboard → Zero Trust → Access → Service Auth → **Service Tokens** → **Create Service Token**.

- Name: `workflow-mcp-worker`
- Token duration: Non-expiring (or set a long rotation schedule — your call)
- Click **Generate Token**

Copy both values immediately — the `Client Secret` is shown only once:
- `CF-Access-Client-Id`: looks like `<uuid>.access`
- `CF-Access-Client-Secret`: long hex string

**1b. Create an Access Application**

Zero Trust → Access → Applications → **Add an Application** → **Self-hosted**.

- **Application name:** `workflow-daemon-tunnel`
- **Application domain:**
  - Subdomain: `mcp`
  - Domain: `tinyassets.io`
  - Path: (leave blank — protects the whole subdomain)
- **Session Duration:** 24 hours
- Click **Next**

On the policy screen:
- **Policy name:** `worker-only`
- **Action:** Service Auth
- **Include rule:** Service Token = `workflow-mcp-worker` (select from dropdown)
- Click **Next**, then **Save**

After saving, Cloudflare Access is now active on `mcp.tinyassets.io`. Direct browser/curl
requests without the service token headers get a Cloudflare Access login redirect or 403.

**1c. Add the service token as Worker secrets**

The Worker must present these headers to every subrequest it makes to `mcp.tinyassets.io`.

Via Wrangler CLI (recommended — avoids copy-paste in the dashboard):

```bash
cd deploy/cloudflare-worker
wrangler secret put CF_ACCESS_CLIENT_ID
# paste the Client Id value when prompted

wrangler secret put CF_ACCESS_CLIENT_SECRET
# paste the Client Secret value when prompted
```

Via Cloudflare dashboard:
Workers & Pages → `workflow-mcp-router` → Settings → Variables and Secrets →
**Add variable** → Type: **Secret** → Name: `CF_ACCESS_CLIENT_ID` → value → Save.
Repeat for `CF_ACCESS_CLIENT_SECRET`.

**1d. Deploy updated worker.js**

Dev ships the 3-line worker.js change (add `env` to handler signature + inject Access
headers on subrequests). Wait for that deploy to propagate (~30s) before running
post-cutover verification. The worker.js change is tracked in the Task #7 dev work.

---

## Step 2: (No cloudflared config change required)

The `mcp.tinyassets.io` ingress entry in cloudflared config is **kept**. The tunnel
still routes that hostname — that's correct. Access gates who can reach it via DNS,
not whether the tunnel serves it. No cloudflared restart needed for this cutover.

---

## Step 3: (No DNS change required)

The `mcp.tinyassets.io` CNAME is **kept**. It resolves publicly (expected), but no
unauthorized client can get a valid response — Cloudflare Access intercepts before
the request reaches the tunnel. No DNS edits needed.

---

## Post-cutover verification

Run all three checks. All three must pass.

### Check 1 — canonical URL still green

```bash
python scripts/mcp_public_canary.py
```

Expected: same green output as pre-cutover baseline. Any failure = stop; do not mark
cutover complete until this is green.

### Check 2 — `mcp.tinyassets.io` direct access is blocked

```bash
curl -si https://mcp.tinyassets.io/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"access-probe","version":"1.0"}}}' \
  | head -5
```

Expected: HTTP **401** or **403** from Cloudflare Access, OR a redirect to the
Cloudflare Access login page (302 with `Location: <team>.cloudflareaccess.com`).

NOT acceptable: HTTP 200 with a valid MCP `result.serverInfo` response. If you see
200, the Access application is not protecting the subdomain — re-check Step 1b policy
configuration before proceeding.

### Check 3 — Worker subrequest still reaches the tunnel (end-to-end via canonical)

Check 1 covers this indirectly (canonical green = Worker → tunnel path working), but
if you want an explicit confirmation that the Access headers are being injected
correctly, tail the Worker logs while running the canary:

```bash
# In one terminal — tail live Worker logs
cd deploy/cloudflare-worker && wrangler tail

# In another terminal — trigger a canonical probe
python scripts/mcp_public_canary.py
```

Expected in Worker tail: a request log entry for `POST /mcp` with status 200 and no
`CF-Access` authentication error. Any `401` in the Worker tail on a canonical-URL
request means the Worker's own secrets are not being injected — verify Step 1c and
redeploy worker.js.

---

**All three green = cutover complete.** Update the STATUS.md Work row for
"Single-entry execution — Option 1 impl" to `done`.

---

## Observability after cutover (replaces dual-URL localization)

The dual-URL probe localization trick (green on `tinyassets.io` + red on `mcp.tinyassets.io` = Worker layer OK, tunnel broken) is retired with this cutover. Replacement observability:

**Cloudflare Worker logs:**
- Dashboard → `tinyassets.io` zone → Workers Routes → click the Worker → Logs (real-time) or Analytics.
- A Worker-layer failure shows: zero requests reaching the Worker, or Worker returning 5xx before forwarding.

**Cloudflared tunnel logs:**
- `journalctl -u cloudflared -f` (Linux systemd) or Windows Event Viewer → Application → cloudflared.
- A tunnel failure shows: `ERR` lines, connection drops, "failed to serve" entries.

**Layer-1 canary (`scripts/uptime_canary.py`):**
- Probes `tinyassets.io/mcp` every N minutes and opens a GitHub issue on failure.
- Single-URL canary is correct for single-URL architecture. The `WORKFLOW_MCP_CANARY_URL` env var controls which URL is probed; confirm it is set to `https://tinyassets.io/mcp`.

---

## Rollback path

Since no DNS or cloudflared config changes were made, rollback is simply removing
the Access application:

1. Zero Trust → Access → Applications → `workflow-daemon-tunnel` → **Delete**.
2. `mcp.tinyassets.io` immediately becomes publicly reachable again (no propagation delay).
3. The Worker continues to work either way — the Access headers it sends are ignored
   if no Access application is protecting the subdomain.

**Note:** Rollback is for emergency diagnosis only. The PLAN.md design decision
argues against a second public surface at steady state. After recovery, re-enable
the Access application and investigate root cause.

---

## Canary env var confirmation

After cutover, confirm the canary is pointed at the right URL.

In `/etc/workflow/env` (or wherever the daemon env is managed):

```
WORKFLOW_MCP_CANARY_URL=https://tinyassets.io/mcp
```

If it still reads `https://mcp.tinyassets.io/mcp`, update it. The Layer-1 canary
probing an Access-blocked URL will hard-fail on every probe otherwise.

Commit the env change via `deploy-prod.yml` or update the host's env file directly,
depending on how env is managed post-DO-cutover.

---

## Follow-up: test / pre-commit invariant (low priority)

After the Option 1 worker.js change ships, add a test to `worker.test.js` asserting
that subrequests to `mcp.tinyassets.io` include both `CF-Access-Client-Id` and
`CF-Access-Client-Secret` headers (sourced from `env`). This guards against a future
worker.js refactor accidentally dropping the Access header injection.

Tracked as a follow-up; not a blocker for the cutover itself.
