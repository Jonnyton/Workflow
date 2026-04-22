---
title: Backup and restore runbook
date: 2026-04-21
row: J — self-host migration
---

# Workflow daemon — backup and restore runbook

State backup for the DO Droplet's `/data` volume. Row J per
`docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md`.

---

## Architecture

- **Script:** `deploy/backup.sh` — tars the `workflow-data` Docker volume and uploads to any
  rclone-compatible remote.
- **Restore:** `deploy/backup-restore.sh` — pulls a snapshot and restores it in-place.
- **Schedule:** `deploy/backup.timer` (systemd) — fires nightly at **02:00 UTC**.
- **Offsite options:** DO Spaces (`s3://`), Hetzner Storage Box (`sftp://`), AWS S3, etc. — any
  rclone remote works. `BACKUP_DEST` is the single config variable.

**Retention schedule:**

| Window | Count | Default env var |
|--------|-------|-----------------|
| Daily  | 7     | `BACKUP_RETAIN_DAILY=7` |
| Weekly | 4     | `BACKUP_RETAIN_WEEKLY=4` |
| Monthly| 6     | `BACKUP_RETAIN_MONTHLY=6` |

The newest archive within each bucket is kept. Oldest bucket that falls outside all windows is
deleted at the end of every run.

---

## Setup

### 1. Configure rclone remote

Install rclone on the Droplet and configure a named remote for your offsite target.

**DO Spaces (recommended — same provider, cheapest):**

```bash
apt-get install -y rclone

# Create a DO Spaces bucket (once) via DO console or API.
# Then configure rclone:
rclone config create spaces s3 \
  provider DigitalOcean \
  endpoint nyc3.digitaloceanspaces.com \
  access_key_id "$DO_SPACES_KEY" \
  secret_access_key "$DO_SPACES_SECRET"
```

**Hetzner Storage Box (SFTP):**

```bash
rclone config create storagebox sftp \
  host u123456.your-storagebox.de \
  user u123456 \
  pass "$(rclone obscure "$STORAGEBOX_PASS")"
```

### 2. Set `BACKUP_DEST` in `/etc/workflow/env`

```bash
# DO Spaces:
echo 'BACKUP_DEST=spaces:my-bucket-name/workflow-backups' >> /etc/workflow/env

# Hetzner Storage Box:
echo 'BACKUP_DEST=storagebox:workflow-backups' >> /etc/workflow/env
```

Any rclone remote URL is accepted: `s3://bucket/path`, `sftp://host/path`,
`spaces:bucket/path`, etc.

### 3. Install and enable the systemd units

```bash
cp /opt/workflow/deploy/backup.service /etc/systemd/system/
cp /opt/workflow/deploy/backup.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now backup.timer
systemctl status backup.timer
```

Verify the first timer run:

```bash
systemctl list-timers backup.timer
```

---

## Trigger a manual backup

```bash
# As root on the Droplet:
sudo systemctl start backup.service

# Watch progress:
journalctl -f -u workflow-backup

# Or run the script directly (useful for testing with DRY_RUN):
source /etc/workflow/env
sudo -E bash /opt/workflow/deploy/backup.sh

# Dry-run (no mutations):
DRY_RUN=1 bash /opt/workflow/deploy/backup.sh
```

---

## List available snapshots

```bash
source /etc/workflow/env
bash /opt/workflow/deploy/backup-restore.sh --list
```

Example output:

```
[restore 2026-04-21T10:00:00Z] available archives at s3://my-bucket/workflow-backups:
  workflow-data-2026-04-21T02-00-00Z.tar.gz
  workflow-data-2026-04-20T02-00-00Z.tar.gz
  workflow-data-2026-04-19T02-00-00Z.tar.gz
```

---

## Restore on the same Droplet

