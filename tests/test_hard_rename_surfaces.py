"""Hard-rename guards for active source/config surfaces.

Historical docs and tests can mention the retired name as evidence or denylist
fixtures. Active code, config, packaging, and website sources should not.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "docs",
    "node_modules",
    "out",
    "tests",
    "venv",
}

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sql",
    ".svelte",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yml",
    ".yaml",
}

RETIRED_STRINGS = {
    "https://github.com/Jonnyton/Workflow": "legacy GitHub repository URL",
    "github.com/Jonnyton/Workflow": "legacy GitHub repository path",
    "Jonnyton/Workflow": "legacy GitHub repository slug",
    "Workflow MCP Server": "legacy MCP server label",
    "Workflow on GitHub": "legacy GitHub link label",
    "public face of Workflow": "legacy two-name positioning",
    "public face of TinyAssets": "two-name transitional positioning",
    "Tiny is the public face of": "two-name transitional positioning",
    "workflow-mark": "legacy public asset/class name",
    "workflow_v0": "legacy prototype resource name",
    "workflow-v0": "legacy prototype resource name",
    "workflow_credit": "legacy prototype currency label",
    "workflow-testnet": "legacy prototype treasury label",
    "postgresql://workflow": "legacy prototype DSN",
    ".workflow-secrets": "legacy local secret path",
    '"name":"workflow"': "legacy JSON server name",
    'name = "workflow"': "legacy config server name",
    'name: "workflow"': "legacy config server name",
}


def _active_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def test_active_surfaces_have_no_high_confidence_retired_workflow_names():
    failures: list[str] = []

    for path in _active_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT)
        for needle, reason in RETIRED_STRINGS.items():
            if needle in text:
                failures.append(f"{rel}: {reason}: {needle!r}")

    assert not failures, (
        "Retired Workflow names found in active source/config surfaces:\n"
        + "\n".join(failures)
    )
