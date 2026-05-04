"""Tests for workflow._rename_compat (Phase 0 of Author->Daemon rename)."""

from __future__ import annotations

import importlib

import pytest

from workflow import _rename_compat


@pytest.fixture
def clear_flag(monkeypatch):
    monkeypatch.delenv("WORKFLOW_AUTHOR_RENAME_COMPAT", raising=False)
    importlib.reload(_rename_compat)
    yield
    importlib.reload(_rename_compat)


def test_default_is_on(clear_flag):
    assert _rename_compat.rename_compat_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "False", "OFF", "no", "NO"])
def test_off_values_disable(monkeypatch, value):
    monkeypatch.setenv("WORKFLOW_AUTHOR_RENAME_COMPAT", value)
    assert _rename_compat.rename_compat_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", ""])
def test_on_values_enable(monkeypatch, value):
    monkeypatch.setenv("WORKFLOW_AUTHOR_RENAME_COMPAT", value)
    assert _rename_compat.rename_compat_enabled() is True


def test_whitespace_tolerated(monkeypatch):
    monkeypatch.setenv("WORKFLOW_AUTHOR_RENAME_COMPAT", "  0  ")
    assert _rename_compat.rename_compat_enabled() is False
