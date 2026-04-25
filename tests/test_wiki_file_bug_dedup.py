"""Task #21 — file_bug dedup-at-filing: similarity check + cosign_bug verb.

Before the fix, every call to `wiki action=file_bug` minted a fresh BUG-NNN
even when an identical or near-identical bug already existed. At scale this
floods the bugs directory with duplicates.

Fix: server-side Jaccard similarity check (threshold 0.5) against existing
bugs before allocating a new id. When a similar bug exists, return
`status: "similar_found"` with the top-3 matches. The caller can then use
`wiki action=cosign_bug` to add context without creating a duplicate.
`force_new=true` overrides the check and always mints a new id.
"""

from __future__ import annotations

import json

import pytest

# ── shared fixture ────────────────────────────────────────────────────────────


@pytest.fixture
def wiki_env(tmp_path, monkeypatch):
    """Set up an isolated wiki root with WORKFLOW_WIKI_PATH."""
    wiki_root = tmp_path / "wiki"
    monkeypatch.setenv("WORKFLOW_WIKI_PATH", str(wiki_root))
    monkeypatch.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    from workflow.universe_server import _ensure_wiki_scaffold
    _ensure_wiki_scaffold(wiki_root)
    return wiki_root


def _file_bug(wiki_env, **kwargs):  # noqa: ARG001
    from workflow.universe_server import wiki
    defaults = {
        "action": "file_bug",
        "component": "test.surface",
        "severity": "minor",
        "title": "Test bug",
        "observed": "saw X",
        "expected": "expected Y",
    }
    defaults.update(kwargs)
    return json.loads(wiki(**defaults))


def _seed_bug(wiki_env, title: str, observed: str = "") -> dict:
    """Seed a bug directly (force_new so dedup doesn't block seeding)."""
    return _file_bug(wiki_env, title=title, observed=observed, force_new=True)


# ── (a) no similar → mint new id ──────────────────────────────────────────────


def test_no_similar_mints_new_id(wiki_env):
    """When no existing bugs are similar, file_bug mints a new id."""
    result = _file_bug(wiki_env, title="Completely unique bug about xyzzy tokens")
    assert result.get("status") == "filed"
    assert result.get("bug_id") is not None
    assert result["bug_id"].startswith("BUG-")


# ── (b) similar existing → similar_found, no id minted ───────────────────────


def test_similar_existing_returns_similar_found(wiki_env):
    """When an existing bug is ≥50% similar, return similar_found without minting."""
    # Seed an existing bug
    _seed_bug(wiki_env, title="Search goals returns zero results for multi-token query",
              observed="search returns empty list for query containing multiple words")

    # Now file essentially the same bug
    result = _file_bug(
        wiki_env,
        title="Search goals returns zero results for multi token query",
        observed="search returns empty list for query with multiple words",
    )
    assert result.get("status") == "similar_found", (
        f"Expected similar_found, got: {result}"
    )
    assert result.get("bug_id") is None, "No id should be minted on similar_found"
    assert "similar" in result
    assert len(result["similar"]) >= 1


def test_similar_found_includes_top_3(wiki_env):
    """similar_found returns up to top-3 matches sorted by similarity."""
    _seed_bug(wiki_env, title="Login fails with wrong password error message shown",
              observed="wrong error displayed on bad credentials")
    _seed_bug(wiki_env, title="Login fails with wrong error shown on bad password",
              observed="wrong error message shown when credentials fail")

    result = _file_bug(
        wiki_env,
        title="Login fails wrong password error message shown",
        observed="wrong error message on bad credentials",
    )
    assert result.get("status") == "similar_found"
    assert len(result["similar"]) <= 3
    # Each entry has required fields
    for entry in result["similar"]:
        assert "bug_id" in entry
        assert "title" in entry
        assert "similarity" in entry
        assert "status" in entry


def test_similar_found_highest_similarity_first(wiki_env):
    """The most similar bug ranks first in the similar list."""
    _seed_bug(wiki_env,
              title="Widget crashes on double-click with null pointer",
              observed="crashes on double-click null pointer exception")
    _seed_bug(wiki_env,
              title="Unrelated button styling issue",
              observed="button looks wrong")

    result = _file_bug(
        wiki_env,
        title="Widget crashes on double-click null pointer",
        observed="crashes on double-click null pointer",
    )
    assert result.get("status") == "similar_found"
    sims = [e["similarity"] for e in result["similar"]]
    assert sims == sorted(sims, reverse=True), "Should be sorted by similarity descending"


# ── (c) force_new=True → mint new id regardless ───────────────────────────────


