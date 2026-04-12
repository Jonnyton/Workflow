from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "capture_idea.py"
    spec = importlib.util.spec_from_file_location("capture_idea", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_append_entry_creates_inbox_and_appends(tmp_path) -> None:
    module = load_module()
    cfg = module.CaptureConfig(
        summary="Explore staged import flow",
        source="user-chat",
        owner="unassigned",
        next_step="triage into STATUS.md or docs/design-notes/",
        links="-",
        root=tmp_path,
    )

    path, entry = module.append_entry(cfg)

    text = path.read_text(encoding="utf-8")
    assert path == tmp_path / "ideas" / "INBOX.md"
    assert "## Inbox" in text
    assert "Explore staged import flow" in text
    assert entry.strip() in text


def test_dry_run_does_not_write(tmp_path) -> None:
    module = load_module()
    cfg = module.CaptureConfig(
        summary="Add retry budget to sync loop",
        source="user-chat",
        owner="planner",
        next_step="triage during the next session",
        links="docs/design-notes/example.md",
        root=tmp_path,
    )

    path, entry = module.append_entry(cfg, dry_run=True)

    assert path == tmp_path / "ideas" / "INBOX.md"
    assert not path.exists()
    assert "Add retry budget to sync loop" in entry
