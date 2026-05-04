#!/usr/bin/env bash
# docker-entrypoint.sh — container startup shim.
#
# 1. Detect silently-empty env_file — emit canonical ENV-UNREADABLE
#    marker to stderr → journald so p0-outage-triage can grep + repair
#    without an SSH shell. Navigator 2026-04-22 §b layer-3.
# 2. If OPENAI_API_KEY is set and codex auth is missing, run
#    `codex login --with-api-key` so the codex provider works
#    without manual pre-login steps on every fresh container.
# 3. exec the passed CMD (preserves tini PID-1 signal forwarding).
#
# Placed before CMD so operators can override CMD freely.

set -euo pipefail

# ---------------------------------------------------------------------
# ENV-UNREADABLE canary
# ---------------------------------------------------------------------
# The systemd unit's ExecStartPre catches the dominant failure shape
# (/etc/workflow/env not readable by user=workflow on the host). This
# entrypoint-level check catches an adjacent subclass: compose read the
# env_file, but the file was empty or stripped, so the container boots
# with no real env — silently broken.
#
# Heuristic: at least one of the required secrets must be non-empty. An
# all-empty env indicates compose silently passed an empty file. The
# ENV-UNREADABLE marker keeps the grep class the same regardless of
# which layer detected the problem.
_env_sentinels=(
    CLOUDFLARE_TUNNEL_TOKEN
    SUPABASE_DB_URL
    WORKFLOW_IMAGE
)
_any_set=0
for _name in "${_env_sentinels[@]}"; do
    if [[ -n "${!_name:-}" ]]; then
        _any_set=1
        break
    fi
done
if [[ "${_any_set}" -eq 0 ]]; then
    # All sentinel env vars empty. compose env_file silently empty/unreadable.
    echo "ENV-UNREADABLE: entrypoint saw no populated secrets; compose env_file likely empty or unreadable" >&2
    echo "ENV-UNREADABLE: expected at least one of ${_env_sentinels[*]} to be set" >&2
    exit 1
fi

# Codex stores auth in ~/.codex/auth.json relative to the running user.
CODEX_AUTH_FILE="${HOME:-/app}/.codex/auth.json"

if [[ -n "${OPENAI_API_KEY:-}" && ! -f "${CODEX_AUTH_FILE}" ]]; then
    echo "[entrypoint] codex auth missing — running codex login..."
    printf '%s' "${OPENAI_API_KEY}" | codex login --with-api-key 2>&1 || {
        echo "[entrypoint] WARN: codex login exited non-zero (continuing anyway)"
    }
fi

exec "$@"
