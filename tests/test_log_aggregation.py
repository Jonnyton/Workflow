"""Tests for Row K log aggregation sidecar (deploy/compose.yml + deploy/vector.yaml)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE = REPO_ROOT / "deploy" / "compose.yml"
VECTOR_YAML = REPO_ROOT / "deploy" / "vector.yaml"
SHIP_LOGS = REPO_ROOT / "deploy" / "ship-logs.sh"


# ---------------------------------------------------------------------------
# compose.yml — sidecar service assertions
# ---------------------------------------------------------------------------


def _load_compose() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_logs_service_defined():
    data = _load_compose()
    assert "logs" in data["services"], "compose.yml must have a 'logs' sidecar service"


def test_logs_service_uses_vector_image():
    data = _load_compose()
    image = data["services"]["logs"]["image"]
    assert image.startswith("timberio/vector:"), f"unexpected image: {image}"


def test_logs_service_restart_policy():
    data = _load_compose()
    restart = data["services"]["logs"].get("restart")
    assert restart == "unless-stopped", f"restart policy should be unless-stopped, got: {restart}"


def test_logs_service_mounts_docker_socket():
    data = _load_compose()
    volumes = data["services"]["logs"].get("volumes", [])
    socket_mounts = [v for v in volumes if "/var/run/docker.sock" in str(v)]
    assert socket_mounts, "logs service must mount /var/run/docker.sock"


def test_logs_service_mounts_vector_config():
    data = _load_compose()
    volumes = data["services"]["logs"].get("volumes", [])
    config_mounts = [v for v in volumes if "vector.yaml" in str(v)]
    assert config_mounts, "logs service must mount vector.yaml config"


def test_logs_service_depends_on_daemon():
    data = _load_compose()
    deps = data["services"]["logs"].get("depends_on", [])
    if isinstance(deps, dict):
        dep_names = list(deps.keys())
    else:
        dep_names = list(deps)
    assert "daemon" in dep_names, "logs service must depend on daemon"


# ---------------------------------------------------------------------------
# vector.yaml — source / transform / sink assertions
# ---------------------------------------------------------------------------


def _load_vector() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(VECTOR_YAML.read_text(encoding="utf-8"))


def test_vector_docker_logs_source():
    data = _load_vector()
    sources = data.get("sources", {})
    docker_source = next(
        (v for v in sources.values() if v.get("type") == "docker_logs"), None
    )
    assert docker_source is not None, "vector.yaml must have a docker_logs source"


def test_vector_tails_workflow_daemon():
    data = _load_vector()
    sources = data.get("sources", {})
    docker_source = next(
        (v for v in sources.values() if v.get("type") == "docker_logs"), None
    )
    assert docker_source is not None
    containers = docker_source.get("include_containers", [])
    assert "workflow-daemon" in containers, "docker_logs source must include workflow-daemon"


def test_vector_tails_workflow_tunnel():
    data = _load_vector()
    sources = data.get("sources", {})
    docker_source = next(
        (v for v in sources.values() if v.get("type") == "docker_logs"), None
    )
    assert docker_source is not None
    containers = docker_source.get("include_containers", [])
    assert "workflow-tunnel" in containers, "docker_logs source must include workflow-tunnel"


def test_vector_has_stdout_sink():
    data = _load_vector()
    sinks = data.get("sinks", {})
    console_sinks = [v for v in sinks.values() if v.get("type") == "console"]
    assert console_sinks, "vector.yaml must have a console/stdout sink (always-on fallback)"


def test_vector_has_betterstack_http_sink():
    data = _load_vector()
    sinks = data.get("sinks", {})
    http_sinks = [v for v in sinks.values() if v.get("type") == "http"]
    assert http_sinks, "vector.yaml must have an HTTP sink for Better Stack"


def test_vector_betterstack_uses_token_env():
    data = _load_vector()
    sinks = data.get("sinks", {})
    http_sinks = [v for v in sinks.values() if v.get("type") == "http"]
    assert http_sinks
    sink = http_sinks[0]
    auth_header = sink.get("request", {}).get("headers", {}).get("Authorization", "")
    assert "BETTERSTACK_SOURCE_TOKEN" in auth_header, (
        "Better Stack sink must interpolate BETTERSTACK_SOURCE_TOKEN"
    )


def test_vector_yaml_parses_cleanly():
    yaml = pytest.importorskip("yaml")
    # Should not raise
    data = yaml.safe_load(VECTOR_YAML.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# ship-logs.sh — basic sanity
# ---------------------------------------------------------------------------


_BASH_AVAILABLE = sys.platform != "win32"


def test_ship_logs_script_exists():
    assert SHIP_LOGS.exists(), "deploy/ship-logs.sh must exist"


@pytest.mark.skipif(not _BASH_AVAILABLE, reason="bash not available on Windows")
def test_ship_logs_dry_run_exits_0(tmp_path):
    if not SHIP_LOGS.exists():
        pytest.skip("ship-logs.sh not yet created")
    env = {
        "DRY_RUN": "1",
        "LOG_DEST": "s3://test-bucket/logs",
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
    }
    result = subprocess.run(
        ["bash", str(SHIP_LOGS)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"DRY_RUN=1 should exit 0; got {result.returncode}\n{result.stderr}"
    )


@pytest.mark.skipif(not _BASH_AVAILABLE, reason="bash not available on Windows")
def test_ship_logs_dry_run_prints_indicator(tmp_path):
    if not SHIP_LOGS.exists():
        pytest.skip("ship-logs.sh not yet created")
    env = {
        "DRY_RUN": "1",
        "LOG_DEST": "s3://test-bucket/logs",
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
    }
    result = subprocess.run(
        ["bash", str(SHIP_LOGS)],
        env=env,
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    assert "dry" in combined.lower(), "DRY_RUN=1 should print a dry-run indicator"


@pytest.mark.skipif(not _BASH_AVAILABLE, reason="bash not available on Windows")
def test_ship_logs_missing_log_dest_exits_1(tmp_path):
    if not SHIP_LOGS.exists():
        pytest.skip("ship-logs.sh not yet created")
    env = {
        "LOG_DEST": "",
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
    }
    result = subprocess.run(
        ["bash", str(SHIP_LOGS)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "missing LOG_DEST should exit non-zero"
