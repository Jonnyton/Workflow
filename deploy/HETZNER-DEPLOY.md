# Hetzner Cloud — Workflow daemon deploy runbook

Self-host migration Row D per
`docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md`.

**Target:** Hetzner Cloud **CX22** (4 vCPU / 8 GB RAM / 80 GB SSD — €5.83/mo),
**Debian 12** image, Falkenstein (FSN1) or Nuremberg (NBG1) region.

**Outcome:** `https://tinyassets.io/mcp` stays green even when the host
machine is powered off. 48-hour-offline acceptance gate lives at Row F;
this runbook gets you to the single-host green state.

---

## Prerequisites

- Hetzner Cloud account + a project provisioned (free; billing card on file).
- SSH keypair registered in Hetzner Cloud → Security → SSH Keys.
- Domain `tinyassets.io` managed by Cloudflare (already true post-P0).
- Cloudflare Zero Trust tunnel `workflow-daemon-prod` already created
  (or a new tunnel you'll create at step 3). Token in hand.
- Supabase project provisioned (for Track A schema + auth).
- GitHub OAuth app registered with callback
  `https://tinyassets.io/authorize/github/callback`.

## Step 1 — Provision the CX22 (~5 min)

Via Hetzner Cloud Console (or `hcloud` CLI):

1. **Servers → Add Server**.
2. **Location:** Falkenstein or Nuremberg.
3. **Image:** Debian 12.
4. **Type:** Shared vCPU → CX22 (Standard).
5. **Networking:** public IPv4 + IPv6 both on. Optional: private network
   if you want to add more boxes later.
6. **SSH keys:** select your registered key.
7. **Firewalls:** create + attach `workflow-daemon` firewall:
   - Inbound: SSH (22) from your admin IP only, ICMP open.
   - **Do NOT** open 8001 — the daemon binds loopback-only.
   - Outbound: all.
8. **Name:** `workflow-daemon-prod-01`.
9. **Cloud-config** (optional): none needed; bootstrap handles provisioning.

Wait for status → green. Copy the public IPv4.

## Step 2 — Bootstrap the box (~3 min)

SSH in:

```bash
ssh root@<public-ipv4>
```

Run the bootstrap script. Two paths:

**Path A (recommended — single command):**

```bash
curl -fsSL https://raw.githubusercontent.com/jfarnsworth/workflow/main/deploy/hetzner-bootstrap.sh \
    -o /tmp/bootstrap.sh
sudo bash /tmp/bootstrap.sh
```

**Path B (local clone — if you want to review first):**

```bash
git clone https://github.com/jfarnsworth/workflow.git /tmp/workflow-src
sudo bash /tmp/workflow-src/deploy/hetzner-bootstrap.sh
```

The script is idempotent. Re-running is safe; it skips steps whose
end-state is already reached. Expected output ends with:

```
[bootstrap] bootstrap complete.

Next steps (host action required):
  1. Fill in secrets: sudo nano /etc/workflow/env
  ...
```

## Step 3 — Fill `/etc/workflow/env` (~5 min)

Open in your editor of choice:

```bash
sudo nano /etc/workflow/env
```

Fill in these fields (template at `/opt/workflow/deploy/workflow-env.template`
documents each):

| Variable | Source |
|---|---|
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare dashboard → Zero Trust → Networks → Tunnels → (tunnel) → Connectors → Install → "Token" field. |
| `SUPABASE_DB_URL` | Supabase dashboard → Project Settings → Database → Connection string → **Pooled** (port 6543). |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard → Project Settings → API → service_role key (keep secret; never ship to clients). |
| `GITHUB_OAUTH_CLIENT_ID` | GitHub → Settings → Developer settings → OAuth Apps → Workflow → Client ID. |
| `GITHUB_OAUTH_CLIENT_SECRET` | Same page → "Generate a new client secret" → copy once. |
| `WORKFLOW_IMAGE` | Optional; default is `ghcr.io/jfarnsworth/workflow-daemon:latest`. For production pinning, use a short-SHA tag from .github/workflows/build-image.yml. |

Save + exit (`Ctrl+O`, `Enter`, `Ctrl+X` in nano).

Permissions check:

```bash
ls -la /etc/workflow/env
# -rw-r----- 1 root workflow ... env
```

If ownership/mode differs, re-run the bootstrap — it resets to
`root:workflow 640`.

## Step 4 — Start the daemon (~30 sec)

```bash
sudo systemctl start workflow-daemon
sudo systemctl status workflow-daemon
```

Expect: **active (running)**. If the container image hasn't been pulled
yet, compose pulls it inline — first start takes ~30s longer than
subsequent restarts.

Tail logs:

```bash
sudo journalctl -u workflow-daemon -f
```

Look for:
- `daemon-1 | Starting Workflow Server on 0.0.0.0:8001 (transport=streamable-http)` — daemon bound.
- `cloudflared | Registered tunnel connection connIndex=0` — tunnel up.

## Step 5 — Verify canary green (~10 sec)

From the Hetzner box (container-internal):

```bash
docker exec workflow-daemon \
    python scripts/mcp_public_canary.py \
        --url http://127.0.0.1:8001/mcp --verbose
```

Expect `[canary] OK` + exit 0.

From your laptop (public-canonical):

```bash
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --verbose
```

Expect `[canary] OK`. **This is the pass gate.** Once green, the
Hetzner box is serving the canonical URL; your home tunnel can stay
off permanently.

Also verify direct-tunnel parity:

```bash
python scripts/mcp_public_canary.py --url https://mcp.tinyassets.io/mcp --verbose
```

Expect `[canary] OK`. If apex is green but `mcp.` is red (or vice versa),
see the **Diagnosis split** section below.

## Step 6 — Power off the host tunnel (optional, only after you've watched green for 10+ min)

If you've been running the old cloudflared on your home box, it's now
redundant (dual-origin race). Stop it:

```bash
# On home box (Windows tray):
#  → Tray → "Stop cloudflared" menuitem
# OR manually:
taskkill /F /IM cloudflared.exe
```

Leave it off. The Hetzner tunnel is now the sole origin for
`mcp.tinyassets.io`.

---

## Rollback

If step 4 or 5 fails:

```bash
sudo systemctl stop workflow-daemon
# Investigate via journalctl; see Diagnosis split below.
# To fully revert:
sudo systemctl disable workflow-daemon
sudo rm /etc/systemd/system/workflow-daemon.service
sudo systemctl daemon-reload
# Destroy the box:
#   Hetzner console → Server → Delete.
```

The canonical URL stays green on your home tunnel throughout rollback
— nothing changes on the Cloudflare side until you flip DNS or disable
the home tunnel. The Hetzner deploy is fully additive until you power
off the home tunnel at Step 6.

---

## Diagnosis split (when things go red)

Two URLs gives us two signals. The color asymmetry names the broken layer.

| `tinyassets.io/mcp` | `mcp.tinyassets.io/mcp` | Diagnosis |
|---|---|---|
| green | green | All healthy. |
| red | green | **Cloudflare Worker or route broken.** The `tinyassets-mcp-proxy` Worker either isn't deployed or its route `tinyassets.io/mcp*` isn't live. Check Cloudflare dashboard → Workers → Triggers. |
| green | red | Worker is caching / returning stale responses; tunnel origin is down. Check `systemctl status workflow-daemon` on Hetzner. |
| red | red | **Tunnel or daemon down.** `systemctl status workflow-daemon` on Hetzner; `docker logs workflow-daemon` + `docker logs workflow-tunnel`. |

## Common failure modes

- **`CLOUDFLARE_TUNNEL_TOKEN` not set or wrong.** `docker logs workflow-tunnel` shows `Unauthorized` or hangs at "Tried to connect to tunnel". Fix: re-copy the token from the Cloudflare dashboard; tokens don't expire but do get regenerated on tunnel rotation.
- **Healthcheck never passes.** `docker inspect workflow-daemon | jq '.[].State.Health'` shows consecutive failures. The healthcheck runs `mcp_public_canary.py` against `http://127.0.0.1:8001/mcp`; if daemon didn't bind, check `docker logs workflow-daemon`.
- **Short-SHA image pin not pullable.** Image tag doesn't exist in GHCR. Fall back to `WORKFLOW_IMAGE=ghcr.io/jfarnsworth/workflow-daemon:latest` in `/etc/workflow/env`, `systemctl restart workflow-daemon`.
- **`/etc/workflow/env` permissions wrong.** Compose reads env file via docker; mode must allow the `workflow` user to read. `chown root:workflow /etc/workflow/env && chmod 640 /etc/workflow/env`.
- **Docker pull fails (GHCR auth).** If the image is private, the box needs a pull credential. This runbook assumes the GHCR image is public; if not, add `docker login ghcr.io` to the bootstrap + supply a PAT with `read:packages`.

---

## What this deploy does NOT include (future rows)

- **Row J (state backup).** Named volume `workflow-data` is NOT yet backed up. Lose the box + lose state. Row J adds nightly snapshots to Hetzner Storage Box (~€1/mo).
- **Row K (log aggregation).** `journalctl` is local-only. Box death loses logs.
- **Row L (daemon watchdog).** `systemd` restarts on crash, but doesn't detect hung-not-crashed (daemon alive, /mcp unresponsive). Row L adds a watchdog unit probing the canary + issuing `systemctl restart` on sustained red.
- **Row M (CI deploy pipeline).** Image updates require manual `WORKFLOW_IMAGE=<new-sha>` edit + `systemctl restart`. Row M adds merge-to-main → SSH deploy → post-deploy canary with auto-rollback.

Each of these ships independently on top of this compose + systemd
foundation. Row D is the anchor.

---

## Cost

- CX22: €5.83/mo → ~$6.50/mo at current exchange.
- Hetzner Storage Box (Row J, not yet wired): ~€1/mo for 100 GB.
- Cloudflare (all Workers traffic on free tier at current volume): $0.
- Supabase Pro (existing, not deploy-gated): $25/mo.

Total incremental cost of self-host migration: **~$7/mo** (storage box
adds $1 when Row J lands).

## Support + escalation

- **Log source of truth:** `journalctl -u workflow-daemon -f` on the Hetzner box.
- **Canary alarm:** `.github/workflows/uptime-canary.yml` auto-opens a GitHub issue labeled `p0-outage` on 2 consecutive reds. Host gets GitHub email notification.
- **Tunnel dashboard:** `https://dash.cloudflare.com/<acct>/one/networks/connectors` — shows tunnel + connector health.

If canary goes red + persists >10 min AND host isn't responding, the
succession runbook (`SUCCESSION.md` §6.1) applies: admin-pool member
can SSH in + restart or rollback per this runbook.
