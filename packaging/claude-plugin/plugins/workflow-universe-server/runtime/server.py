from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _load_universe_server_module():
    bundle_root = Path(__file__).resolve().parent
    source_path = bundle_root / "fantasy_author" / "universe_server.py"

    if not source_path.is_file():
        raise FileNotFoundError(
            f"Bundled Universe Server source not found: {source_path}"
        )

    spec = importlib.util.spec_from_file_location(
        "workflow_mcpb_universe_server",
        source_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec for {source_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = os.environ.get("UNIVERSE_SERVER_BASE", "").strip()
    if not base:
        raise RuntimeError(
            "UNIVERSE_SERVER_BASE is required. Configure the plugin's "
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

    module = _load_universe_server_module()
    module.main(transport="stdio")


if __name__ == "__main__":
    main()
