# Day-of-Cutover Runbook

**Single source of truth for the host's activation day.** Every account to create, every secret to paste, every command to run — in order, with no scavenger hunt.

**Target:** `https://tinyassets.io/mcp` stays green with host's home machine off. Total host time ~60-75 min end-to-end (~20 min of which is account signups). Most of the heavy lifting is checked-in scripts + GitHub Actions — host fills creds once; pipelines take over.

**Prereq:** you're reading this on the day you're ready to flip. If Row D / Row H / Row J / Row K / Row M / Row N haven't all landed yet, stop; see `docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md` for row status.

---

## 0. What you're about to do

Five stages, top to bottom:

1. **Account signups** (~15 min, host-only) — Hetzner, Supabase, Hetzner Storage Box, Better Stack, Cloudflare API token, GitHub OAuth app.
2. **Credential collection** (~10 min, host-only) — one table; paste values into a scratch doc.
3. **GitHub secrets + variables** (~5 min, host-only) — paste from the scratch doc into repo settings.
4. **Hetzner provisioning + activation** (~20 min, mostly automated) — run bootstrap, fill `/etc/workflow/env`, start the service.
5. **Cutover + post-cutover smoke** (~10 min) — verify canary green, power off home machine, watch for 10 min, done.

After Stage 5 + a 48h-host-offline trial, the §6 acceptance in the exec plan closes and the host's computer is provably replaceable.

---

## Stage 1 — Account signups

Do these in any order. Each box = one account. Cost column shows monthly commitment.

- [ ] **Hetzner Cloud** — `https://accounts.hetzner.com/signUp`. Email + card. €5.83/mo CX22.
- [ ] **Hetzner Storage Box** — `https://www.hetzner.com/storage/storage-box`. BX11 plan, ~€4/mo (100 GB). Same account as Hetzner Cloud works; billing is separate line item.
- [ ] **Supabase** — `https://supabase.com/dashboard/sign-up`. GitHub login. Create a project (name: `workflow-prod`, region: closest to your users, Postgres version: latest). Pro plan $25/mo — upgrade when you're ready to commit; free tier works for day-of-cutover testing.
- [ ] **Better Stack** — `https://betterstack.com/users/sign-up`. Free tier is fine (3 GB/mo logs, 3-day retention). Create a Source: "Vector" → Linux → note the source token.
- [ ] **Cloudflare API token** — `https://dash.cloudflare.com/profile/api-tokens` → **Create Token** → **Custom token**:
  - Permissions: `Zone:DNS:Edit` on `tinyassets.io` zone, `Account:Workers Routes:Edit`.
  - Token TTL: 1 year (set calendar reminder).
  - Copy the token once — it's not retrievable.
- [ ] **GitHub OAuth App** — `https://github.com/settings/applications/new`:
  - Application name: `Workflow`.
  - Homepage URL: `https://tinyassets.io`.
  - Authorization callback URL: `https://tinyassets.io/authorize/github/callback`.
  - After creation: copy Client ID; click **Generate a new client secret**; copy secret once.
- [ ] **GHCR image registry** — no signup; uses your existing GitHub account. First `.github/workflows/build-image.yml` run on main-branch push will publish the image. Verify at `https://github.com/<your-username>?tab=packages` after first build.

**Cost summary (monthly):**

| Line item | $/mo |
|---|---|
| Hetzner CX22 | ~$6.50 |
| Hetzner Storage Box BX11 | ~$4.50 |
| Supabase Pro | $25 |
| Cloudflare (Free + Worker free tier) | $0 |
| Better Stack (Free) | $0 |
| GitHub Actions + GHCR | $0 (public repo) |
| **Total** | **~$36** |

---

## Stage 2 — Credential collection