def test_force_new_skips_similarity_check(wiki_env):
    """force_new=True always mints a new id even when similar exists."""
    _seed_bug(wiki_env, title="Goals search fails for multi-token queries always",
              observed="zero results returned for multi-token search queries")

    result = _file_bug(
        wiki_env,
        title="Goals search fails for multi-token queries always",
        observed="zero results for multi-token search",
        force_new=True,
    )
    assert result.get("status") == "filed", (
        f"Expected filed with force_new=True, got: {result}"
    )
    assert result.get("bug_id") is not None


# ── (d) cosign_bug roundtrip ──────────────────────────────────────────────────


def test_cosign_bug_roundtrip(wiki_env):
    """cosign_bug appends a Cosigns section, increments count, returns count."""
    from workflow.universe_server import wiki

    filed = _seed_bug(wiki_env, title="Cosign target bug unique string xyzabc",
                      observed="the xyzabc thing broke")
    bug_id = filed["bug_id"]

    result = json.loads(wiki(
        action="cosign_bug",
        bug_id=bug_id,
        reporter_context="I also saw this: xyzabc broken on my machine too",
    ))
    assert result.get("status") == "cosigned", f"Expected cosigned, got: {result}"
    assert result.get("bug_id") == bug_id
    assert result.get("cosign_count") == 1


def test_cosign_bug_increments_count(wiki_env):
    """Each subsequent cosign increments cosign_count by 1."""
    from workflow.universe_server import wiki

    filed = _seed_bug(wiki_env, title="Multi-cosign target bug zyxwvu98",
                      observed="zyxwvu98 broken")
    bug_id = filed["bug_id"]

    for i in range(1, 4):
        result = json.loads(wiki(
            action="cosign_bug",
            bug_id=bug_id,
            reporter_context=f"Reporter {i} sees the zyxwvu98 issue",
        ))
        assert result["cosign_count"] == i, (
            f"Expected cosign_count={i}, got {result['cosign_count']}"
        )


def test_cosign_bug_file_contains_entry(wiki_env):
    """The bug file on disk should contain a ## Cosigns section after cosigning."""
    from workflow.universe_server import wiki

    filed = _seed_bug(wiki_env, title="Readable cosign test bug qwerty99",
                      observed="qwerty99 broke")
    bug_id = filed["bug_id"]
    file_path = wiki_env / filed["path"]

    json.loads(wiki(
        action="cosign_bug",
        bug_id=bug_id,
        reporter_context="I also observed qwerty99 failure in production",
    ))
    content = file_path.read_text(encoding="utf-8")
    assert "## Cosigns" in content
    assert "I also observed qwerty99 failure in production" in content


# ── (e) cosign_bug on missing bug_id → structured error ──────────────────────


def test_cosign_bug_missing_bug_id_returns_error(wiki_env):
    from workflow.universe_server import wiki

    result = json.loads(wiki(
        action="cosign_bug",
        bug_id="BUG-999",
        reporter_context="Test context",
    ))
    assert "error" in result


def test_cosign_bug_missing_required_args_returns_error(wiki_env):
    from workflow.universe_server import wiki

    # Missing bug_id
    r1 = json.loads(wiki(action="cosign_bug", reporter_context="ctx"))
    assert "error" in r1

    # Missing reporter_context
    r2 = json.loads(wiki(action="cosign_bug", bug_id="BUG-001"))
    assert "error" in r2


# ── (f) regression — existing file_bug tests still work ──────────────────────


def test_file_bug_still_mints_id_on_empty_bugs_dir(wiki_env):
    """Regression: first-ever bug on a clean wiki must still file cleanly."""
    result = _file_bug(wiki_env, title="First ever unique bug for regression test abc123")
    assert result.get("status") == "filed"
    assert result["bug_id"].startswith("BUG-")


def test_file_bug_returns_path_in_pages_bugs(wiki_env):
    """Filed bug path must be under pages/bugs/."""
    result = _file_bug(wiki_env, title="Path check bug for unique abc987",
                       force_new=True)
    assert result["path"].startswith("pages/bugs/"), (
        f"Expected path under pages/bugs/, got: {result['path']!r}"
    )


def test_file_bug_validation_errors_still_work(wiki_env):
    """Validation errors (missing required field) still return error dict."""
    from workflow.universe_server import wiki

    result = json.loads(wiki(action="file_bug", title=""))
    assert "error" in result

    result = json.loads(wiki(action="file_bug", title="T", component="c", severity="invalid"))
    assert "error" in result


def test_file_bug_unrelated_query_does_not_trigger_similar_found(wiki_env):
    """A query with zero token overlap with existing bugs must file cleanly."""
    _seed_bug(wiki_env, title="Login authentication fails with wrong password error",
              observed="login error message wrong on bad credentials")

    result = _file_bug(
        wiki_env,
        title="Database connection pool exhausted under load",
        observed="connection pool timeout exception thrown",
    )
    # Completely different domain — should not trigger dedup
    assert result.get("status") == "filed", (
        f"Unrelated bug should file cleanly, got: {result}"
    )
