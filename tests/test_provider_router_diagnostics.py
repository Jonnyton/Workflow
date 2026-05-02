"""Tests for FEAT-006 — per-provider skip/failure diagnostics on
``AllProvidersExhaustedError``.

Verifies the additive observability surface: when the chain exhausts,
the exception carries a structured ``attempts`` list so operators can
see *why* each provider was skipped, plus a ``chain_state`` dict for
get_run.error_detail / get_status surfaces.

Behavior is unchanged — these tests only assert the new structured
fields exist + carry the right classifications. The existing tests in
test_providers.py / test_provider_retry.py continue to assert the
behavior side.
"""

from __future__ import annotations

import pytest

from workflow.exceptions import AllProvidersExhaustedError
from workflow.providers.diagnostics import (
    ProviderAttemptDiagnostic,
    SkipClass,
    build_chain_state,
    classify_unavailable,
)


class TestProviderAttemptDiagnostic:
    def test_to_dict_drops_none_fields(self):
        a = ProviderAttemptDiagnostic(
            provider="codex",
            status="failed",
            skip_class="auth_invalid",
            detail="401 Unauthorized",
        )
        d = a.to_dict()
        assert d == {
            "provider": "codex",
            "status": "failed",
            "skip_class": "auth_invalid",
            "detail": "401 Unauthorized",
        }
        assert "cooldown_remaining_s" not in d

    def test_to_dict_keeps_cooldown_when_set(self):
        a = ProviderAttemptDiagnostic(
            provider="gemini-free",
            status="skipped",
            skip_class="quota_or_cooldown",
            cooldown_remaining_s=42,
        )
        d = a.to_dict()
        assert d["cooldown_remaining_s"] == 42

    def test_default_detail_empty_string_kept(self):
        # detail="" is a valid value, should NOT be dropped (only None is)
        a = ProviderAttemptDiagnostic(
            provider="ollama-local",
            status="skipped",
            skip_class="not_in_registry",
        )
        d = a.to_dict()
        assert d["detail"] == ""


class TestBuildChainState:
    def test_minimal(self):
        state = build_chain_state(
            role="writer",
            chain=["codex", "ollama-local"],
            attempts=[],
        )
        assert state == {
            "role": "writer",
            "chain": ["codex", "ollama-local"],
            "attempts": [],
        }

    def test_full(self):
        attempts = [
            ProviderAttemptDiagnostic(
                provider="codex", status="failed",
                skip_class="auth_invalid", detail="bundle expired",
            ),
            ProviderAttemptDiagnostic(
                provider="ollama-local", status="skipped",
                skip_class="not_in_registry",
            ),
        ]
        state = build_chain_state(
            role="writer",
            chain=["codex", "ollama-local"],
            attempts=attempts,
            api_key_providers_enabled=False,
            pinned_writer="codex",
            allowlist=["codex", "ollama-local"],
        )
        assert state["role"] == "writer"
        assert state["api_key_providers_enabled"] is False
        assert state["pinned_writer"] == "codex"
        assert state["allowlist"] == ["codex", "ollama-local"]
        assert len(state["attempts"]) == 2
        assert state["attempts"][0]["skip_class"] == "auth_invalid"
        assert state["attempts"][1]["skip_class"] == "not_in_registry"


class TestClassifyUnavailable:
    @pytest.mark.parametrize("msg,expected", [
        ("401 Unauthorized", "auth_invalid"),
        ("403 Forbidden", "auth_invalid"),
        ("Token expired", "auth_invalid"),
        ("Auth failed: invalid_token", "auth_invalid"),
        ("no_credentials available", "auth_invalid"),
        ("Connection refused", "endpoint_unreachable"),
        ("DNS resolution failed", "endpoint_unreachable"),
        ("provider unreachable", "endpoint_unreachable"),
        ("", "endpoint_unreachable"),  # default safer guess
    ])
    def test_classification(self, msg, expected):
        assert classify_unavailable(Exception(msg)) == expected


class TestAllProvidersExhaustedError:
    def test_backward_compat_message_only(self):
        # Existing call sites still work — pre-FEAT-006 callers don't
        # pass attempts/chain_state.
        err = AllProvidersExhaustedError("All providers exhausted for role=writer")
        assert str(err) == "All providers exhausted for role=writer"
        assert err.attempts is None
        assert err.chain_state is None

    def test_with_structured_diagnostics(self):
        attempts = [
            ProviderAttemptDiagnostic(
                provider="codex", status="failed",
                skip_class="auth_invalid", detail="bundle expired",
            ),
        ]
        chain_state = build_chain_state(
            role="writer",
            chain=["codex"],
            attempts=attempts,
            api_key_providers_enabled=False,
        )
        err = AllProvidersExhaustedError(
            "All providers exhausted for role=writer.",
            attempts=attempts,
            chain_state=chain_state,
        )
        assert err.attempts == attempts
        assert err.chain_state["role"] == "writer"
        assert err.chain_state["api_key_providers_enabled"] is False
        assert err.chain_state["attempts"][0]["skip_class"] == "auth_invalid"
