"""Tests for deploy/backup.sh and deploy/backup-restore.sh.

Coverage:
  - shellcheck lint (skipped if shellcheck not installed)
  - DRY_RUN=1 exits 0 with no mutations (no tar, upload, or rclone calls)
  - Missing BACKUP_DEST exits 1 when DRY_RUN is not set
  - backup-restore.sh DRY_RUN=1 exits 0 after identifying target archive
  - backup-restore.sh missing BACKUP_DEST exits 1
  - Retention-policy logic: Python port of the awk window to verify
    daily-7 / weekly-4 / monthly-6 boundaries
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BACKUP_SH = REPO / "deploy" / "backup.sh"
RESTORE_SH = REPO / "deploy" / "backup-restore.sh"

_SHELLCHECK = shutil.which("shellcheck")
_BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(_BASH is None, reason="bash not available")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(script: Path, env: dict, args: list[str] | None = None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **env}
    cmd = [_BASH, str(script)] + (args or [])
    return subprocess.run(cmd, capture_output=True, text=True, env=full_env)


# ---------------------------------------------------------------------------
# shellcheck
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SHELLCHECK is None, reason="shellcheck not installed")
def test_backup_sh_shellcheck():
    result = subprocess.run(
        [_SHELLCHECK, "--severity=warning", str(BACKUP_SH)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"shellcheck backup.sh:\n{result.stdout}\n{result.stderr}"


@pytest.mark.skipif(_SHELLCHECK is None, reason="shellcheck not installed")
def test_restore_sh_shellcheck():
    result = subprocess.run(
        [_SHELLCHECK, "--severity=warning", str(RESTORE_SH)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"shellcheck backup-restore.sh:\n{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# backup.sh — DRY_RUN
# ---------------------------------------------------------------------------

def test_backup_dry_run_exits_0_without_backup_dest():
    """DRY_RUN=1 must exit 0 even when BACKUP_DEST is absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "DRY_RUN": "1",
            "BACKUP_DEST": "",
            "BACKUP_LOG": str(Path(tmpdir) / "backup.log"),
        }
        result = _run(BACKUP_SH, env)
    assert result.returncode == 0, f"expected exit 0, got {result.returncode}\n{result.stderr}"


