"""Retention-prune helper for deploy/backup.sh.

Reads a newline-delimited list of archive filenames from stdin (rclone lsf
--format n output), applies the daily/weekly/monthly keep policy, and writes
the names to DELETE to stdout — one per line.

Usage (called by backup.sh):
    rclone lsf --format n DEST/ | python3 backup_prune.py \\
        --keep-daily 7 --keep-weekly 4 --keep-monthly 6

Exit codes:
    0   success (pruned names printed; if nothing to prune, empty output)
    1   argument error
"""

from __future__ import annotations

import argparse
import re
import sys


def _apply_retention(
    names: list[str],
    keep_daily: int,
    keep_weekly: int,
    keep_monthly: int,
) -> list[str]:
    """Return names that should be deleted (oldest first)."""
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

    to_delete = sorted(set(names) - keep)
    return to_delete


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backup retention pruner")
    p.add_argument("--keep-daily", type=int, default=7)
    p.add_argument("--keep-weekly", type=int, default=4)
    p.add_argument("--keep-monthly", type=int, default=6)
    args = p.parse_args(argv)

    names = [line.strip() for line in sys.stdin if line.strip()]
    to_delete = _apply_retention(names, args.keep_daily, args.keep_weekly, args.keep_monthly)
    for name in to_delete:
        print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
