#!/usr/bin/env bash
# docker-entrypoint.sh — container startup shim.
#
# 1. If OPENAI_API_KEY is set and codex auth is missing, run
#    `codex login --with-api-key` so the codex provider works
#    without manual pre-login steps on every fresh container.
# 2. exec the passed CMD (preserves tini PID-1 signal forwarding).
#
# Placed before CMD so operators can override CMD freely.

set -euo pipefail

# Codex stores auth in ~/.codex/auth.json relative to the running user.
CODEX_AUTH_FILE="${HOME:-/app}/.codex/auth.json"

if [[ -n "${OPENAI_API_KEY:-}" && ! -f "${CODEX_AUTH_FILE}" ]]; then
    echo "[entrypoint] codex auth missing — running codex login..."
    printf '%s' "${OPENAI_API_KEY}" | codex login --with-api-key 2>&1 || {
        echo "[entrypoint] WARN: codex login exited non-zero (continuing anyway)"
    }
fi

exec "$@"