def test_backup_dry_run_prints_dry_run_indicator():
    """DRY_RUN=1 output must mention 'dry'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "DRY_RUN": "1",
            "BACKUP_DEST": "s3://test-bucket/backups",
            "BACKUP_LOG": str(Path(tmpdir) / "backup.log"),
        }
        result = _run(BACKUP_SH, env)
    combined = (result.stdout + result.stderr).lower()
    assert "dry" in combined, f"Expected 'dry' in output:\n{result.stdout}\n{result.stderr}"


def test_backup_dry_run_no_mutating_commands(tmp_path):
    """DRY_RUN=1: tar and rclone must not be invoked."""
    call_log = tmp_path / "calls.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for cmd in ("tar", "rclone", "docker"):
        fake_cmd = fake_bin / cmd
        fake_cmd.write_text(
            "#!/usr/bin/env bash\n"
            f"echo \"{cmd} called: $*\" >> '{call_log}'\n"
            "exit 0\n"
        )
        fake_cmd.chmod(0o755)

    env = {
        "DRY_RUN": "1",
        "BACKUP_DEST": "s3://test-bucket/backups",
        "BACKUP_LOG": str(tmp_path / "backup.log"),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
    }
    result = _run(BACKUP_SH, env)
    assert result.returncode == 0, f"exit {result.returncode}\n{result.stderr}"
    if call_log.exists():
        calls = call_log.read_text()
        assert "tar called" not in calls, f"tar was invoked in DRY_RUN:\n{calls}"
        assert "rclone called" not in calls, f"rclone was invoked in DRY_RUN:\n{calls}"


# ---------------------------------------------------------------------------
# backup.sh — BACKUP_DEST check
# ---------------------------------------------------------------------------

def test_backup_exits_1_when_backup_dest_missing():
    """Without DRY_RUN, missing BACKUP_DEST must exit 1."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "DRY_RUN": "0",
            "BACKUP_DEST": "",
            "BACKUP_LOG": str(Path(tmpdir) / "backup.log"),
        }
        result = _run(BACKUP_SH, env)
    assert result.returncode == 1, (
        f"expected exit 1 for missing BACKUP_DEST, got {result.returncode}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# backup-restore.sh — DRY_RUN
# ---------------------------------------------------------------------------

def _fake_rclone_bin(tmp_path: Path) -> Path:
    """Return path dir containing a fake rclone that returns one listing entry."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    fake_rclone = fake_bin / "rclone"
    fake_rclone.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "lsf" ]]; then\n'
        "    echo '2026-04-20T02-00-00Z;workflow-data-2026-04-20T02-00-00Z.tar.gz'\n"
        "    exit 0\n"
        "fi\n"
        'if [[ "$1" == "ls" ]]; then exit 0; fi\n'
        'if [[ "$1" == "obscure" ]]; then echo "obscured"; exit 0; fi\n'
        "exit 0\n"
    )
    fake_rclone.chmod(0o755)
    return fake_bin


def test_restore_dry_run_exits_0(tmp_path):
    """DRY_RUN=1 on restore must exit 0 after identifying the archive."""
    fake_bin = _fake_rclone_bin(tmp_path)
    env = {
        "DRY_RUN": "1",
        "BACKUP_DEST": "s3://test-bucket/workflow-backups",
        "BACKUP_LOG": str(tmp_path / "backup.log"),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
    }
    result = _run(RESTORE_SH, env)
    assert result.returncode == 0, f"exit {result.returncode}\n{result.stdout}\n{result.stderr}"


def test_restore_dry_run_prints_dry_run_indicator(tmp_path):
    """DRY_RUN=1 restore output must mention 'dry'."""
    fake_bin = _fake_rclone_bin(tmp_path)
    env = {
        "DRY_RUN": "1",
        "BACKUP_DEST": "s3://test-bucket/workflow-backups",
        "BACKUP_LOG": str(tmp_path / "backup.log"),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
    }
    result = _run(RESTORE_SH, env)
    combined = (result.stdout + result.stderr).lower()
    assert "dry" in combined, f"Expected 'dry':\n{result.stdout}\n{result.stderr}"


def test_restore_exits_1_when_backup_dest_missing():
    """Missing BACKUP_DEST must exit 1 on restore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "BACKUP_DEST": "",
            "BACKUP_LOG": str(Path(tmpdir) / "backup.log"),
        }
        result = _run(RESTORE_SH, env)
    assert result.returncode == 1, (
        f"expected exit 1 for missing BACKUP_DEST, got {result.returncode}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Retention-policy logic (Python port of the awk window)
# ---------------------------------------------------------------------------

def _apply_retention(
    names: list[str], keep_daily: int, keep_weekly: int, keep_monthly: int
) -> set[str]:
    """Python port of backup.sh's awk retention window.

    Returns the set of archive names that SHOULD BE DELETED.
    """
    keep: set[str] = set()
    week_seen: dict[str, bool] = {}
    month_seen: dict[str, bool] = {}
    daily_count = 0
    weekly_count = 0
    monthly_count = 0

    for name in sorted(names, reverse=True):
        if not re.match(r"^workflow-data-\d.*\.tar\.gz$", name):
            continue
        daily_count += 1
        if daily_count <= keep_daily:
            keep.add(name)
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
        if not m:
            continue
        date_str = m.group(1)
        day = int(date_str[8:10])
        week_bucket = date_str[:7] + f"-W{(day + 6) // 7}"
        if week_bucket not in week_seen:
            week_seen[week_bucket] = True
            weekly_count += 1
            if weekly_count <= keep_weekly:
                keep.add(name)
                continue
        month_bucket = date_str[:7]
        if month_bucket not in month_seen:
            month_seen[month_bucket] = True
            monthly_count += 1
            if monthly_count <= keep_monthly:
                keep.add(name)
                continue

    return set(names) - keep


def _make_archives(dates: list[str]) -> list[str]:
    return [f"workflow-data-{d}T02-00-00Z.tar.gz" for d in dates]


def test_retention_keeps_last_7_daily():
    """With 10 archives and daily=7, most recent 7 must never be deleted."""
    dates = [f"2026-04-{d:02d}" for d in range(1, 11)]
    names = _make_archives(dates)
    to_delete = _apply_retention(names, keep_daily=7, keep_weekly=4, keep_monthly=6)
    recent_7 = set(_make_archives(dates[-7:]))
    assert recent_7.isdisjoint(to_delete), (
        f"Recent 7 should never be deleted: {to_delete & recent_7}"
    )


def test_retention_keeps_weekly_anchors():
    """Archives from different weeks should be kept beyond the daily window."""
    # 14 days across 2 weeks
    dates = [f"2026-04-{d:02d}" for d in range(1, 15)]
    names = _make_archives(dates)
    to_delete = _apply_retention(names, keep_daily=7, keep_weekly=2, keep_monthly=6)
    # Apr 8 is first of week 2 (days 8-14)
    week2_anchor = "workflow-data-2026-04-08T02-00-00Z.tar.gz"
    assert week2_anchor not in to_delete, f"Week anchor should be kept: {week2_anchor}"


def test_retention_all_recent_no_pruning():
    """Fewer archives than daily window means nothing is pruned."""
    dates = [f"2026-04-{d:02d}" for d in range(1, 6)]
    names = _make_archives(dates)
    to_delete = _apply_retention(names, keep_daily=7, keep_weekly=4, keep_monthly=6)
    assert to_delete == set(), f"Nothing should be pruned: {to_delete}"


def test_retention_monthly_anchor_kept():
    """One archive per month is kept when beyond weekly window.

    The retention algo keeps the NEWEST archive per monthly bucket (since
    it walks newest-first). With two months of data and keep_monthly=2,
    at least one archive from each month must survive.
    """
    march = [f"2026-03-{d:02d}" for d in range(1, 32) if d <= 31]
    april = [f"2026-04-{d:02d}" for d in range(1, 5)]
    names = _make_archives(march + april)
    to_delete = _apply_retention(names, keep_daily=7, keep_weekly=4, keep_monthly=2)
    # At least one March archive must survive (the monthly anchor is newest-first,
    # so Mar 31 is kept as the March monthly representative).
    march_kept = [n for n in names if "2026-03-" in n and n not in to_delete]
    assert march_kept, f"At least one March archive should be kept; all deleted: {to_delete}"
