---
title: Cloud daemon restart runbook
date: 2026-04-25
audience: Tier-2 host (daemon operator)
status: active
---

# Cloud daemon restart runbook

Consolidated recovery reference for the DO Droplet running the Workflow daemon.
Use this as your first stop when `https://tinyassets.io/mcp` goes red or the
daemon stops responding.

Related docs:
- Full deploy: `deploy/DEPLOY.md`
- State restore from backup: `deploy/RESTORE.md` and `docs/ops/backup-restore-runbook.md`
- P0 trace (2026-04-23 disk-full incident): `docs/audits/2026-04-23-p0-auto-recovery-trace.md`

---

## Quick-start: diagnose by canary color

Run both canary probes first. The color pair tells you exactly which layer is broken.

```bash
# From your laptop:
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --verbose
python scripts/mcp_public_canary.py --url https://mcp.tinyassets.io/mcp --verbose
```

| `tinyassets.io/mcp` | `mcp.tinyassets.io/mcp` | Go to |
|---|---|---|
| green | green | All healthy — no action needed. |
| red | green | [Cloudflare Worker broken](#cloudflare-worker-broken) |
| green | red | [Tunnel or daemon down](#tunnel-or-daemon-down) |
| red | red | [Tunnel or daemon down](#tunnel-or-daemon-down) |

---

## SSH access

```bash
ssh root@<droplet-ip>
# IP is in /etc/workflow/env as DO_DROPLET_HOST, or check DigitalOcean console.
```

---

## Tunnel or daemon down

### 1. Check status

```bash
sudo systemctl status workflow-daemon
sudo journalctl -u workflow-daemon -n 50 --no-pager
```

Look for:
- `daemon-1 | Starting Workflow Server on 0.0.0.0:8001` — daemon bound
- `cloudflared | Registered tunnel connection connIndex=0` — tunnel up

### 2. Simple restart (try this first)

```bash
sudo systemctl restart workflow-daemon
sudo systemctl status workflow-daemon
```

Wait 30–60 seconds for the container image to fully start, then re-run the canary.

### 3. If restart fails — check individual containers

```bash
docker ps -a
docker logs workflow-daemon --tail 50
docker logs workflow-tunnel --tail 50
```

Common patterns:

**Daemon not binding (port conflict or crash loop):**
```bash
docker logs workflow-daemon --tail 100 | grep -E "Error|Exception|Starting"
```

**Tunnel not connecting:**
```bash
docker logs workflow-tunnel --tail 50
# "Unauthorized" → token wrong or regenerated; see env fix below
```

### 4. Fix `/etc/workflow/env` and restart

```bash
sudo nano /etc/workflow/env
# Fix the relevant variable (see table below)
sudo systemctl restart workflow-daemon
```

Key variables to check:

| Variable | Source |
|---|---|
| `CLOUDFLARE_TUNNEL_TOKEN` | Cloudflare dashboard → Zero Trust → Networks → Tunnels → (tunnel) → Connectors |
| `WORKFLOW_IMAGE` | GHCR image tag; fall back to `ghcr.io/jonnyton/workflow-daemon:latest` if pinned tag missing |

After editing, check permissions:
```bash
ls -la /etc/workflow/env
# Must be: -rw-r----- 1 root workflow ... env
# Fix if wrong:
sudo chown root:workflow /etc/workflow/env && sudo chmod 640 /etc/workflow/env
```

---

## Cloudflare Worker broken

The tunnel is up but the apex route is broken.

1. Check Cloudflare dashboard → Workers & Pages → `tinyassets-mcp-proxy` → Triggers.
   - Route `tinyassets.io/mcp*` should be listed and enabled.
2. If the route is missing, re-add it: Workers → (worker) → Triggers → Add route.
3. Re-run the canary after ~30 seconds for propagation.

---

## Disk-full recovery (P0 pattern)

Symptom: daemon crashes or produces empty output; `df -h /` shows 95%+ used.

This is the 2026-04-23 P0 pattern. Root cause: provider stack exhaustion →
empty-prose → REVERT loop → log/checkpoint accumulation fills disk.

### Step 1 — Reclaim Docker layer cache (safe)

This reclaims Docker's build cache and unused images. It does NOT touch the
`workflow-data` named volume where live state lives.

```bash
docker system prune -af
# Expect several GB reclaimed.
df -h /
```

### Step 2 — Verify volume integrity

```bash
VOLUME_DIR="$(sudo docker volume inspect --format '{{ .Mountpoint }}' workflow-data)"
sudo ls -lh "${VOLUME_DIR}"
# Should show: .auth.db, .node_eval.db, .author_server.db, per-universe subdirs
```

### Step 3 — Restart the daemon

```bash
sudo systemctl restart workflow-daemon
sudo journalctl -u workflow-daemon -f
```

### Step 4 — Confirm canary green

```bash
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --verbose
```

### Step 5 — Address root cause

Disk-full will recur if the underlying loop (empty-prose → REVERT) isn't fixed.
After recovery, file a bug or check STATUS.md for the active P0 concern and
resume daemon only if the loop is resolved. If the revert-loop concern is still
open in STATUS.md, keep the daemon paused (write `.pause` to the data dir) until
the fix lands.

**DO NOT resize the volume as the only fix** — the revert-loop generates faster
than reclamation. Fix the loop first.

If disk pressure is chronic (>80% after prune), expand the Droplet disk:
DigitalOcean → Droplet → Resize → choose a larger disk tier, then reboot.

---

## Daemon PAUSED state

The daemon can be soft-paused without stopping the container:

```bash
# Pause:
VOLUME_DIR="$(sudo docker volume inspect --format '{{ .Mountpoint }}' workflow-data)"
sudo touch "${VOLUME_DIR}/.pause"

# Resume:
sudo rm "${VOLUME_DIR}/.pause"
```

The worker process stays alive (tunnel stays up, `/mcp` responds to init).
The daemon stops picking up new work. Use this when the daemon is looping
and you need to preserve uptime while diagnosing.

---

## Watchdog behavior

The bootstrap installs `workflow-watchdog.timer` which fires every 2 minutes:
- 3 consecutive canary reds → auto-restarts `workflow-daemon.service`
- Rate-limited to one restart per 10 minutes (prevents hot-loop on persistent failure)

Check watchdog logs:
```bash
sudo journalctl -u workflow-watchdog -f
sudo systemctl list-timers workflow-watchdog.timer
```

If the watchdog is restarting the daemon repeatedly without recovery, the root
cause is deeper than a simple hang. Disable the watchdog temporarily while you
diagnose:
```bash
sudo systemctl stop workflow-watchdog.timer
# ... investigate ...
sudo systemctl start workflow-watchdog.timer
```

---

## Full state restore (data loss / bad migration)

Use `deploy/RESTORE.md` or `docs/ops/backup-restore-runbook.md`.

Quick path (restore latest backup on existing Droplet):
```bash
sudo systemctl stop workflow-daemon
source /etc/workflow/env
sudo -E bash /opt/workflow/deploy/backup-restore.sh
sudo systemctl start workflow-daemon
python3 /opt/workflow/scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --verbose
```

---

## Escalation

If canary stays red after trying the steps above:

1. Check `docs/audits/2026-04-23-p0-auto-recovery-trace.md` for patterns.
2. Check `SUCCESSION.md §6.1` for admin-pool escalation path.
3. File a `p0-outage` GitHub issue (the uptime-canary GHA workflow does this
   automatically on 2 consecutive reds — check if it already filed one).
4. Check `.github/workflows/uptime-canary.yml` for the most recent canary run.