```bash
# Dry-run first — shows which archive would be restored:
DRY_RUN=1 sudo -E bash /opt/workflow/deploy/backup-restore.sh

# Restore latest:
sudo -E bash /opt/workflow/deploy/backup-restore.sh

# Restore a specific snapshot:
sudo -E bash /opt/workflow/deploy/backup-restore.sh --timestamp=2026-04-20T02-00-00Z
```

The script stops `workflow-daemon`, extracts the archive into the Docker volume, then restarts the
daemon. Downtime is ~30–90 seconds for a typical volume.

---

## Restore on a new Droplet (disaster recovery)

Use this when the original Droplet is gone or unrecoverable.

1. Provision a fresh Droplet and run `deploy/hetzner-bootstrap.sh` (idempotent; DigitalOcean-compatible).
   Bootstrap automatically configures:
   - Docker log-rotation (`/etc/docker/daemon.json` — 10 MB max, 3 files)
   - 2 GB swap file (`/swapfile`) + `/etc/fstab` persistence + `vm.swappiness=10`
2. Copy `/etc/workflow/env` from the vault (or re-populate from the succession runbook).
3. Pull the daemon image:
   ```bash
   docker pull ghcr.io/jonnyton/workflow-daemon:latest
   ```
4. Run the restore:
   ```bash
   source /etc/workflow/env
   sudo -E bash /opt/workflow/deploy/backup-restore.sh
   ```
5. Bring up the full stack:
   ```bash
   docker compose -f /opt/workflow/deploy/compose.yml up -d
   ```
6. Verify:
   ```bash
   python scripts/mcp_public_canary.py --url http://127.0.0.1:8001/mcp
   ```

---

## Verify backup health

Check the last backup result:

```bash
journalctl -u workflow-backup --since "24 hours ago" | grep -E "backup complete|ERROR"
```

Or tail the log file directly:

```bash
tail -20 /var/log/workflow-backup.log
```

Expected healthy output ends with `backup complete.`

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `BACKUP_DEST is not set` | Env file missing the variable | Add `BACKUP_DEST=...` to `/etc/workflow/env` |
| `volume workflow-data not found` | Docker volume not yet created | Run `docker compose up -d` first |
| `rclone upload failed` | Network/auth error | Check rclone config: `rclone lsd $BACKUP_DEST` |
| `tar failed` | Volume data corrupted | Check `docker logs workflow-daemon`; may need full restore |
| Timer never fires | Unit not enabled | `systemctl enable --now backup.timer` |

---

## Offsite backup — GitHub release assets

When `GH_TOKEN` is set in `/etc/workflow/env`, `backup.sh` also ships the
tarball to a private GitHub repo (`Jonnyton/workflow-backups`) as a release
asset via `scripts/backup_ship_gh.py`.  This is a second copy independent of
the rclone primary destination.

**Restore from a GitHub release asset:**

```bash
# List available releases (requires GH_TOKEN or gh CLI auth).
gh release list --repo Jonnyton/workflow-backups

# Download a specific release asset.
gh release download <tag> --repo Jonnyton/workflow-backups --dir /tmp

# Restore (same as rclone path — feed the tarball to backup-restore.sh).
BACKUP_FILE=/tmp/workflow-data-<tag>.tar.gz sudo -E bash /opt/workflow/deploy/backup-restore.sh
```

Or via raw API (no gh CLI):

```bash
curl -sL -H "Authorization: Bearer $GH_TOKEN" \
  "https://api.github.com/repos/Jonnyton/workflow-backups/releases/latest" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['assets'][0]['browser_download_url'])"
# Then curl -L <url> > /tmp/backup.tar.gz
```

**Retention:** 30 releases kept by default (`BACKUP_GH_RETAIN`). Oldest pruned
on each successful upload.

**Setup:** create `Jonnyton/workflow-backups` as a private repo once (or let
`backup_ship_gh.py` create it automatically on first run).  Add `GH_TOKEN` to
`/etc/workflow/env` with `repo` scope.

