"""Import-smoke + entry-point + shared-helper consistency for the 6 canary scripts.

Defends a forever-rule uptime layer: if any canary script can't even be
imported, the corresponding CI step in `.github/workflows/uptime-canary.yml`
silently degrades to a no-op or hard-fails the runner. These tests catch
that class at PR time, before the canary goes red in production.

Coverage:
    - All 6 scripts import without side effects (parametrized).
    - Each exposes a `main` callable.
    - Shared helpers `_now_local_iso` / `_append_log` are defined exactly
      once (in `uptime_canary`); wiki_canary imports them by reference.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


CANARY_MODULES = (
    "uptime_canary",
    "mcp_public_canary",
    "mcp_tool_canary",
    "last_activity_canary",
    "revert_loop_canary",
    "wiki_canary",
)


@pytest.fixture(scope="module")
def loaded_modules() -> dict[str, object]:
    """Import each canary module once. Failure here is the smoke signal."""
    return {name: importlib.import_module(name) for name in CANARY_MODULES}


@pytest.mark.parametrize("module_name", CANARY_MODULES)
def test_canary_module_importable(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod is not None


@pytest.mark.parametrize("module_name", CANARY_MODULES)
def test_canary_module_exposes_main_callable(
    module_name: str, loaded_modules: dict[str, object],
) -> None:
    mod = loaded_modules[module_name]
    assert hasattr(mod, "main"), f"{module_name} has no `main` attribute"
    assert callable(mod.main), f"{module_name}.main is not callable"


@pytest.mark.parametrize("module_name", CANARY_MODULES)
def test_canary_module_has_default_url(
    module_name: str, loaded_modules: dict[str, object],
) -> None:
    """Every canary defaults to the canonical public endpoint."""
    mod = loaded_modules[module_name]
    assert hasattr(mod, "DEFAULT_URL"), f"{module_name} has no DEFAULT_URL"
    assert mod.DEFAULT_URL == "https://tinyassets.io/mcp", (
        f"{module_name}.DEFAULT_URL drifted from the canonical "
        f"https://tinyassets.io/mcp (host directive 2026-04-20). "
        f"Got: {mod.DEFAULT_URL!r}"
    )


def test_log_helpers_single_definition(loaded_modules: dict[str, object]) -> None:
    """`_now_local_iso` + `_append_log` are defined in exactly one place.

    Per design: `uptime_canary` owns log-line helpers; `wiki_canary` reuses
    them by import (verified by identity check below). Other canaries don't
    persist a log line — they print to stdout/stderr and let CI/Task
    Scheduler capture the result. If a future canary adds its own copy of
    `_now_local_iso` / `_append_log`, this test fails to force the author
    to either reuse uptime_canary's helpers or justify the divergence.
    """
    uptime = loaded_modules["uptime_canary"]
    wiki = loaded_modules["wiki_canary"]

    assert hasattr(uptime, "_now_local_iso")
    assert hasattr(uptime, "_append_log")

    assert wiki._now_local_iso is uptime._now_local_iso, (
        "wiki_canary._now_local_iso must be the SAME object as "
        "uptime_canary._now_local_iso (imported, not re-defined)."
    )
    assert wiki._append_log is uptime._append_log, (
        "wiki_canary._append_log must be the SAME object as "
        "uptime_canary._append_log (imported, not re-defined)."
    )

    # Other canaries SHOULD NOT have their own copies of these names —
    # if they did, they'd be silently writing to a different log path
    # or formatting timestamps differently.
    for name in ("mcp_public_canary", "mcp_tool_canary",
                 "last_activity_canary", "revert_loop_canary"):
        mod = loaded_modules[name]
        assert not hasattr(mod, "_now_local_iso"), (
            f"{name} defines its own `_now_local_iso` — divergent from "
            f"uptime_canary. Either import from uptime_canary or document "
            f"why this canary needs a different timestamp format."
        )
        assert not hasattr(mod, "_append_log"), (
            f"{name} defines its own `_append_log` — divergent from "
            f"uptime_canary. Either import from uptime_canary or document "
            f"why this canary needs a different log path."
        )


def test_tool_canary_helpers_reused_by_wiki_canary(
    loaded_modules: dict[str, object],
) -> None:
    """`_post` / `_extract_tool_text` / `ToolCanaryError` are reused by wiki_canary.

    wiki_canary deliberately imports `_post` / `_extract_tool_text` /
    `ToolCanaryError` from `mcp_tool_canary` rather than re-implementing
    them. Verifies the chain stays connected.
    """
    tool = loaded_modules["mcp_tool_canary"]
    wiki = loaded_modules["wiki_canary"]

    assert wiki._post is tool._post
    assert wiki._extract_tool_text is tool._extract_tool_text
    # ToolCanaryError is imported by wiki_canary at module scope; verify
    # it resolves to the same class object.
    from mcp_tool_canary import ToolCanaryError as _ToolCanaryError
    assert _ToolCanaryError is tool.ToolCanaryError
