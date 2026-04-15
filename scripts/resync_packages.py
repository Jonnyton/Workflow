"""Re-sync workflow/ and domains/fantasy_author/ from fantasy_author_original/."""
import re
from pathlib import Path

ROOT = Path('.')
ORIG = ROOT / 'fantasy_author_original'
WORKFLOW = ROOT / 'workflow'
DOMAINS = ROOT / 'domains' / 'fantasy_author'
DOMAIN_DIRS = {'graphs', 'nodes', 'state'}
NODES_RENAME = 'phases'


def _rewrite_path(path: str) -> str:
    """Rewrite a single dotted path."""
    if path.startswith('fantasy_author.nodes'):
        return 'domains.fantasy_author.phases' + path[len('fantasy_author.nodes'):]
    if path.startswith('fantasy_author.graphs'):
        return 'domains.fantasy_author.graphs' + path[len('fantasy_author.graphs'):]
    if path.startswith('fantasy_author.state'):
        return 'domains.fantasy_author.state' + path[len('fantasy_author.state'):]
    if path.startswith('fantasy_author.'):
        return 'workflow.' + path[len('fantasy_author.'):]
    if path == 'fantasy_author':
        return 'workflow'
    return path


def rewrite_imports(content: str) -> str:
    """Rewrite all fantasy_author references using path-level replacement."""
    def replace(m):
        return _rewrite_path(m.group(0))
    return re.sub(r'fantasy_author(?:\.\w+)*', replace, content)


def sync_file(src: Path, dst: Path) -> bool:
    content = src.read_text()
    new_content = rewrite_imports(content)
    if dst.exists() and dst.read_text() == new_content:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(new_content)
    return True


def main():
    updated = created = 0
    for src in sorted(ORIG.rglob('*.py')):
        if '__pycache__' in str(src):
            continue
        rel = src.relative_to(ORIG)
        parts = rel.parts
        # Skip bridge files
        if rel.name == '__main__.py' and len(parts) == 1:
            continue
        if str(rel) == 'api.py':
            continue

        if len(parts) >= 2 and parts[0] in DOMAIN_DIRS:
            dst_dir = DOMAINS / (NODES_RENAME if parts[0] == 'nodes' else parts[0])
            dst = dst_dir / Path(*parts[1:])
        else:
            dst = WORKFLOW / rel

        existed = dst.exists()
        if sync_file(src, dst):
            tag = "UPDATED" if existed else "CREATED"
            print(f"  {tag}: {dst}")
            if existed:
                updated += 1
            else:
                created += 1
    print(f"\nSync: {updated} updated, {created} created")


if __name__ == '__main__':
    main()
