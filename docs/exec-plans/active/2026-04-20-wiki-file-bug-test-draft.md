---
title: Task #3 pre-drafted test file — tests/test_wiki_file_bug.py
date: 2026-04-20
author: dev-2
status: staging — NOT YET APPLIED; waiting on lead's 3-gate clearance for Task #3
parent: docs/design-notes/2026-04-20-wiki-bug-reports-patches.md
---

# Pre-drafted test file for Task #3 landing

Lead authorized pre-drafting `tests/test_wiki_file_bug.py` while Task #3
waits on three gates (deploy rollout / Task #5 droplet scrub / navigator
severity-rubric reconcile). Parked here as a Markdown staging artifact so
pytest does not pick it up early. Copy the code block into
`tests/test_wiki_file_bug.py` when gates clear.

Fixture pattern mirrors `tests/test_wiki_tools.py:102-145` (the existing
`wiki_dir` fixture) plus a `"bugs"` subdirectory for the new category.

## Open question — severity rubric

Navigator is reconciling `critical/major/minor/cosmetic` (convention doc)
vs `low/medium/high/blocker` (patches doc). Tests below assume the
**patches doc** values (`low/medium/high/blocker`) since that's the
dispatch-ready substrate that lands as code. If navigator flips to
`critical/major/minor/cosmetic`, swap `_VALID_SEVERITIES` constants in
the test + the seed entry severity strings in BUG-001 / BUG-002 before
running.

## Code (paste-ready)

