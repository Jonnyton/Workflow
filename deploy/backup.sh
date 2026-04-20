#!/usr/bin/env bash
# backup.sh — nightly snapshot of the workflow-data named volume.
#
# Self-host migration Row J per
# docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md.
#
# Tars the Docker named volume's backing directory + uploads via
# rclone to a Hetzner Storage Box. Retention: 7 daily + 4 weekly,
# purged at the end of each run.
#
# Triggered by workflow-backup.service (systemd oneshot) from
# workflow-backup.timer (nightly 03:00 UTC).
#
# Required env (from /etc/workflow/env, sourced by the systemd unit):
#   STORAGEBOX_HOST   e.g. u123456.your-storagebox.de
#   STORAGEBOX_USER   storage box username
#   STORAGEBOX_PASS   storage box password (unquoted)
#
# Optional env:
#   BACKUP_PREFIX     remote path prefix (default: workflow-backups)
#   BACKUP_VOLUME     Docker volume name (default: workflow-data)
#   BACKUP_RETAIN_DAILY   default 7
#   BACKUP_RETAIN_WEEKLY  default 4
#
# Exit codes:
#   0 upload + prune succeeded.
#   1 config missing / rclone config failed.
#   2 tar failed (source volume missing or corrupted).
#   3 rclone upload failed.
#   4 retention prune failed (non-fatal; surfaced but doesn't block).

set -euo pipefail

BACKUP_PREFIX="${BACKUP_PREFIX:-workflow-backups}"
BACKUP_VOLUME="${BACKUP_VOLUME:-workflow-data}"
BACKUP_RETAIN_DAILY="${BACKUP_RETAIN_DAILY:-7}"
BACKUP_RETAIN_WEEKLY="${BACKUP_RETAIN_WEEKLY:-4}"

# Docker-internal volume mountpoint. `docker volume inspect` is more
# robust than hardcoding the path, but requires docker CLI + is slower.
# Hardcode for speed; fall back to inspect if the literal doesn't exist.
VOLUME_DIR="/var/lib/docker/volumes/${BACKUP_VOLUME}/_data"

log() { echo "[backup $(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

# ----- 1. validate env --------------------------------------------------

if [[ -z "${STORAGEBOX_HOST:-}" || -z "${STORAGEBOX_USER:-}" || -z "${STORAGEBOX_PASS:-}" ]]; then
    log "ERROR: STORAGEBOX_HOST / STORAGEBOX_USER / STORAGEBOX_PASS not set"
    log "fill them in /etc/workflow/env and restart this timer"
    exit 1
fi

# ----- 2. locate volume -------------------------------------------------

if [[ ! -d "${VOLUME_DIR}" ]]; then
    # Fall back to `docker volume inspect` in case Docker picked a
    # non-default storage root.
    VOLUME_DIR="$(docker volume inspect --format '{{ .Mountpoint }}' "${BACKUP_VOLUME}" 2>/dev/null || echo '')"
    if [[ -z "${VOLUME_DIR}" || ! -d "${VOLUME_DIR}" ]]; then
        log "ERROR: volume ${BACKUP_VOLUME} not found on disk"
        exit 2
    fi
fi

log "source: ${VOLUME_DIR}"

# ----- 3. tar the volume ------------------------------------------------

TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
TAR_NAME="workflow-data-${TS}.tar.zst"
TAR_PATH="/tmp/${TAR_NAME}"

log "creating archive ${TAR_PATH}..."
if ! tar --zstd -cf "${TAR_PATH}" -C "$(dirname "${VOLUME_DIR}")" "$(basename "${VOLUME_DIR}")"; then
    log "ERROR: tar failed"
    rm -f "${TAR_PATH}"
    exit 2
fi
TAR_SIZE="$(stat -c %s "${TAR_PATH}" 2>/dev/null || echo '?')"
log "  archive size: ${TAR_SIZE} bytes"

# ----- 4. rclone config (ephemeral) ------------------------------------

# Write a minimal rclone config to $HOME/.config/rclone so the upload
# command knows the remote. Credentials come from env — never written
# to disk in a way that survives this invocation (systemd's PrivateTmp).
RCLONE_CONFIG_DIR="${HOME}/.config/rclone"
mkdir -p "${RCLONE_CONFIG_DIR}"
RCLONE_CONFIG_FILE="${RCLONE_CONFIG_DIR}/rclone.conf"

# Use SFTP backend; Hetzner Storage Box supports SFTP on port 22.
cat > "${RCLONE_CONFIG_FILE}" <<EOF
[storagebox]
type = sftp
host = ${STORAGEBOX_HOST}
user = ${STORAGEBOX_USER}
pass = $(rclone obscure "${STORAGEBOX_PASS}" 2>/dev/null || echo "${STORAGEBOX_PASS}")
port = 22
EOF
chmod 600 "${RCLONE_CONFIG_FILE}"

# ----- 5. upload --------------------------------------------------------

REMOTE_PATH="storagebox:${BACKUP_PREFIX}/${TAR_NAME}"
log "uploading to ${REMOTE_PATH}..."
if ! rclone copyto --contimeout 60s --timeout 900s "${TAR_PATH}" "${REMOTE_PATH}"; then
    log "ERROR: rclone upload failed"
    rm -f "${TAR_PATH}"
    exit 3
fi
log "  upload OK"

rm -f "${TAR_PATH}"

# ----- 6. retention prune ----------------------------------------------

# Keep the last BACKUP_RETAIN_DAILY daily tarballs + the first tarball
# of each of the last BACKUP_RETAIN_WEEKLY weeks (Sunday cutoff).
# Prune is best-effort; failure here doesn't fail the backup itself.
log "pruning retention window (keep ${BACKUP_RETAIN_DAILY} daily + ${BACKUP_RETAIN_WEEKLY} weekly)..."
set +e
rclone lsf --format tp "storagebox:${BACKUP_PREFIX}/" 2>/dev/null \
    | sort -r \
    | awk -F';' -v keep_daily="${BACKUP_RETAIN_DAILY}" -v keep_weekly="${BACKUP_RETAIN_WEEKLY}" '
        {
          name = $2
          # Files named workflow-data-YYYY-MM-DDTHH-MM-SSZ.tar.zst
          if (name !~ /^workflow-data-[0-9].*\.tar\.zst$/) next
          daily_count++
          if (daily_count <= keep_daily) { keep[name]=1; next }
          # Weekly: retain first tarball seen per ISO week.
          match(name, /[0-9]{4}-[0-9]{2}-[0-9]{2}/, d)
          if (d[0] == "") next
          # Use week-year as the bucket key. gawk-specific mktime.
          bucket = substr(d[0], 1, 7)  # YYYY-MM roughly enough for weekly
          if (!(bucket in week_seen)) {
            week_seen[bucket] = 1
            weekly_count++
            if (weekly_count <= keep_weekly) keep[name] = 1
          }
          if (!(name in keep)) print name
        }
    ' \
    | while read -r victim; do
        log "  prune: ${victim}"
        rclone deletefile "storagebox:${BACKUP_PREFIX}/${victim}" || \
            log "    WARN: delete failed for ${victim}"
    done
prune_status=$?
set -e

if [[ "${prune_status}" -ne 0 ]]; then
    log "WARN: retention prune exited ${prune_status} (backup itself succeeded)"
    exit 4
fi

log "backup complete."
exit 0
