"""Tests for deploy/hetzner-bootstrap.sh provisioning sections.

Coverage:
  - shellcheck lint (skipped if not installed)
  - Docker daemon.json section present with correct log config
  - Swap section present: creates /swapfile, swapon, fstab entry
  - fstab idempotency guard: grep -qF prevents duplicate lines
  - vm.swappiness sysctl.d persistence present
  - Script is idempotent (structural checks, not runtime)
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BOOTSTRAP_SH = REPO / "deploy" / "hetzner-bootstrap.sh"

_SHELLCHECK = shutil.which("shellcheck")
_BASH = shutil.which("bash")


def _text() -> str:
    return BOOTSTRAP_SH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# shellcheck
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SHELLCHECK is None, reason="shellcheck not installed")
def test_bootstrap_shellcheck():
    result = subprocess.run(
        [_SHELLCHECK, "--severity=warning", str(BOOTSTRAP_SH)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"shellcheck hetzner-bootstrap.sh:\n{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Docker log-rotation section
# ---------------------------------------------------------------------------

def test_docker_daemon_json_path_present():
    assert "/etc/docker/daemon.json" in _text()


def test_docker_log_max_size_10m():
    assert '"max-size":"10m"' in _text() or '"max-size": "10m"' in _text()


def test_docker_log_max_file_3():
    assert '"max-file":"3"' in _text() or '"max-file": "3"' in _text()


def test_docker_log_driver_json_file():
    assert '"log-driver":"json-file"' in _text() or '"log-driver": "json-file"' in _text()


def test_docker_daemon_json_idempotent_guard():
    """Section must check existing config before writing (idempotency)."""
    text = _text()
    # Should have a guard that reads + validates existing daemon.json
    assert "DOCKER_DAEMON_JSON" in text
    # The section should only write if the file is absent OR misconfigured.
    # Check for a conditional wrapping the write.
    assert re.search(r'if \[\[.*DOCKER_DAEMON_JSON', text, re.MULTILINE), (
        "docker daemon.json write must be inside an idempotency guard"
    )


# ---------------------------------------------------------------------------
# Swap section
# ---------------------------------------------------------------------------

def test_swap_swapfile_path():
    assert 'SWAPFILE="/swapfile"' in _text()


def test_swap_size_2gb():
    assert "SWAP_SIZE_MB=2048" in _text() or "2048" in _text()


def test_swap_fallocate_present():
    assert "fallocate" in _text()


def test_swap_swapon_present():
    assert "swapon" in _text()


def test_swap_fstab_entry_present():
    text = _text()
    assert "/swapfile" in text
    assert "/etc/fstab" in text


def test_swap_fstab_idempotency_guard():
    """fstab append must be guarded by grep -qF to prevent duplicate lines."""
    text = _text()
    # The guard must use grep with -qF (fixed-string quiet match) on /etc/fstab
    assert re.search(r'grep.*-.*q.*F.*fstab|grep.*fstab.*-.*q.*F', text), (
        "fstab append must be guarded by 'grep -qF ... /etc/fstab' to prevent duplicates"
    )


def test_swap_chmod_600():
    """swapfile must be chmod 600 (world-readable swap is a security risk)."""
    assert "chmod 600" in _text()


# ---------------------------------------------------------------------------
# vm.swappiness persistence
# ---------------------------------------------------------------------------

def test_swappiness_sysctl_d_file():
    assert "sysctl.d" in _text()


def test_swappiness_value_10():
    assert "vm.swappiness=10" in _text()


def test_swappiness_idempotent_guard():
    text = _text()
    assert re.search(r'if \[\[.*SYSCTL_SWAP', text, re.MULTILINE), (
        "vm.swappiness write must be inside an idempotency guard"
    )


# ── Task #61 — mkdir -p /opt/workflow/deploy pre-git-clone ───────────


def test_deploy_dir_mkdir_present():
    text = _text()
    assert "mkdir -p" in text and "/deploy" in text, (
        "hetzner-bootstrap.sh must mkdir -p the deploy dir before git-clone"
    )


def test_deploy_dir_mkdir_before_git_clone():
    text = _text()
    mkdir_pos = text.find("mkdir -p")
    # Find the position of the actual git clone command.
    clone_pos = text.find("git clone")
    assert mkdir_pos != -1 and clone_pos != -1, "both mkdir and git clone must be present"
    assert mkdir_pos < clone_pos, (
        "mkdir -p deploy dir must appear before the git clone step"
    )


def test_deploy_dir_mkdir_uses_workflow_home_var():
    text = _text()
    # Should use the ${WORKFLOW_HOME} variable, not a hardcoded path.
    assert re.search(r'mkdir -p.*WORKFLOW_HOME.*deploy', text), (
        "deploy dir mkdir should use ${WORKFLOW_HOME}/deploy, not a hardcoded path"
    )
