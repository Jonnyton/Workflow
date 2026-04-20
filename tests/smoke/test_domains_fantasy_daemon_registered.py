"""Smoke: fantasy_daemon domain registers cleanly.

fantasy_daemon is the benchmark domain. If it fails to import, domain
registration is broken and the MCP server won't have any domain to bind
against — tier-1 chatbot users see "no domains available."
"""

from __future__ import annotations


def test_fantasy_daemon_package_imports():
    import domains.fantasy_daemon  # noqa: F401


def test_fantasy_daemon_has_graphs():
    import importlib

    # graphs/ is the canonical path that holds chapter + worldbuild + etc.
    # The package should expose *something* under graphs — even just a
    # submodule — for downstream wiring to work.
    try:
        graphs = importlib.import_module("domains.fantasy_daemon.graphs")
    except ImportError as exc:
        raise AssertionError(f"domains.fantasy_daemon.graphs missing: {exc}") from exc
    assert graphs is not None
