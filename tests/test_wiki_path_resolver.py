"""Tests for workflow.storage.wiki_path — Row B-pattern cleanup.

Pre-2026-04-20 the wiki root hardcoded ``r"C:\\Users\\Jonathan\\Projects\\Wiki"``
as the fallback. This leaked the developer's username into any log/URL
that surfaced the path AND broke every non-host deploy (container, new
OSS contributor, etc.). The resolver closes the class the same way
``data_dir()`` did for universe state.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """Strip env vars the wiki + data_dir resolvers read."""
    for name in (
        "WORKFLOW_WIKI_PATH",
        "WIKI_PATH",
        "WORKFLOW_DATA_DIR",
        "UNIVERSE_SERVER_BASE",
        "WORKFLOW_DEPRECATIONS",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


# ---- precedence -----------------------------------------------------------


def test_workflow_wiki_path_takes_precedence(clean_env, tmp_path):
    from workflow.storage import wiki_path

    target = tmp_path / "canonical-wiki"
    clean_env.setenv("WORKFLOW_WIKI_PATH", str(target))
    clean_env.setenv("WIKI_PATH", "/some/legacy/wiki")

    assert wiki_path() == target.resolve()


def test_legacy_wiki_path_used_when_canonical_unset(clean_env, tmp_path):
    from workflow.storage import wiki_path

    target = tmp_path / "legacy-wiki"
    clean_env.setenv("WIKI_PATH", str(target))
    assert wiki_path() == target.resolve()


def test_legacy_wiki_path_deprecation_warning_opt_in(clean_env, tmp_path):
    from workflow.storage import wiki_path

    clean_env.setenv("WIKI_PATH", str(tmp_path))
    clean_env.setenv("WORKFLOW_DEPRECATIONS", "1")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        wiki_path()
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1
    assert "WIKI_PATH" in str(deprecations[0].message)
    assert "WORKFLOW_WIKI_PATH" in str(deprecations[0].message)


def test_legacy_wiki_path_silent_by_default(clean_env, tmp_path):
    from workflow.storage import wiki_path

    clean_env.setenv("WIKI_PATH", str(tmp_path))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        wiki_path()
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations == []


# ---- platform defaults ----------------------------------------------------


def test_default_is_absolute(clean_env):
    from workflow.storage import wiki_path

    assert wiki_path().is_absolute()


def test_default_inherits_data_dir(clean_env, tmp_path):
    """When only WORKFLOW_DATA_DIR is set, wiki_path returns <data>/wiki."""
    from workflow.storage import data_dir, wiki_path

    root = tmp_path / "data-root"
    clean_env.setenv("WORKFLOW_DATA_DIR", str(root))

    assert data_dir() == root.resolve()
    assert wiki_path() == (root / "wiki").resolve()


def test_explicit_env_is_absolute(clean_env, tmp_path):
    from workflow.storage import wiki_path

    clean_env.setenv("WORKFLOW_WIKI_PATH", "relative/wiki")
    assert wiki_path().is_absolute()


def test_expanduser_honored(clean_env):
    from workflow.storage import wiki_path

    clean_env.setenv("WORKFLOW_WIKI_PATH", "~/wiki-test")
    assert wiki_path() == (Path.home() / "wiki-test").resolve()


def test_empty_string_env_treated_as_unset(clean_env, tmp_path):
    """Empty WORKFLOW_WIKI_PATH must fall through, not return CWD."""
    from workflow.storage import wiki_path

    clean_env.setenv("WORKFLOW_WIKI_PATH", "")
    clean_env.setenv("WIKI_PATH", "")
    clean_env.setenv("WORKFLOW_DATA_DIR", str(tmp_path))

    assert wiki_path() == (tmp_path / "wiki").resolve()


def test_whitespace_only_env_treated_as_unset(clean_env, tmp_path):
    from workflow.storage import wiki_path

    clean_env.setenv("WORKFLOW_WIKI_PATH", "   ")
    clean_env.setenv("WORKFLOW_DATA_DIR", str(tmp_path))

    assert wiki_path() == (tmp_path / "wiki").resolve()


# ---- integration with universe_server ------------------------------------


def test_universe_server_wiki_root_uses_resolver(clean_env, tmp_path):
    from workflow.api.helpers import _wiki_root

    target = tmp_path / "via-univ-server"
    clean_env.setenv("WORKFLOW_WIKI_PATH", str(target))

    assert _wiki_root() == target.resolve()


def test_no_cwd_drift_when_env_unset(clean_env, tmp_path, monkeypatch):
    """The pre-cleanup class — resolver never returns a CWD-relative path."""
    from workflow.storage import wiki_path

    clean_env.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    first = wiki_path()
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    monkeypatch.chdir(subdir)
    second = wiki_path()
    assert first == second, "wiki_path() returned a CWD-relative path"
    assert first.is_absolute()


# ---- regression guard — no hardcoded Windows dev path -------------------


def test_no_hardcoded_jonathan_path_anywhere(clean_env, tmp_path):
    """The pre-cleanup default ``C:\\Users\\Jonathan\\Projects\\Wiki`` is gone.

    Resolver returns the platform-correct default (data_dir/wiki) when
    no env is set. If this regresses, the class comes back.
    """
    from workflow.storage import wiki_path

    clean_env.setenv("WORKFLOW_DATA_DIR", str(tmp_path))
    result = str(wiki_path())
    assert "C:\\Users\\Jonathan\\Projects\\Wiki" not in result
    assert "C:/Users/Jonathan/Projects/Wiki" not in result


def test_wiki_path_exported_from_workflow_storage(clean_env):
    import workflow.storage

    assert "wiki_path" in workflow.storage.__all__
    assert callable(workflow.storage.wiki_path)


# ---- cross-OS leakage rejection (2026-04-19 container incident) ----------
#
# Host sets WIKI_PATH="C:\\Users\\Jonathan\\Projects\\Wiki" in its shell, the
# value propagates to the container (docker env var pass-through, or stale
# compose file), and on Linux ``Path("C:\\Users\\...")`` is NOT absolute —
# joining against CWD yields ``/app/C:\\Users\\Jonathan\\Projects\\Wiki``.
# Per AGENTS.md #8 (fail loudly, never silently) the resolver must refuse.


def test_looks_like_windows_path_heuristic():
    from workflow.storage import _looks_like_windows_path

    assert _looks_like_windows_path("C:\\Users\\Jonathan")
    assert _looks_like_windows_path("c:/users/jonathan")
    assert _looks_like_windows_path("D:\\data")
    assert _looks_like_windows_path("z:/wiki")
    assert not _looks_like_windows_path("/data/wiki")
    assert not _looks_like_windows_path("~/wiki")
    assert not _looks_like_windows_path("wiki")
    assert not _looks_like_windows_path("")
    assert not _looks_like_windows_path("C")  # too short
    assert not _looks_like_windows_path("C:")  # no separator


def test_wiki_path_rejects_windows_path_on_posix(clean_env, monkeypatch):
    # _reject_windows_path_on_posix does `import os` and reads os.name
    # at call time, so monkeypatching the os module flips the check.
    import os as _os

    import workflow.storage as storage

    monkeypatch.setattr(_os, "name", "posix")

    clean_env.setenv("WORKFLOW_WIKI_PATH", "C:\\Users\\Jonathan\\Projects\\Wiki")
    with pytest.raises(ValueError) as exc_info:
        storage.wiki_path()
    msg = str(exc_info.value)
    assert "WORKFLOW_WIKI_PATH" in msg
    assert "C:\\Users\\Jonathan\\Projects\\Wiki" in msg
    assert "POSIX" in msg


def test_wiki_path_rejects_legacy_windows_path_on_posix(clean_env, monkeypatch):
    import os as _os

    import workflow.storage as storage

    monkeypatch.setattr(_os, "name", "posix")

    clean_env.setenv("WIKI_PATH", "C:\\Users\\Jonathan\\Projects\\Wiki")
    with pytest.raises(ValueError) as exc_info:
        storage.wiki_path()
    assert "WIKI_PATH" in str(exc_info.value)


def test_data_dir_rejects_windows_path_on_posix(clean_env, monkeypatch):
    import os as _os

    import workflow.storage as storage

    monkeypatch.setattr(_os, "name", "posix")

    clean_env.setenv("WORKFLOW_DATA_DIR", "C:\\Users\\Jonathan\\Projects\\Workflow")
    with pytest.raises(ValueError) as exc_info:
        storage.data_dir()
    assert "WORKFLOW_DATA_DIR" in str(exc_info.value)


def test_windows_path_accepted_on_windows(clean_env, monkeypatch, tmp_path):
    """On actual Windows the path resolver must accept drive-letter paths."""
    import os as _os

    import workflow.storage as storage

    monkeypatch.setattr(_os, "name", "nt")
    # Use a real tmp path — resolve() on Windows runtime will produce a
    # valid absolute path.
    clean_env.setenv("WORKFLOW_WIKI_PATH", str(tmp_path))
    result = storage.wiki_path()
    assert result.is_absolute()


def test_posix_absolute_path_not_rejected_on_posix(clean_env, monkeypatch):
    """/data/wiki must NOT trigger the Windows-path rejection on POSIX.

    We can't actually instantiate a PosixPath on Windows (the host),
    so we test the narrow contract: `_reject_windows_path_on_posix`
    does not raise for this input. The full ``wiki_path()`` path-
    construction step is exercised by the existing tests running on
    the host's real OS.
    """
    import os as _os

    from workflow.storage import _reject_windows_path_on_posix

    monkeypatch.setattr(_os, "name", "posix")
    # Should not raise.
    _reject_windows_path_on_posix("/data/wiki", "WORKFLOW_WIKI_PATH")
    _reject_windows_path_on_posix("/app/wiki", "WORKFLOW_WIKI_PATH")
    _reject_windows_path_on_posix("~/wiki", "WORKFLOW_WIKI_PATH")


def test_wiki_tool_returns_clear_error_for_windows_leakage(clean_env, monkeypatch):
    """The wiki MCP tool surfaces the coerced error, not a crash."""
    import json as _json
    import os as _os

    monkeypatch.setattr(_os, "name", "posix")
    clean_env.setenv("WORKFLOW_WIKI_PATH", "C:\\Users\\Jonathan\\Projects\\Wiki")

    # Force a fresh universe_server so it picks up the env.
    import importlib

    import workflow.universe_server as us
    importlib.reload(us)

    result_json = us.wiki(action="read")
    payload = _json.loads(result_json)
    assert "error" in payload
    # Error should name the env var so deploy fixer knows which to unset.
    assert "WORKFLOW_WIKI_PATH" in payload["error"]
    assert "POSIX" in payload["error"]
    importlib.reload(us)


# ---- source-file regression guard ----------------------------------------


def test_no_hardcoded_wiki_path_in_universe_server():
    """Hard guard — universe_server.py must not contain the pre-cleanup
    hardcoded Windows path. If someone re-introduces it, this fails.
    """
    import workflow.universe_server as us

    source = Path(us.__file__).read_text(encoding="utf-8", errors="replace")
    assert "Jonathan\\Projects\\Wiki" not in source, (
        "pre-cleanup hardcoded wiki path re-introduced in workflow/universe_server.py"
    )
    assert "Jonathan/Projects/Wiki" not in source
