from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = REPO_ROOT / "packaging" / "mcpb"
DIST_ROOT = REPO_ROOT / "packaging" / "dist"
STAGE_ROOT = DIST_ROOT / "workflow-universe-server-src"
BUNDLE_PATH = DIST_ROOT / "workflow-universe-server.mcpb"


def _copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Required source file not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _stage_bundle() -> Path:
    if STAGE_ROOT.exists():
        shutil.rmtree(STAGE_ROOT)

    STAGE_ROOT.mkdir(parents=True, exist_ok=True)

    _copy_file(TEMPLATE_ROOT / "manifest.json", STAGE_ROOT / "manifest.json")
    _copy_file(TEMPLATE_ROOT / "pyproject.toml", STAGE_ROOT / "pyproject.toml")
    _copy_file(TEMPLATE_ROOT / "server.py", STAGE_ROOT / "server.py")
    _copy_file(
        REPO_ROOT / "fantasy_author" / "universe_server.py",
        STAGE_ROOT / "fantasy_author" / "universe_server.py",
    )
    _copy_file(
        REPO_ROOT / "assets" / "icon.png",
        STAGE_ROOT / "assets" / "icon.png",
    )

    return STAGE_ROOT


def _run(command: list[str], *, cwd: Path) -> None:
    executable = (
        shutil.which(command[0])
        or shutil.which(f"{command[0]}.cmd")
        or command[0]
    )
    subprocess.run([executable, *command[1:]], cwd=str(cwd), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage and optionally validate/pack the Workflow MCPB bundle."
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the staged bundle with the official MCPB CLI.",
    )
    parser.add_argument(
        "--pack",
        action="store_true",
        help="Pack the staged bundle into packaging/dist/workflow-universe-server.mcpb.",
    )
    args = parser.parse_args()

    stage_root = _stage_bundle()
    print(f"Staged bundle source at {stage_root}")

    if args.validate or args.pack:
        _run(
            ["npx", "-y", "@anthropic-ai/mcpb", "validate", str(stage_root)],
            cwd=REPO_ROOT,
        )
        print("MCPB manifest validation passed.")

    if args.pack:
        DIST_ROOT.mkdir(parents=True, exist_ok=True)
        _run(
            [
                "npx",
                "-y",
                "@anthropic-ai/mcpb",
                "pack",
                str(stage_root),
                str(BUNDLE_PATH),
            ],
            cwd=REPO_ROOT,
        )
        print(f"Packed bundle at {BUNDLE_PATH}")


if __name__ == "__main__":
    main()
