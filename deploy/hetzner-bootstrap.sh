#!/usr/bin/env bash
# hetzner-bootstrap.sh — idempotent provisioning for a fresh Debian 12 Linux VM.
#
# Provider-neutral despite the file name (name kept for git history).
# Verified on: Hetzner Cloud CX22, DigitalOcean Basic Droplet, Linode 1 GB,
# Vultr Cloud Compute. Any Debian 12 VM with root SSH + outbound-internet
# works. Bootstrap is idempotent; provider-specific install-time dashboards
# (Hetzner Cloud Console vs DO Droplets UI vs etc.) do not change the
# script's execution.
#
# Current production target (2026-04-20): DigitalOcean Basic Droplet.
# Pivoted from Hetzner mid-cutover due to a Hetzner US individual-signup
# form bug; Hetzner remains the documented fallback per exec plan §2.
#
# Self-host migration Row D per
# docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md.
#
# Idempotent: safe to re-run. Skips steps whose end-state is already
# reached. No destructive actions; existing /opt/workflow or
# /etc/workflow content is preserved.
#
# Usage (on the target box, as root):
#   curl -fsSL https://raw.githubusercontent.com/jfarnsworth/workflow/main/deploy/hetzner-bootstrap.sh -o /tmp/bootstrap.sh
#   sudo bash /tmp/bootstrap.sh
#
# OR (local-clone):
#   sudo bash deploy/hetzner-bootstrap.sh
#
# Post-bootstrap host action:
#   1. Fill /etc/workflow/env with real secrets (CLOUDFLARE_TUNNEL_TOKEN,
#      SUPABASE_*, GITHUB_OAUTH_*).
#   2. systemctl start workflow-daemon
#   3. Verify: python3 /opt/workflow/scripts/mcp_public_canary.py
#      --url https://tinyassets.io/mcp --verbose

set -euo pipefail

# Must run as root.
if [[ "${EUID}" -ne 0 ]]; then
    echo "bootstrap: must run as root (try: sudo bash $0)" >&2
    exit 1
fi

WORKFLOW_USER="workflow"
WORKFLOW_UID=1001
WORKFLOW_HOME="/opt/workflow"
ENV_DIR="/etc/workflow"
REPO_URL="https://github.com/jfarnsworth/workflow.git"
REPO_REF="main"

log() { echo "[bootstrap] $*"; }

# ----- 1. apt baseline ----------------------------------------------------

log "apt update + base packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    ca-certificates \
    curl \
    git \
    gnupg \
    python3 \
    python3-pip \
    jq \
    rclone \
    zstd

# ----- 2. Docker CE + compose plugin --------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    log "installing Docker CE..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
    cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/debian ${codename} stable
EOF
    apt-get update -qq
    apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    log "Docker installed: $(docker --version)"
else
    log "Docker already installed: $(docker --version)"
fi

# ----- 3. workflow user ---------------------------------------------------

if ! id -u "${WORKFLOW_USER}" >/dev/null 2>&1; then
    log "creating ${WORKFLOW_USER} user (uid ${WORKFLOW_UID})..."
    useradd --system \
            --uid "${WORKFLOW_UID}" \
            --home "${WORKFLOW_HOME}" \
            --create-home \
            --shell /usr/sbin/nologin \
            --comment "Workflow daemon service account" \
            "${WORKFLOW_USER}"
else
    log "${WORKFLOW_USER} user already exists"
fi

# Add workflow user to docker group so it can issue docker compose
# commands via the systemd unit.
if ! id -nG "${WORKFLOW_USER}" | grep -qw docker; then
    log "adding ${WORKFLOW_USER} to docker group..."
    usermod -aG docker "${WORKFLOW_USER}"
fi

# ----- 4. repo checkout at /opt/workflow ----------------------------------

if [[ ! -d "${WORKFLOW_HOME}/.git" ]]; then
    log "cloning repo into ${WORKFLOW_HOME}..."
    # Wipe any pre-existing non-git content (e.g. useradd created
    # /opt/workflow as home, leaving it empty). Safe because the
    # directory only exists if we just created it.
    rm -rf "${WORKFLOW_HOME}"
    git clone --branch "${REPO_REF}" --depth 1 "${REPO_URL}" "${WORKFLOW_HOME}"
else
    log "repo already present at ${WORKFLOW_HOME}; fetching latest..."
    git -C "${WORKFLOW_HOME}" fetch --depth 1 origin "${REPO_REF}"
    git -C "${WORKFLOW_HOME}" reset --hard "origin/${REPO_REF}"
fi
chown -R "${WORKFLOW_USER}:${WORKFLOW_USER}" "${WORKFLOW_HOME}"

# Make the compose.yml reachable at the path the systemd unit expects.
if [[ ! -f "${WORKFLOW_HOME}/compose.yml" ]]; then
    ln -sf "${WORKFLOW_HOME}/deploy/compose.yml" "${WORKFLOW_HOME}/compose.yml"
fi

# ----- 5. /etc/workflow env directory -------------------------------------

mkdir -p "${ENV_DIR}"
chown "root:${WORKFLOW_USER}" "${ENV_DIR}"
chmod 750 "${ENV_DIR}"

if [[ ! -f "${ENV_DIR}/env" ]]; then
    log "creating ${ENV_DIR}/env from template (DO NOT FORGET TO FILL IN)..."
    cp "${WORKFLOW_HOME}/deploy/workflow-env.template" "${ENV_DIR}/env"
    chown "root:${WORKFLOW_USER}" "${ENV_DIR}/env"
    chmod 640 "${ENV_DIR}/env"
    log "  → edit ${ENV_DIR}/env and fill in CLOUDFLARE_TUNNEL_TOKEN + SUPABASE_* + GITHUB_OAUTH_* before starting the service"
