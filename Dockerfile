# Dockerfile for the Workflow daemon (MCP server).
#
# Per docs/exec-plans/active/2026-04-20-selfhost-uptime-migration.md Row A:
# provider-agnostic container image that ships to Fly.io, Hetzner, or any
# Linux host. No Fly-specific config baked in; that lives in Row D.
#
# Build:
#     docker build -t workflow-daemon .
#
# Run (local smoke):
#     docker run -p 8001:8001 \
#       -v $(pwd)/data:/data \
#       -e WORKFLOW_DATA_DIR=/data \
#       workflow-daemon
#
# MCP initialize probe (after run):
#     curl -sS -X POST http://localhost:8001/mcp \
#       -H "Content-Type: application/json" \
#       -H "Accept: application/json, text/event-stream" \
#       -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
#            "params":{"protocolVersion":"2024-11-05","capabilities":{},
#                      "clientInfo":{"name":"probe","version":"1.0"}}}'
#
# Image is multi-stage: builder layer installs native-compilation deps,
# final layer stays slim (no build-essential).

# ---------- Stage 1: builder ----------

FROM python:3.11-slim AS builder

# Native build-deps for lancedb (rust), clingo (cmake), spacy (cython),
# and general C extensions. Removed from the final image.
# Node.js 20 LTS via nodesource — Debian's default apt nodejs is too old
# (Node 12/18) for @openai/codex which requires Node ≥ 18; nodesource 20
# is the smallest LTS that's known-compatible and widely battle-tested.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        curl \
        git \
        pkg-config \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install rust toolchain for lancedb wheels that lack pre-built linux
# binaries. Pinned to a known-good version; bump when lancedb upgrades.
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --default-toolchain stable --profile minimal

# Install codex CLI to an explicit prefix so the path is deterministic
# across distros. npm global prefix under nodesource Debian may be
# /usr/lib/node_modules (not /usr/local/lib), so we pin to /opt/codex-install
# and symlink the bin — then COPY --from=builder targets a known path.
RUN mkdir -p /opt/codex-install && \
    npm install --prefix /opt/codex-install @openai/codex && \
    ln -s /opt/codex-install/node_modules/.bin/codex /usr/local/bin/codex && \
    codex --version

WORKDIR /build

# Copy project metadata + source so editable install works.
COPY pyproject.toml ./
COPY workflow/ ./workflow/
COPY domains/ ./domains/
# fantasy_daemon is the node-execution runtime invoked by
# workflow.cloud_worker. Without it in the image, the cloud worker
# supervisor crash-loops with `No module named fantasy_daemon`.
COPY fantasy_daemon/ ./fantasy_daemon/

# Install into a venv that we'll copy to the final stage. Keeps the
# final image free of pip metadata + build tools.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -e ".[mcp,gemini,groq,grok]"

# ---------- Stage 2: final ----------

FROM python:3.11-slim

# Runtime-only deps. No build-essential here.
# libgomp1 is a common transitive native dep for numpy/scipy-backed
# packages (spacy, lancedb); include it proactively.
# Node.js 20 LTS via nodesource — same version as builder so the copied
# codex binary's native addons are ABI-compatible. No npm needed at
# runtime; the codex module tree is COPY'd from the builder.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bubblewrap \
        ca-certificates \
        curl \
        libgomp1 \
        tini \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y curl \
    && rm -rf /var/lib/apt/lists/* && \
    groupadd --system --gid 1001 workflow && \
    useradd --system --uid 1001 --gid workflow --home /app --shell /bin/bash workflow

# Copy the codex install tree from builder and recreate the symlink.
# /opt/codex-install is a deterministic path set in the builder stage.
COPY --from=builder /opt/codex-install /opt/codex-install
RUN ln -s /opt/codex-install/node_modules/.bin/codex /usr/local/bin/codex

WORKDIR /app

# Copy the populated venv + source from the builder.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/workflow /app/workflow
COPY --from=builder /build/domains /app/domains
COPY --from=builder /build/fantasy_daemon /app/fantasy_daemon
COPY --from=builder /build/pyproject.toml /app/pyproject.toml

# Static data files required at runtime.
# world_rules.lp is the ASP constraint program; asp_engine.py resolves it
# relative to the package root (parents[2]/data/). The *.db files in data/
# are runtime state and live in WORKFLOW_DATA_DIR, not here.
COPY data/world_rules.lp /app/data/world_rules.lp

# Stdlib-only MCP canary — reused across Layer-1 (local), tier-3 GHA,
# docker-build CI, cloud canary, and the compose.yml container-health
# healthcheck. Single definition of "healthy MCP" across every probe
# surface. Copied directly (not via the builder stage) because the
# script is pure stdlib — no compilation needed.
COPY scripts/mcp_public_canary.py /app/scripts/mcp_public_canary.py
COPY deploy/docker-entrypoint.sh /app/docker-entrypoint.sh

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Data directory — Row B will wire WORKFLOW_DATA_DIR through all
# on-disk state. For now, /data is the expected bind-mount target;
# operators supply it via `-v /host/path:/data` + the env var below.
ENV WORKFLOW_DATA_DIR=/data
RUN mkdir -p /data && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R workflow:workflow /data /app

USER workflow

EXPOSE 8001

# tini as PID 1 handles signal forwarding + zombie reaping.
# docker-entrypoint.sh enforces cloud-daemon subscription-only auth,
# optionally installs a subscription Codex auth bundle, then execs the CMD.
ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]

# Default command — the FastMCP streamable-http server on 0.0.0.0:8001.
# Matches `if __name__ == "__main__": main()` in workflow/universe_server.py.
CMD ["python", "-m", "workflow.universe_server"]
