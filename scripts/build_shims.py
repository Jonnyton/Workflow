"""Convert fantasy_author/ package to thin re-export shims.

Each module becomes a one-liner that re-exports from workflow/ or domains/.
Preserves backward compatibility for any code still importing from fantasy_author.
"""
import os
import shutil
from pathlib import Path

ROOT = Path('.')
FA = ROOT / 'fantasy_author'
FA_BACKUP = ROOT / 'fantasy_author_original'

# Mapping: fantasy_author subpackage -> target package
DOMAIN_PACKAGES = {'graphs', 'nodes', 'state'}

# nodes -> phases rename
NODES_TARGET = 'domains.fantasy_author.phases'

def shim_content(fa_module: str) -> str:
    """Generate shim content for a given fantasy_author module path."""
    parts = fa_module.split('.')
    
    if len(parts) >= 2 and parts[1] == 'nodes':
        # fantasy_author.nodes.X -> domains.fantasy_author.phases.X
        target = NODES_TARGET
        if len(parts) > 2:
            target += '.' + '.'.join(parts[2:])
        return f'"""Shim: use {target} instead."""\nfrom {target} import *  # noqa: F401,F403\n'
    
    if len(parts) >= 2 and parts[1] in DOMAIN_PACKAGES:
        # fantasy_author.graphs.X -> domains.fantasy_author.graphs.X
        target = 'domains.fantasy_author.' + '.'.join(parts[1:])
        return f'"""Shim: use {target} instead."""\nfrom {target} import *  # noqa: F401,F403\n'
    
    # Everything else -> workflow.X
    target = 'workflow.' + '.'.join(parts[1:]) if len(parts) > 1 else 'workflow'
    return f'"""Shim: use {target} instead."""\nfrom {target} import *  # noqa: F401,F403\n'


def build_shims():
    # Back up original
    if FA_BACKUP.exists():
        shutil.rmtree(FA_BACKUP)
    shutil.copytree(FA, FA_BACKUP)
    print(f"Backed up fantasy_author/ -> fantasy_author_original/")
    
    # Walk original and create shims
    count = 0
    for py_file in sorted(FA.rglob('*.py')):
        if '__pycache__' in str(py_file):
            continue
        
        rel = py_file.relative_to(ROOT)
        # Convert path to module: fantasy_author/memory/core.py -> fantasy_author.memory.core
        module = str(rel).replace(os.sep, '.').replace('.py', '')
        if module.endswith('.__init__'):
            module = module[:-9]  # strip .__init__
        
        # Skip __main__ — we'll handle that separately
        if '__main__' in module:
            continue
        
        content = shim_content(module)
        py_file.write_text(content)
        count += 1
        print(f"  {rel} -> shim ({module})")
    
    # Special __main__.py — delegate to workflow.__main__
    main_file = FA / '__main__.py'
    main_file.write_text(
        '"""Shim: use python -m workflow instead."""\n'
        'from workflow.__main__ import main\n\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    )
    count += 1
    print(f"  fantasy_author/__main__.py -> delegate to workflow.__main__")
    
    # Update __init__.py with deprecation notice
    init_file = FA / '__init__.py'
    init_file.write_text(
        '"""Fantasy Author — backward compatibility shim.\n\n'
        'This package re-exports from workflow/ and domains/fantasy_author/.\n'
        'New code should import from workflow.* or domains.fantasy_author.* directly.\n'
        '"""\n\n'
        '__version__ = "0.1.0"\n'
    )
    print(f"  fantasy_author/__init__.py -> deprecation notice")
    
    print(f"\nConverted {count} files to shims.")
    print(f"Original code backed up in fantasy_author_original/")


if __name__ == '__main__':
    build_shims()