Open a scratch text file on your desktop (don't commit to git). Fill in these values as you collect them. You'll paste into `/etc/workflow/env` in Stage 4 and GitHub secrets in Stage 3.

```
# Scratch — DO NOT COMMIT

# Hetzner
HETZNER_API_TOKEN=          # Hetzner Cloud Console → Security → API Tokens → Create → Read & Write
HETZNER_SSH_PUBKEY_NAME=    # name of SSH key you registered (not the key itself)
HETZNER_BOX_IP=             # filled in during Stage 4 after box provisions

# Hetzner Storage Box
STORAGE_BOX_HOST=           # Storage Box dashboard → "SMB/Samba" or "BorgBackup" tab → hostname
STORAGE_BOX_USER=           # same tab → username
STORAGE_BOX_PASSWORD=       # same tab → generated password (not your Hetzner account password)

# Supabase
SUPABASE_DB_URL=            # Project Settings → Database → Connection string → Connection pooling (port 6543) → URI
SUPABASE_SERVICE_ROLE_KEY=  # Project Settings → API → service_role key

# Cloudflare
CLOUDFLARE_API_TOKEN=       # from Stage 1
CLOUDFLARE_ZONE_ID=         # dash.cloudflare.com → tinyassets.io → Overview → right-hand sidebar → Zone ID
CLOUDFLARE_TUNNEL_TOKEN=    # Zero Trust → Networks → Tunnels → workflow-daemon-prod → Connectors → Install tunnel → copy "Token" field
                            #   (Create the tunnel first if it doesn't exist: Zero Trust → Networks → Tunnels → Create a tunnel → "Cloudflared" → name=workflow-daemon-prod
                            #    → save → skip the connector-install page, just copy the token.
                            #    Then: Public Hostname tab → Add hostname → mcp.tinyassets.io → Service: http://localhost:8001)

# GitHub
GITHUB_OAUTH_CLIENT_ID=     # github.com/settings/developers → OAuth Apps → Workflow → Client ID
GITHUB_OAUTH_CLIENT_SECRET= # same page → Generate a new client secret

# Better Stack
BETTERSTACK_SOURCE_TOKEN=   # Better Stack dashboard → Sources → workflow-daemon → source token

# SSH deploy key (Stage 3.2)
DEPLOY_SSH_PRIVATE_KEY=     # generate in Stage 3.2, fill after
```

**Env-var mapping cheat sheet** — what goes where:

| Credential | Goes into `/etc/workflow/env` on Hetzner box? | Goes into GitHub repo secrets? | Goes into GitHub repo variables? |
|---|---|---|---|
| `CLOUDFLARE_TUNNEL_TOKEN` | YES | — | — |
| `SUPABASE_DB_URL` | YES | — | — |
| `SUPABASE_SERVICE_ROLE_KEY` | YES | YES (for future migration runs via GHA) | — |
| `GITHUB_OAUTH_CLIENT_ID` | YES | — | — |
| `GITHUB_OAUTH_CLIENT_SECRET` | YES | — | — |
| `BETTERSTACK_SOURCE_TOKEN` | YES | — | — |
| `CLOUDFLARE_API_TOKEN` | — | YES (for `emergency-dns.yml`) | — |
| `CLOUDFLARE_ZONE_ID` | — | YES | — |
| `HETZNER_API_TOKEN` | — | YES (for future hcloud scripts) | — |
| `DEPLOY_SSH_PRIVATE_KEY` | — | YES (for Row M `deploy-prod.yml`) | — |
| `DEPLOY_SSH_HOST` (= `HETZNER_BOX_IP`) | — | YES | — |
| `DEPLOY_SSH_USER` (default: `root`) | — | YES | — |
| `CLOUDFLARE_ZONE_NAME` (= `tinyassets.io`) | — | — | YES |

---

## Stage 3 — GitHub secrets + variables

### 3.1 Paste secrets + variables into the repo

Navigate to `https://github.com/jfarnsworth/workflow/settings/secrets/actions`. Click **New repository secret** for each:

- [ ] `CLOUDFLARE_API_TOKEN`
- [ ] `CLOUDFLARE_ZONE_ID`
- [ ] `HETZNER_API_TOKEN`
- [ ] `SUPABASE_SERVICE_ROLE_KEY`
- [ ] `DEPLOY_SSH_HOST` (value = `HETZNER_BOX_IP` from Stage 4; come back after provisioning)
- [ ] `DEPLOY_SSH_USER` (value: `root` for first cut, `workflow` later if you harden)
- [ ] `DEPLOY_SSH_PRIVATE_KEY` (see 3.2 below — comes back here)

Then **Variables** tab:

- [ ] `CLOUDFLARE_ZONE_NAME` = `tinyassets.io`

### 3.2 Generate the deploy SSH key (~1 min)

On your laptop:

```bash
ssh-keygen -t ed25519 -C "workflow-deploy" -f ~/.ssh/workflow_deploy -N ""
```

Two files appear:

- `~/.ssh/workflow_deploy` — **private**. Paste contents into GitHub secret `DEPLOY_SSH_PRIVATE_KEY`.
- `~/.ssh/workflow_deploy.pub` — public. You'll add this to the Hetzner box in Stage 4 Step 2 (after bootstrap). Keep the file handy.

### 3.3 Set `SECRETS_EXPIRY_METADATA_JSON` repo variable

Variables tab → `SECRETS_EXPIRY_METADATA_JSON`:

```json
[
  {"name":"CLOUDFLARE_API_TOKEN","provider":"cloudflare","expires_on":"2027-04-20","runbook":"docs/ops/host-independence-runbook.md#emergency-dns"},
  {"name":"HETZNER_API_TOKEN","provider":"hetzner","expires_on":"2027-04-20","runbook":"docs/ops/host-independence-runbook.md"},
  {"name":"SUPABASE_SERVICE_ROLE_KEY","provider":"supabase","expires_on":"2027-04-20","runbook":"docs/ops/host-independence-runbook.md"},
  {"name":"GITHUB_OAUTH_CLIENT_SECRET","provider":"github","expires_on":"2027-04-20","runbook":"docs/ops/host-independence-runbook.md"},
  {"name":"CLOUDFLARE_TUNNEL_TOKEN","provider":"cloudflare","expires_on":"2027-04-20","runbook":"deploy/HETZNER-DEPLOY.md"}
]
```

The monthly `secrets-expiry-check.yml` workflow reads this and opens a GitHub issue 30 days before any expiry.

### 3.4 Trigger first GHCR build

If no image tag exists yet on GHCR, trigger a build before proceeding:

- [ ] Go to **Actions** tab → `build-image.yml` → **Run workflow** → branch: `main` → Run.
- [ ] Wait for green (~5-8 min).
- [ ] Verify: `https://github.com/jfarnsworth?tab=packages` shows `workflow-daemon:latest`.

---

## Stage 4 — Hetzner provisioning + activation

Follows `deploy/HETZNER-DEPLOY.md` with the credential table above pre-filled.

### Step 4.1 — Register SSH key in Hetzner (~1 min)

- [ ] Hetzner Cloud Console → **Security** → **SSH Keys** → **Add SSH Key** → paste `~/.ssh/workflow_deploy.pub` contents → name it `workflow-deploy`.

### Step 4.2 — Provision the CX22 (~5 min)

- [ ] Hetzner Cloud Console → **Servers** → **Add Server**:
  - Location: Falkenstein (FSN1) or Nuremberg (NBG1).
  - Image: Debian 12.
  - Type: Shared vCPU → **CX22**.
  - Networking: public IPv4 + IPv6 both ON.
  - Firewall: create + attach `workflow-daemon`:
    - Inbound: SSH (22) from your admin IP only + ICMP.
    - Do NOT open 8001.
    - Outbound: all.
  - SSH key: select `workflow-deploy`.
  - Name: `workflow-daemon-prod-01`.
- [ ] Wait for status → green. Copy the public IPv4 into your scratch doc as `HETZNER_BOX_IP`.
- [ ] Back to GitHub secrets (Stage 3.1) → set `DEPLOY_SSH_HOST` = this IP.

### Step 4.3 — Bootstrap the box (~3 min)

From your laptop:

```bash
ssh -i ~/.ssh/workflow_deploy root@<HETZNER_BOX_IP>
```

On the box:

```bash
curl -fsSL https://raw.githubusercontent.com/jfarnsworth/workflow/main/deploy/hetzner-bootstrap.sh -o /tmp/bootstrap.sh
sudo bash /tmp/bootstrap.sh
```

Script is idempotent. Ends with `[bootstrap] bootstrap complete.`

### Step 4.4 — Fill `/etc/workflow/env` (~3 min)

On the box:

```bash
sudo nano /etc/workflow/env
```

Paste from your Stage 2 scratch doc (keeping existing comments):

```
WORKFLOW_IMAGE=ghcr.io/jfarnsworth/workflow-daemon:latest
CLOUDFLARE_TUNNEL_TOKEN=<paste>
WORKFLOW_MCP_CANARY_URL=https://tinyassets.io/mcp
SUPABASE_DB_URL=<paste>
SUPABASE_SERVICE_ROLE_KEY=<paste>
GITHUB_OAUTH_CLIENT_ID=<paste>
GITHUB_OAUTH_CLIENT_SECRET=<paste>
BETTERSTACK_SOURCE_TOKEN=<paste>
```

Save (`Ctrl+O`, `Enter`, `Ctrl+X`).

Verify permissions:

```bash
ls -la /etc/workflow/env
# Expect: -rw-r----- 1 root workflow ...
```

If mode is wrong, re-run the bootstrap — it resets to `root:workflow 640`.

### Step 4.5 — Configure Storage Box backup target (~2 min)

On the box:

```bash
sudo mkdir -p /etc/workflow/backup
sudo tee /etc/workflow/backup/rclone.conf > /dev/null <<EOF
[storagebox]
type = sftp
host = <STORAGE_BOX_HOST>
user = <STORAGE_BOX_USER>
pass = $(echo -n '<STORAGE_BOX_PASSWORD>' | rclone obscure -)
port = 23
EOF
sudo chmod 600 /etc/workflow/backup/rclone.conf
sudo chown root:workflow /etc/workflow/backup/rclone.conf
```

(The Row J backup script reads this; Row J ships `/opt/workflow/deploy/backup.sh` + the systemd timer.)

### Step 4.6 — Start the daemon (~30 sec)

```bash
sudo systemctl start workflow-daemon
sudo systemctl status workflow-daemon
```

Expect **active (running)**. First start pulls the image (~30s extra).

Tail logs in a separate terminal:

```bash
sudo journalctl -u workflow-daemon -f
```

Look for:
- `daemon-1 | Starting Workflow Server on 0.0.0.0:8001 (transport=streamable-http)` — daemon bound.
- `cloudflared | Registered tunnel connection connIndex=0` — tunnel up.
- `vector | Connected to Better Stack` (if Row K shipped) — logs flowing.

### Step 4.7 — Enable Row L watchdog (~1 min)

```bash
sudo systemctl enable --now workflow-watchdog.timer
sudo systemctl list-timers workflow-watchdog.timer
```

Expect timer active. Watchdog probes `/mcp` every 30 s; 3 consecutive fails → `systemctl restart workflow-daemon`; 5 restarts in 10 min → stops + fires a GitHub issue via Row H alarm sink.

### Step 4.8 — Enable Row J backup (~1 min)

```bash
sudo systemctl enable --now workflow-backup.timer
sudo systemctl list-timers workflow-backup.timer
```

Timer fires nightly at 03:00 UTC. Verify manually once:

```bash
sudo systemctl start workflow-backup.service
sudo journalctl -u workflow-backup.service --since "5 minutes ago"
# Expect: rsync completed, snapshot at storagebox:/workflow/YYYY-MM-DD/
```

---

## Stage 5 — Cutover + post-cutover smoke

### Step 5.1 — Verify both URLs green (~1 min)

From your laptop:

```bash
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --verbose
python scripts/mcp_public_canary.py --url https://mcp.tinyassets.io/mcp --verbose
```

Both should print `[canary] OK` + exit 0. If asymmetric, see Diagnosis table in `deploy/HETZNER-DEPLOY.md`.

### Step 5.2 — Verify cloud canary running (~1 min)

- [ ] GitHub → Actions → `uptime-canary.yml` → confirm most recent run is green (< 10 min ago).
- [ ] Check Issues — no open issues labeled `p0-outage`.

### Step 5.3 — Power off home tunnel (~30 sec)

Home machine, Windows tray:
- Right-click Workflow tray icon → **Stop cloudflared**.

Or manually:

```powershell
taskkill /F /IM cloudflared.exe
```

Leave it off. The Hetzner tunnel is now sole origin.

### Step 5.4 — Watch for 10 minutes

- [ ] From your laptop, run the canary every 2 min for 10 min (or just watch Actions → uptime-canary.yml for the next 2 runs). All green.
- [ ] Check Better Stack dashboard — logs arriving from Hetzner box (`vector` source, lines from `workflow-daemon` container).
- [ ] Check Row J backup — `sudo systemctl list-timers` on the box shows next fire within 24h.

### Step 5.5 — Power off the home machine

If all of 5.1-5.4 are green, the home machine is no longer load-bearing.

- [ ] Shutdown / hibernate the home machine.
- [ ] Leave powered off for 48 consecutive hours (pick a low-stakes window — travel, weekend, etc.).
- [ ] During the 48h window: Row H canary runs every 5 min from GHA; any red opens a GitHub issue.
- [ ] At hour 48, if zero reds on either URL + zero open `p0-outage` issues + Row J backup fired at least once → **§6 acceptance closed.** The host's computer is provably replaceable.

---

## Rollback

If anything goes red between Step 4.6 and Step 5.5, rollback is additive-clean (home tunnel never went down):

- [ ] On Hetzner: `sudo systemctl stop workflow-daemon`.
- [ ] Home machine: re-start the cloudflared tray → "Start cloudflared". The home tunnel is the original origin; Cloudflare's tunnel DNS points at whichever connector is up. With Hetzner stopped + home up, `mcp.tinyassets.io/mcp` resolves back to home.
- [ ] Run the canary: `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp`. Expect green.
- [ ] Open a GitHub issue titled `Cutover rollback: <date>` describing what went red + `journalctl` excerpt. Resume troubleshooting; schedule retry.

**If both tunnels are running simultaneously (pre-Step-5.3):** Cloudflare load-balances across connectors; both are serving the same daemon contract via different origins — traffic is safe, dual-origin race is harmless for MCP (stateless per request).

**If canary stays red past Step 5.4 AND you can't reach the box:** Hetzner Console → your server → **Rescue** tab → enable Rescue mode → reboot into Rescue → SSH in with Hetzner's rescue password to read `/var/log/` before deciding whether to destroy + redeploy.

**If the Worker at `tinyassets.io/mcp` is the broken layer (red apex, green subdomain):** the Worker route is independent. `cd deploy/cloudflare-worker && wrangler deploy` from a laptop with the Cloudflare token republishes. Or use `emergency-dns.yml` workflow with `delete-worker-route` to remove the route entirely (apex falls back to whatever is behind it).

---

## After cutover — what happens automatically

These pipelines run without host action. Host just reads GitHub notifications.

- **Uptime canary** (`.github/workflows/uptime-canary.yml`) — every 5 min, probes both URLs, opens `p0-outage` issue on 2 consecutive reds, auto-closes on 3 consecutive greens.
- **Image builds** (`.github/workflows/build-image.yml`) — on every push to main, builds + publishes to GHCR with `latest` + short-SHA tags.
- **Deploy pipeline** (`.github/workflows/deploy-prod.yml`, Row M) — on every push to main after image build green, SSHs to Hetzner, `docker compose pull && up -d`, runs post-deploy canary, auto-rollback on red.
- **Secrets expiry** (`.github/workflows/secrets-expiry-check.yml`) — monthly, opens an issue 30 days before any secret in `SECRETS_EXPIRY_METADATA_JSON` expires.
- **Nightly backup** (systemd timer on box, Row J) — 03:00 UTC, rsync to Storage Box, 7-day + 4-week + 12-month retention.
- **Watchdog** (systemd timer on box, Row L) — 30 s probe, restart on hang, stop-flap safety at 5 restarts / 10 min.
- **Logs** (Vector sidecar on box, Row K) — stream to Better Stack continuously.

Host-required actions going forward:
- **Annual:** rotate Cloudflare + Hetzner + Supabase + GitHub-OAuth secrets when `SECRET EXPIRY` issues fire.
- **Annual:** pre-pay Hetzner 12 months (Row N step §1).
- **At Row-D + 30 days:** switch Supabase to annual prepay (Row N).
- **As needed:** approve + merge PRs. Deploy pipeline takes it from there.

---

## Troubleshooting appendix

| Symptom | Most-likely cause | Fix |
|---|---|---|
| `systemctl start workflow-daemon` hangs | First image pull slow over Hetzner's NAT | Wait ~60 s; check `docker ps -a` for `workflow-daemon` status |
| `docker logs workflow-tunnel` shows `Unauthorized` | `CLOUDFLARE_TUNNEL_TOKEN` wrong or token regenerated | Re-copy from Cloudflare Zero Trust dashboard; edit `/etc/workflow/env`; `systemctl restart workflow-daemon` |
| Canary green from Hetzner box but red from laptop | DNS propagation or Cloudflare caching | Wait 5 min; flush local DNS: `ipconfig /flushdns` (Win) or `sudo dscacheutil -flushcache` (Mac) |
| `docker compose pull` fails with "unauthorized" | GHCR image is private (should be public) | Option A: make package public at `github.com/<user>?tab=packages` → workflow-daemon → Package settings → Change visibility. Option B: add `docker login ghcr.io -u <user> -p <PAT-with-read:packages>` to bootstrap |
| Better Stack shows no logs | `BETTERSTACK_SOURCE_TOKEN` wrong or Vector sidecar not running | `docker ps` — look for `workflow-logs` container. `docker logs workflow-logs` — Vector config errors print here |
| Backup fails with "permission denied" on Storage Box | Wrong password in `/etc/workflow/backup/rclone.conf`, or password not obscured via `rclone obscure` | Rewrite config per Step 4.5; ensure password is passed through `rclone obscure -` before writing |
| Watchdog flap loop (5 restarts in 10 min) | Daemon crash-looping on startup — bad config or missing env var | Stop watchdog: `systemctl stop workflow-watchdog.timer`. Read `journalctl -u workflow-daemon` for root cause. Fix `/etc/workflow/env` or image tag. |
| `emergency-dns.yml` dry-run fails with "403" | `CLOUDFLARE_API_TOKEN` scope missing `Zone:DNS:Edit` | Regenerate token with correct scopes; paste into `CLOUDFLARE_API_TOKEN` secret |

---

## References

- `deploy/HETZNER-DEPLOY.md` — canonical Hetzner deploy runbook this consolidates.
- `docs/ops/host-independence-runbook.md` — bills + DNS + secrets rotation details (Row N).
- `docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md` — full exec plan with all 14 rows.
- `docs/design-notes/2026-04-19-uptime-canary-layered.md` — canary design.
- `SUCCESSION.md` — what happens if the host can't maintain this.
