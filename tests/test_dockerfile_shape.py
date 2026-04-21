"""Tests for Dockerfile shape and env wiring.

Verifies:
- codex CLI install layer is present in the Dockerfile
- nodejs runtime is included in the final stage
- OPENAI_API_KEY is referenced in workflow-env.template
- compose.yml env_file passes /etc/workflow/env to the daemon service
- The codex module copy layer is present

These are static text-parse tests — they don't require Docker to be
installed and run in < 0.1s.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE = REPO_ROOT / "deploy" / "compose.yml"
ENV_TEMPLATE = REPO_ROOT / "deploy" / "workflow-env.template"


# ---------------------------------------------------------------------------
# Dockerfile — codex CLI presence
# ---------------------------------------------------------------------------


def test_dockerfile_installs_codex_npm():
    """Builder stage must install @openai/codex via npm."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "@openai/codex" in text, (
        "Dockerfile must install @openai/codex — required by codex_provider.py"
    )


def test_dockerfile_builder_has_nodejs_for_npm():
    """Builder stage must include nodejs + npm to run npm install."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "nodesource" in text, (
        "Dockerfile must use nodesource to install Node.js 20 "
        "(Debian default nodejs is too old for @openai/codex)"
    )
    assert "setup_20.x" in text, "Dockerfile must pin Node.js 20 via setup_20.x"


def test_dockerfile_final_stage_has_nodejs_runtime():
    """Final stage must ship nodejs so the codex CLI (Node.js binary) can run."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    # The final stage starts at 'FROM python:3.11-slim' (second FROM).
    # Assert nodejs appears after the second FROM.
    froms = [i for i, line in enumerate(text.splitlines()) if line.startswith("FROM ")]
    assert len(froms) >= 2, "Expected at least 2 FROM stages"
    final_stage_text = "\n".join(text.splitlines()[froms[1]:])
    assert "nodejs" in final_stage_text, (
        "Final image stage must install nodejs runtime for codex CLI"
    )


def test_dockerfile_copies_codex_binary():
    """Final stage must COPY codex install tree from builder."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY --from=builder" in text, (
        "Dockerfile must COPY codex from builder to final stage"
    )
    # Codex is installed to /opt/codex-install in the builder; that dir is COPY'd.
    copy_lines = [
        line for line in text.splitlines()
        if line.strip().startswith("COPY --from=builder") and "codex-install" in line
    ]
    assert copy_lines, (
        "Expected a 'COPY --from=builder /opt/codex-install ...' line in final stage"
    )


def test_dockerfile_codex_version_smoke():
    """Builder stage must run 'codex --version' to verify install."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "codex --version" in text, (
        "Dockerfile must run 'codex --version' after install to catch broken installs"
    )


# ---------------------------------------------------------------------------
# workflow-env.template — OPENAI_API_KEY
# ---------------------------------------------------------------------------


def test_env_template_has_openai_api_key():
    """workflow-env.template must include an OPENAI_API_KEY placeholder."""
    text = ENV_TEMPLATE.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" in text, (
        "workflow-env.template must have OPENAI_API_KEY so operators know to fill it in"
    )


def test_env_template_openai_key_is_placeholder():
    """OPENAI_API_KEY line must be blank (placeholder, not a real key)."""
    for line in ENV_TEMPLATE.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            value = line.split("=", 1)[1].strip()
            assert value == "", (
                f"OPENAI_API_KEY must be a blank placeholder; found: {value!r}"
            )
            return
    raise AssertionError("OPENAI_API_KEY= line not found in workflow-env.template")


# ---------------------------------------------------------------------------
# compose.yml — env_file wiring
# ---------------------------------------------------------------------------


def test_compose_daemon_uses_env_file():
    """daemon service in compose.yml must load /etc/workflow/env."""
    text = COMPOSE.read_text(encoding="utf-8")
    assert "/etc/workflow/env" in text, (
        "compose.yml daemon service must reference /etc/workflow/env as env_file "
        "so OPENAI_API_KEY (and other secrets) are passed to the container"
    )


def test_compose_env_file_covers_daemon_service():
    """The env_file stanza must be in the daemon service block, not just cloudflared."""
    yaml = __import__("yaml")
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    daemon_env_files = data["services"]["daemon"].get("env_file", [])
    env_file_values = [
        ef if isinstance(ef, str) else ef.get("path", "")
        for ef in daemon_env_files
    ]
    assert any("/etc/workflow/env" in v for v in env_file_values), (
        "daemon service env_file must include /etc/workflow/env"
    )