```python
"""Tests for Task #3 — wiki `file_bug` action + BUG-NNN allocator.

Covers `_wiki_file_bug` helper, `_next_bug_id` allocator, `_slugify_title`
filesystem-safe slug, `_render_bug_markdown` frontmatter shape, and the
end-to-end `wiki(action="file_bug", ...)` dispatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from workflow.universe_server import (
    _next_bug_id,
    _render_bug_markdown,
    _slugify_title,
    _wiki_file_bug,
    wiki,
)


@pytest.fixture
def wiki_dir(tmp_path, monkeypatch):
    """Temporary wiki tree with a `bugs` category pre-created."""
    wiki_root = tmp_path / "Wiki"
    wiki_root.mkdir()
    for sub in ["projects", "concepts", "bugs"]:
        (wiki_root / "pages" / sub).mkdir(parents=True)
        (wiki_root / "drafts" / sub).mkdir(parents=True)
    (wiki_root / "raw").mkdir()
    (wiki_root / "index.md").write_text(
        "---\ntitle: Index\ntype: index\n---\n# Wiki\n", encoding="utf-8"
    )
    (wiki_root / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    (wiki_root / "WIKI.md").write_text("# Wiki Schema\n", encoding="utf-8")
    monkeypatch.setenv("WIKI_PATH", str(wiki_root))
    return wiki_root


class TestNextBugId:
    def test_empty_dir_returns_bug_001(self, wiki_dir):
        bugs_dir = wiki_dir / "pages" / "bugs"
        assert _next_bug_id(bugs_dir) == "BUG-001"

    def test_existing_bug_007_returns_bug_008(self, wiki_dir):
        bugs_dir = wiki_dir / "pages" / "bugs"
        (bugs_dir / "BUG-007-example.md").write_text("x", encoding="utf-8")
        assert _next_bug_id(bugs_dir) == "BUG-008"

    def test_non_integer_id_ignored(self, wiki_dir):
        bugs_dir = wiki_dir / "pages" / "bugs"
        (bugs_dir / "BUG-xyz-invalid.md").write_text("x", encoding="utf-8")
        (bugs_dir / "BUG-005-real.md").write_text("x", encoding="utf-8")
        assert _next_bug_id(bugs_dir) == "BUG-006"

    def test_scans_drafts_too(self, wiki_dir):
        (wiki_dir / "pages" / "bugs" / "BUG-001-p.md").write_text(
            "x", encoding="utf-8"
        )
        (wiki_dir / "drafts" / "bugs" / "BUG-002-d.md").write_text(
            "x", encoding="utf-8"
        )
        assert _next_bug_id(wiki_dir / "pages" / "bugs") == "BUG-003"


class TestSlugifyTitle:
    def test_basic(self):
        assert _slugify_title("My Bug Report") == "my-bug-report"

    def test_special_chars(self):
        assert _slugify_title("foo/bar:baz (v2)") == "foo-bar-baz-v2"

    def test_truncation_at_60(self):
        long = "a" * 100
        assert len(_slugify_title(long, max_len=60)) == 60

    def test_empty_returns_untitled(self):
        assert _slugify_title("") == "untitled"
        assert _slugify_title("!!!") == "untitled"


class TestRenderBugMarkdown:
    def test_all_frontmatter_fields_present(self):
        md = _render_bug_markdown(
            bug_id="BUG-042",
            title="Test title",
            component="extensions.patch_branch",
            severity="high",
            repro="call X",
            observed="got Y",
            expected="wanted Z",
            workaround="use W",
            first_seen_date="2026-04-20",
        )
        assert "id: BUG-042" in md
        assert "title: Test title" in md
        assert "component: extensions.patch_branch" in md
        assert "severity: high" in md
        assert "status: open" in md
        assert "## What happened\n\ngot Y" in md
        assert "## Repro\n\ncall X" in md
        assert "## Workaround\n\nuse W" in md

    def test_empty_optionals_render_placeholders(self):
        md = _render_bug_markdown(
            bug_id="BUG-001",
            title="x",
            component="y",
            severity="low",
            repro="",
            observed="",
            expected="",
            workaround="",
            first_seen_date="2026-04-20",
        )
        assert "_not specified_" in md
        assert "_none_" in md


class TestFileBugValidation:
    def test_missing_title_rejected(self, wiki_dir):
        out = json.loads(
            _wiki_file_bug(component="x", severity="high", title="")
        )
        assert "error" in out

    def test_missing_component_rejected(self, wiki_dir):
        out = json.loads(
            _wiki_file_bug(component="", severity="high", title="t")
        )
        assert "error" in out

    def test_missing_severity_rejected(self, wiki_dir):
        out = json.loads(
            _wiki_file_bug(component="x", severity="", title="t")
        )
        assert "error" in out

    def test_invalid_severity_rejected(self, wiki_dir):
        out = json.loads(
            _wiki_file_bug(component="x", severity="wombat", title="t")
        )
        assert "error" in out
        assert "valid" in out or "severity" in out["error"].lower()


class TestFileBugWrites:
    def test_happy_path_creates_page(self, wiki_dir):
        out = json.loads(
            _wiki_file_bug(
                component="extensions.patch_branch",
                severity="high",
                title="First bug",
                repro="call X",
                observed="Y",
                expected="Z",
                workaround="W",
            )
        )
        assert out["status"] == "filed"
        assert out["bug_id"] == "BUG-001"
        path = wiki_dir / out["path"]
        assert path.exists()
        body = path.read_text(encoding="utf-8")
        assert "BUG-001" in body
        assert "First bug" in body

    def test_log_appended(self, wiki_dir):
        _wiki_file_bug(
            component="x",
            severity="low",
            title="logged",
        )
        log = (wiki_dir / "log.md").read_text(encoding="utf-8")
        assert "file_bug" in log
        assert "BUG-001" in log


class TestFileBugCollisionRetry:
    def test_collision_retries_and_advances_id(self, wiki_dir):
        # Pre-seed BUG-001 so _next_bug_id first returns BUG-002.
        (wiki_dir / "pages" / "bugs" / "BUG-001-seed.md").write_text(
            "x", encoding="utf-8"
        )
        # Simulate a race: another process writes BUG-002 between our
        # _next_bug_id() and our open('x'). The atomic create must fail
        # on attempt 1, retry, and land BUG-003.
        real_open = open
        first_call = {"fired": False}

        def fake_open(path, mode="r", *args, **kwargs):
            p = Path(path) if not isinstance(path, Path) else path
            if (
                mode == "x"
                and "BUG-002" in p.name
                and not first_call["fired"]
            ):
                first_call["fired"] = True
                # Plant the colliding file so retry's scan sees it.
                real_open(path, "w", *args, **kwargs).close()
                raise FileExistsError(path)
            return real_open(path, mode, *args, **kwargs)

        with patch(
            "workflow.universe_server.open", side_effect=fake_open, create=True
        ):
            out = json.loads(
                _wiki_file_bug(
                    component="x", severity="low", title="racy"
                )
            )
        assert out["status"] == "filed"
        assert out["bug_id"] == "BUG-003"


class TestFileBugViaWikiDispatch:
    def test_dispatch_routes_file_bug(self, wiki_dir):
        out = json.loads(
            wiki(
                action="file_bug",
                component="extensions.patch_branch",
                severity="high",
                title="Dispatched",
                repro="r",
                observed="o",
                expected="e",
            )
        )
        assert out["status"] == "filed"
        assert out["bug_id"] == "BUG-001"

    def test_bugs_in_valid_categories(self):
        """Smoke test that 'bugs' is registered via patch (a)."""
        from workflow.universe_server import _WIKI_CATEGORIES
        assert "bugs" in _WIKI_CATEGORIES
```

## Notes for when patches land

- `_wiki_file_bug`, `_next_bug_id`, `_slugify_title`, `_render_bug_markdown`
  all come from patch (e). If the final landed symbols differ, update
  imports.
- `TestFileBugCollisionRetry.test_collision_retries_and_advances_id` uses
  a brittle monkeypatch of `open` at module scope with `create=True`.
  If `_wiki_file_bug` accesses `open` via a local alias or a helper
  wrapper, target that instead. Run the test once after landing; if it
  fails, adjust the patch target before claiming done.
- `TestFileBugViaWikiDispatch.test_dispatch_routes_file_bug` exercises
  the (d3) kwargs propagation — if this fails with empty-string args,
  the kwargs dict at universe_server.py ~9364-9385 wasn't extended.
