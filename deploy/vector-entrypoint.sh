#!/bin/sh
# vector-entrypoint.sh — conditional Better Stack sink loader.
#
# Vector supports --config-dir for loading multiple YAML files. This
# wrapper assembles /run/vector-config/ from the two source files:
#
#   vector.yaml            — always loaded (sources + transforms + stdout)
#   vector-betterstack.yaml — loaded ONLY when BETTERSTACK_SOURCE_TOKEN
#                              is non-empty
#
# With the token unset, only stdout is configured — no 401 errors, no
# "Service call failed" noise every 5 seconds.

set -eu

CONFIG_DIR=/run/vector-config
mkdir -p "${CONFIG_DIR}"

# Always: base config (sources, transforms, stdout sink).
cp /etc/vector/vector.yaml "${CONFIG_DIR}/vector.yaml"

# Optional: Better Stack sink.
if [ -n "${BETTERSTACK_SOURCE_TOKEN:-}" ]; then
    cp /etc/vector/vector-betterstack.yaml "${CONFIG_DIR}/vector-betterstack.yaml"
    echo "[vector-entrypoint] BETTERSTACK_SOURCE_TOKEN set — Better Stack sink enabled"
else
    echo "[vector-entrypoint] BETTERSTACK_SOURCE_TOKEN unset — stdout only"
fi

exec vector --config-dir "${CONFIG_DIR}" "$@"
