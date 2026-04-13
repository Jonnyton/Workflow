"""Migrate fantasy_author imports to workflow/domains paths.

Usage: python scripts/migrate_imports.py [--dry-run] [paths...]
If no paths given, processes tests/ and scripts/.
"""
import re
import sys
from pathlib import Path

SCRIPT_NAME = 'migrate_imports.py'


def _rewrite_dotted_path(path: str) -> str:
    """Rewrite a single dotted import path string."""
    # fantasy_author.nodes.X -> domains.fantasy_author.phases.X
    if path.startswith('fantasy_author.nodes'):
        return 'domains.fantasy_author.phases' + path[len('fantasy_author.nodes'):]
    # fantasy_author.graphs.X -> domains.fantasy_author.graphs.X
    if path.startswith('fantasy_author.graphs'):
        return 'domains.fantasy_author.graphs' + path[len('fantasy_author.graphs'):]
    # fantasy_author.state.X -> domains.fantasy_author.state.X
    if path.startswith('fantasy_author.state'):
        return 'domains.fantasy_author.state' + path[len('fantasy_author.state'):]
    # fantasy_author.X -> workflow.X (everything else)
    if path.startswith('fantasy_author.'):
        return 'workflow.' + path[len('fantasy_author.'):]
    if path == 'fantasy_author':
        return 'workflow'
    return path


def migrate_line(line: str) -> str:
    """Rewrite a single line's fantasy_author imports."""
    if 'fantasy_author' not in line:
        return line

    # Handle import statements: from fantasy_author.X.Y import Z
    m = re.match(r'^(\s*from\s+)(fantasy_author\S*)(.*)', line)
    if m:
        prefix, path, rest = m.groups()
        return f"{prefix}{_rewrite_dotted_path(path)}{rest}"

    # Handle: import fantasy_author.X
    m = re.match(r'^(\s*import\s+)(fantasy_author\S*)(\s+as\s+.*|$)', line)
    if m:
        prefix, path, rest = m.groups()
        return f"{prefix}{_rewrite_dotted_path(path)}{rest}"

    # Handle string references — replace all occurrences of fantasy_author.X.Y.Z
    # in quotes or general text (patch paths, docstrings, comments)
    def _replace_match(m):
        return _rewrite_dotted_path(m.group(0))

    return re.sub(r'fantasy_author(?:\.\w+)+', _replace_match, line)


def migrate_file(path: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    content = path.read_text()
    lines = content.split('\n')
    changes = []
    new_lines = []

    for i, line in enumerate(lines):
        new_line = migrate_line(line)
        if new_line != line:
            changes.append(f"  L{i+1}: {line.strip()}")
            changes.append(f"     -> {new_line.strip()}")
        new_lines.append(new_line)

    if changes and not dry_run:
        path.write_text('\n'.join(new_lines))

    return len(changes) // 2, changes


def main():
    dry_run = '--dry-run' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--dry-run']

    if args:
        paths = [Path(a) for a in args]
    else:
        paths = [Path('tests'), Path('scripts')]

    total_files = 0
    total_changes = 0

    for p in paths:
        files = [p] if p.is_file() else sorted(p.rglob('*.py'))
        for f in files:
            if f.name == SCRIPT_NAME:
                continue
            count, changes = migrate_file(f, dry_run)
            if count > 0:
                total_files += 1
                total_changes += count
                prefix = '[DRY] ' if dry_run else ''
                print(f"\n{prefix}{f} ({count} changes)")
                for c in changes[:20]:
                    print(c)
                if len(changes) > 20:
                    print(f"  ... +{len(changes)//2 - 10} more")

    verb = "would change" if dry_run else "changed"
    print(f"\n{'='*60}")
    print(f"Total: {verb} {total_changes} imports across {total_files} files")


if __name__ == '__main__':
    main()
