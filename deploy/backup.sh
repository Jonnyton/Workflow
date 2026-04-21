#!/usr/bin/env bash
# backup.sh — nightly snapshot of the workflow-data named volume.
#
# Self-host migration Row J per
# docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md.
#
# Tars the Docker named volume's backing directory + uploads to any
# rclone-compatible remote. Retention: 7 daily + 4 weekly + 6 monthly,
# pruned at the end of each run.
#
# Triggered by backup.service (systemd oneshot) from
# backup.timer (nightly 02:00 UTC).
#
# Required env (from /etc/workflow/env, sourced by the systemd unit):
#   BACKUP_DEST   rclone destination URL, e.g.:
#                   s3://my-do-spaces-bucket/workflow-backups
#                   sftp://u123456.your-storagebox.de/workflow-backups
#                 Any rclone remote URL works; rclone must already be
#                 configured for the scheme (see docs/ops/backup-restore-runbook.md).
#
# Optional env:
#   BACKUP_VOLUME          Docker volume name (default: workflow-data)
#   BACKUP_RETAIN_DAILY    keep last N daily archives (default: 7)
#   BACKUP_RETAIN_WEEKLY   keep first archive per week, last N weeks (default: 4)
#   BACKUP_RETAIN_MONTHLY  keep first archive per month, last N months (default: 6)
#   DRY_RUN                set to "1" — print plan, no tar/upload/prune
#   BACKUP_LOG             append log to this file (default: /var/log/workflow-backup.log)
#
# Exit codes:
#   0  upload + prune succeeded (or DRY_RUN=1 — no mutations).
#   1  BACKUP_DEST not set.
#   2  tar failed (source volume missing or unreadable).
#   3  rclone upload failed.
#   4  retention prune failed (non-fatal; upload itself succeeded).

set -euo pipefail

BACKUP_VOLUME="${BACKUP_VOLUME:-workflow-data}"
BACKUP_RETAIN_DAILY="${BACKUP_RETAIN_DAILY:-7}"
BACKUP_RETAIN_WEEKLY="${BACKUP_RETAIN_WEEKLY:-4}"
BACKUP_RETAIN_MONTHLY="${BACKUP_RETAIN_MONTHLY:-6}"
DRY_RUN="${DRY_RUN:-0}"
BACKUP_LOG="${BACKUP_LOG:-/var/log/workflow-backup.log}"

# Docker-internal volume mountpoint. Fall back to `docker volume inspect`
# when Docker uses a non-default storage root.
VOLUME_DIR="/var/lib/docker/volumes/${BACKUP_VOLUME}/_data"

log() {
    local msg="[backup $(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
    echo "${msg}"
    echo "${msg}" >> "${BACKUP_LOG}" 2>/dev/null || true
}

# ----- 1. validate env --------------------------------------------------

if [[ "${DRY_RUN}" != "1" ]]; then
    if [[ -z "${BACKUP_DEST:-}" ]]; then
        log "ERROR: BACKUP_DEST is not set"
        log "Set it in /etc/workflow/env, e.g.: BACKUP_DEST=s3://my-bucket/workflow-backups"
        exit 1
    fi
fi

if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY_RUN=1 — skipping volume locate, tar, upload, and prune. No mutations."
    log "  BACKUP_DEST=${BACKUP_DEST:-<unset>}"
    log "  BACKUP_VOLUME=${BACKUP_VOLUME}"
    log "  retention: daily=${BACKUP_RETAIN_DAILY} weekly=${BACKUP_RETAIN_WEEKLY} monthly=${BACKUP_RETAIN_MONTHLY}"
    exit 0
fi

# ----- 2. locate volume -------------------------------------------------

if [[ ! -d "${VOLUME_DIR}" ]]; then
    VOLUME_DIR="$(docker volume inspect --format '{{ .Mountpoint }}' "${BACKUP_VOLUME}" 2>/dev/null || echo '')"
    if [[ -z "${VOLUME_DIR}" || ! -d "${VOLUME_DIR}" ]]; then
        log "ERROR: volume ${BACKUP_VOLUME} not found on disk"
        exit 2
    fi
fi

log "source: ${VOLUME_DIR}"
log "dest:   ${BACKUP_DEST}"

# ----- 3. tar the volume ------------------------------------------------

TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
TAR_NAME="workflow-data-${TS}.tar.gz"
TAR_PATH="/tmp/${TAR_NAME}"

log "creating archive ${TAR_PATH}..."
if ! tar -czf "${TAR_PATH}" -C "$(dirname "${VOLUME_DIR}")" "$(basename "${VOLUME_DIR}")"; then
    log "ERROR: tar failed"
    rm -f "${TAR_PATH}"
    exit 2
fi
TAR_SIZE="$(stat -c %s "${TAR_PATH}" 2>/dev/null || echo '?')"
log "  archive size: ${TAR_SIZE} bytes"

# ----- 4. upload --------------------------------------------------------

log "uploading to ${BACKUP_DEST}/${TAR_NAME}..."
if ! rclone copyto --contimeout 60s --timeout 900s \
        "${TAR_PATH}" "${BACKUP_DEST}/${TAR_NAME}"; then
    log "ERROR: rclone upload failed"
    rm -f "${TAR_PATH}"
    exit 3
fi
log "  upload OK"
rm -f "${TAR_PATH}"

# ----- 5. retention prune ----------------------------------------------

# Keep:
#   - last BACKUP_RETAIN_DAILY daily archives (most recent N)
#   - first archive of each week for last BACKUP_RETAIN_WEEKLY weeks
#   - first archive of each month for last BACKUP_RETAIN_MONTHLY months
# Prune is best-effort; failure is non-fatal.
#
# Python replaces awk here: mawk (Debian default) lacks the 3-arg match()
# and gensub() extensions used by GNU awk. Python 3 is guaranteed present
# on the droplet (disk_watch.py depends on it).
log "pruning retention (daily=${BACKUP_RETAIN_DAILY} weekly=${BACKUP_RETAIN_WEEKLY} monthly=${BACKUP_RETAIN_MONTHLY})..."
PRUNE_SCRIPT="$(dirname "$(realpath "$0")")/../scripts/backup_prune.py"
set +e
set +o pipefail
# rclone lsf default output is filename-per-line — no --format flag needed
# (prior --format n was invalid; 'n' isn't a valid format char and made
# rclone exit 1, which pipefail propagated → systemd marked service failed).
rclone lsf "${BACKUP_DEST}/" 2>/dev/null \
    | python3 "${PRUNE_SCRIPT}" \
        --keep-daily "${BACKUP_RETAIN_DAILY}" \
        --keep-weekly "${BACKUP_RETAIN_WEEKLY}" \
        --keep-monthly "${BACKUP_RETAIN_MONTHLY}" \
    | while read -r victim; do
        log "  prune: ${victim}"
        rclone deletefile "${BACKUP_DEST}/${victim}" || \
            log "    WARN: delete failed for ${victim}"
    done
prune_status=$?
set -eo pipefail

if [[ "${prune_status}" -ne 0 ]]; then
    log "WARN: retention prune exited ${prune_status} (backup itself succeeded)"
    exit 4
fi

log "backup complete."
exit 0
