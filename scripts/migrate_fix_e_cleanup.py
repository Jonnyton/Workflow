"""One-time migration: close Fix E DB-derivative orphan rows.

Fix E originally ran against `knowledge.db::facts` only. The
`story.db` derivatives (`extracted_facts`, `character_states`,
`scene_history`, `promises`) were left behind on every universe that
ran a drift-then-synthesize cycle prior to 2026-04-19.

Mission 26 Probe B found 80+ orphan extracted_facts rows + 3
scene_history tombstones + 9 residual character_states rows in
`echoes_of_the_cosmos`. This script walks every universe under
`<base>/` (default `output/`) and drops the drift-keyed rows across
both DBs using the expanded `cleanup_drift_all` helper.

Usage:

    python scripts/migrate_fix_e_cleanup.py                 # dry-run
    python scripts/migrate_fix_e_cleanup.py --apply         # commit
    python scripts/migrate_fix_e_cleanup.py --base path/to/output

Safe to re-run: cleanup operations are idempotent (already-clean
universes produce zero deletions).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from domains.fantasy_daemon.phases.drift_cleanup import (  # noqa: E402
    _drift_pattern_sql,
    _scene_id_drift_pattern,
)


def _count_drift_rows(universe_dir: Path, universe_id: str) -> dict[str, int]:
    """Return per-table drift-row counts for this universe (read-only).

    Mirrors the exact WHERE clauses cleanup_drift_* uses so dry-run
    output matches what --apply would delete.
    """
    counts = {
        "knowledge.facts": 0,
        "story.scene_history": 0,
        "story.extracted_facts": 0,
        "story.character_states": 0,
        "story.promises": 0,
    }

    kg_path = universe_dir / "knowledge.db"
    if kg_path.exists():
        try:
            conn = sqlite3.connect(str(kg_path))
            try:
                where, params = _drift_pattern_sql(universe_id)
                row = conn.execute(
                    f"SELECT COUNT(*) FROM facts WHERE {where}", params,
                ).fetchone()
                counts["knowledge.facts"] = row[0] if row else 0
            finally:
                conn.close()
        except sqlite3.Error:
            pass

    story_path = universe_dir / "story.db"
    if story_path.exists():
        try:
            conn = sqlite3.connect(str(story_path))
            try:
                pattern = _scene_id_drift_pattern(universe_id)
                for table, column, key in [
                    ("scene_history", "scene_id", "story.scene_history"),
                    ("extracted_facts", "scene_id", "story.extracted_facts"),
                    (
                        "character_states", "last_updated_scene",
                        "story.character_states",
                    ),
                    ("promises", "created_scene", "story.promises"),
                ]:
                    exists = conn.execute(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE type='table' AND name=?",
                        (table,),
                    ).fetchone()
                    if not exists:
                        continue
                    row = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {column} GLOB ?",
                        (pattern,),
                    ).fetchone()
                    counts[key] = row[0] if row else 0
            finally:
                conn.close()
        except sqlite3.Error:
            pass

    return counts


def _find_universes(base_dir: Path) -> list[Path]:
    """Every subdir of base_dir that looks like a universe directory."""
    if not base_dir.is_dir():
        return []
    result = []
    for entry in sorted(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        # A universe has either story.db or knowledge.db; or a
        # universe.json metadata file.
        if (
            (entry / "story.db").exists()
            or (entry / "knowledge.db").exists()
            or (entry / "universe.json").exists()
        ):
            result.append(entry)
    return result


def _run_cleanup(universe_dir: Path, universe_id: str) -> dict[str, int]:
    """Import and invoke cleanup_drift_all (--apply path only)."""
    from domains.fantasy_daemon.phases.drift_cleanup import cleanup_drift_all

    kg_path = str(universe_dir / "knowledge.db")
    story_path = str(universe_dir / "story.db")
    return cleanup_drift_all(universe_id, kg_path, story_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate existing universes to Fix E DB-derivative cleanup.",
    )
    parser.add_argument(
        "--base", type=Path, default=REPO_ROOT / "output",
        help="Base directory containing universe subdirs (default: output/).",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Commit deletions (default is dry-run).",
    )
    parser.add_argument(
        "--universe", type=str, default="",
        help="Limit to a single universe by directory name.",
    )
    args = parser.parse_args(argv)

    universes = _find_universes(args.base)
    if args.universe:
        universes = [u for u in universes if u.name == args.universe]
        if not universes:
            print(
                f"ERROR: no universe named {args.universe!r} under {args.base}",
                file=sys.stderr,
            )
            return 1

    if not universes:
        print(f"No universe directories found under {args.base}")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Scanning {len(universes)} universe(s) under {args.base}")

    grand_total = 0
    reports: list[dict] = []
    for universe_dir in universes:
        universe_id = universe_dir.name
        before = _count_drift_rows(universe_dir, universe_id)
        total = sum(before.values())
        report = {
            "universe": universe_id,
            "path": str(universe_dir),
            "drift_rows_detected": before,
            "total": total,
        }

        if total == 0:
            print(f"  {universe_id}: CLEAN (no drift rows)")
            reports.append(report)
            continue

        print(f"  {universe_id}: {total} drift row(s) — {before}")
        if args.apply:
            deleted = _run_cleanup(universe_dir, universe_id)
            report["deleted"] = deleted
            print(f"    → deleted {sum(deleted.values())}: {deleted}")
            grand_total += sum(deleted.values())
        else:
            grand_total += total
        reports.append(report)

    print("")
    print(f"[{mode}] Total drift rows {'deleted' if args.apply else 'detected'}: {grand_total}")
    if not args.apply and grand_total > 0:
        print("Re-run with --apply to commit the deletions.")

    # Summary artifact for audit.
    out = args.base / "fix_e_migration_report.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"mode": mode, "reports": reports}, indent=2),
            encoding="utf-8",
        )
        print(f"Report: {out}")
    except OSError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
