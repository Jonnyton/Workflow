"""Bundle entry point — boots the Workflow Universe Server MCP.

The build script stages the live ``workflow/`` package next to this
file. ``uv run`` (configured by ``manifest.json``) then runs us with
the bundle root on ``sys.path``, so a normal ``import workflow.universe_server``
resolves to the bundled package — no shim, no importlib magic.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    base = os.environ.get("UNIVERSE_SERVER_BASE", "").strip()
    if not base:
        raise RuntimeError(
            "UNIVERSE_SERVER_BASE is required. Configure the bundle's "
            "'Universe Base Directory' before launching it."
        )

    base_path = Path(base).expanduser().resolve()
    if not base_path.exists():
        raise RuntimeError(
            f"UNIVERSE_SERVER_BASE does not exist: {base_path}"
        )
    if not base_path.is_dir():
        raise RuntimeError(
            f"UNIVERSE_SERVER_BASE must be a directory: {base_path}"
        )

    os.environ["UNIVERSE_SERVER_BASE"] = str(base_path)

    # Ensure the bundled `workflow/` package wins over any system copy.
    bundle_root = Path(__file__).resolve().parent
    if str(bundle_root) not in sys.path:
        sys.path.insert(0, str(bundle_root))

    from workflow import universe_server
    universe_server.main(transport="stdio")


if __name__ == "__main__":
    main()