else
    log "${ENV_DIR}/env already present; leaving contents alone"
fi

# ----- 6. systemd unit install --------------------------------------------

SYSTEMD_UNIT="/etc/systemd/system/workflow-daemon.service"
if [[ ! -f "${SYSTEMD_UNIT}" ]] \
   || ! cmp -s "${WORKFLOW_HOME}/deploy/workflow-daemon.service" "${SYSTEMD_UNIT}"; then
    log "installing workflow-daemon.service..."
    cp "${WORKFLOW_HOME}/deploy/workflow-daemon.service" "${SYSTEMD_UNIT}"
    systemctl daemon-reload
    systemctl enable workflow-daemon
    log "  daemon unit installed + enabled (NOT started — fill env first)"
else
    log "workflow-daemon.service already current"
fi

# Row L — watchdog unit + timer. Enabled immediately because it's
# idempotent even before the main daemon starts — it just records
# reds + waits to cross threshold.
WATCHDOG_UNIT="/etc/systemd/system/workflow-watchdog.service"
WATCHDOG_TIMER="/etc/systemd/system/workflow-watchdog.timer"
watchdog_changed=0
if [[ ! -f "${WATCHDOG_UNIT}" ]] \
   || ! cmp -s "${WORKFLOW_HOME}/deploy/workflow-watchdog.service" "${WATCHDOG_UNIT}"; then
    cp "${WORKFLOW_HOME}/deploy/workflow-watchdog.service" "${WATCHDOG_UNIT}"
    watchdog_changed=1
fi
if [[ ! -f "${WATCHDOG_TIMER}" ]] \
   || ! cmp -s "${WORKFLOW_HOME}/deploy/workflow-watchdog.timer" "${WATCHDOG_TIMER}"; then
    cp "${WORKFLOW_HOME}/deploy/workflow-watchdog.timer" "${WATCHDOG_TIMER}"
    watchdog_changed=1
fi
if [[ "${watchdog_changed}" -eq 1 ]]; then
    log "installed workflow-watchdog service + timer"
    systemctl daemon-reload
    systemctl enable --now workflow-watchdog.timer
else
    log "workflow-watchdog service + timer already current"
fi

# Scoped sudoers rule — workflow user gets NOPASSWD ONLY for
# `systemctl restart workflow-daemon.service`. Watchdog needs this when
# threshold is crossed. No other sudo privileges granted.
SUDOERS_FILE="/etc/sudoers.d/workflow-watchdog"
SUDOERS_RULE="${WORKFLOW_USER} ALL=(root) NOPASSWD:/usr/bin/systemctl restart workflow-daemon.service"
if [[ ! -f "${SUDOERS_FILE}" ]] || ! grep -qF "${SUDOERS_RULE}" "${SUDOERS_FILE}"; then
    log "installing scoped sudoers rule for watchdog restart..."
    echo "${SUDOERS_RULE}" > "${SUDOERS_FILE}"
    chmod 0440 "${SUDOERS_FILE}"
    if ! visudo -c -q; then
        log "ERROR: sudoers syntax check failed; removing the rule"
        rm -f "${SUDOERS_FILE}"
        exit 1
    fi
else
    log "sudoers rule already present"
fi

# Row J — backup service + timer. Enabled unconditionally — if
# STORAGEBOX_* env is blank, backup.sh exits 1 with a clear message.
# Enable-on-install gives ops a one-step "fill the creds and it
# backs up tonight" flow instead of a forgotten-enable trap.
BACKUP_UNIT="/etc/systemd/system/workflow-backup.service"
BACKUP_TIMER="/etc/systemd/system/workflow-backup.timer"
backup_changed=0
if [[ ! -f "${BACKUP_UNIT}" ]] \
   || ! cmp -s "${WORKFLOW_HOME}/deploy/workflow-backup.service" "${BACKUP_UNIT}"; then
    cp "${WORKFLOW_HOME}/deploy/workflow-backup.service" "${BACKUP_UNIT}"
    backup_changed=1
fi
if [[ ! -f "${BACKUP_TIMER}" ]] \
   || ! cmp -s "${WORKFLOW_HOME}/deploy/workflow-backup.timer" "${BACKUP_TIMER}"; then
    cp "${WORKFLOW_HOME}/deploy/workflow-backup.timer" "${BACKUP_TIMER}"
    backup_changed=1
fi
if [[ "${backup_changed}" -eq 1 ]]; then
    log "installed workflow-backup service + timer"
    systemctl daemon-reload
    systemctl enable --now workflow-backup.timer
else
    log "workflow-backup service + timer already current"
fi

# ----- 7. final checks + instructions -------------------------------------

log "bootstrap complete."
cat <<EOF

Next steps (host action required):

  1. Fill in secrets:
       sudo nano ${ENV_DIR}/env
     (See deploy/HETZNER-DEPLOY.md for which values go where.)

  2. Start the service:
       sudo systemctl start workflow-daemon

  3. Tail logs:
       sudo journalctl -u workflow-daemon -f

  4. Verify canary green:
       python3 ${WORKFLOW_HOME}/scripts/mcp_public_canary.py \\
           --url https://tinyassets.io/mcp --verbose

  If the canary comes back exit 0 with [canary] OK, the self-host
  deploy is live. Host machine can now power off + tinyassets.io/mcp
  stays up.

EOF
