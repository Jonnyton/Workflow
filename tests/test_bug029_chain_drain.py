"""Tests for BUG-029 Part A — chain-drain detection + observability.

Covers:
- QuotaTracker.all_api_providers_in_cooldown(): True when all API providers
  cooled, False when at least one API provider is available.
- QuotaTracker.cooldown_remaining_dict(): returns per-provider remaining seconds.
- get_status exposes per_provider_cooldown_remaining as a dict.
- CHAIN_DRAINED warning is emitted when chain drains to local-only.
"""

from __future__ import annotations

import json
import logging

import pytest


class TestAllApiProvidersInCooldown:
    def _tracker(self):
        from workflow.providers.quota import QuotaTracker
        return QuotaTracker()

    def test_returns_false_when_no_providers_cooled(self):
        qt = self._tracker()
        chain = ["claude-code", "codex", "ollama-local"]
        assert qt.all_api_providers_in_cooldown(chain) is False

    def test_returns_true_when_all_api_providers_cooled(self):
        qt = self._tracker()
        qt.cooldown("claude-code", 120)
        qt.cooldown("codex", 120)
        chain = ["claude-code", "codex", "ollama-local"]
        assert qt.all_api_providers_in_cooldown(chain) is True

    def test_returns_false_when_one_api_provider_available(self):
        qt = self._tracker()
        qt.cooldown("claude-code", 120)
        chain = ["claude-code", "codex", "ollama-local"]
        assert qt.all_api_providers_in_cooldown(chain) is False

    def test_returns_false_when_chain_is_only_local(self):
        qt = self._tracker()
        chain = ["ollama-local"]
        assert qt.all_api_providers_in_cooldown(chain) is False

    def test_custom_local_providers_set(self):
        qt = self._tracker()
        qt.cooldown("claude-code", 120)
        qt.cooldown("codex", 120)
        chain = ["claude-code", "codex", "my-local"]
        # When my-local is declared local, all API providers (claude-code, codex) are cooled.
        assert qt.all_api_providers_in_cooldown(chain, local_providers={"my-local"}) is True

    def test_returns_false_when_chain_is_empty(self):
        qt = self._tracker()
        assert qt.all_api_providers_in_cooldown([]) is False


class TestCooldownRemainingDict:
    def _tracker(self):
        from workflow.providers.quota import QuotaTracker
        return QuotaTracker()

    def test_returns_zero_for_uncooled_providers(self):
        qt = self._tracker()
        result = qt.cooldown_remaining_dict(["claude-code", "ollama-local"])
        assert result["claude-code"] == 0
        assert result["ollama-local"] == 0

    def test_returns_positive_for_cooled_providers(self):
        qt = self._tracker()
        qt.cooldown("claude-code", 120)
        result = qt.cooldown_remaining_dict(["claude-code", "codex"])
        assert result["claude-code"] > 0
        assert result["codex"] == 0

    def test_all_providers_covered(self):
        qt = self._tracker()
        providers = ["claude-code", "codex", "gemini-free", "groq-free"]
        result = qt.cooldown_remaining_dict(providers)
        assert set(result.keys()) == set(providers)


class TestChainDrainWarning:
    def test_chain_drain_emits_warning(self, caplog):
        """When all API providers are cooled and chain falls through,
        CHAIN_DRAINED warning must appear in the log."""
        import asyncio
        from unittest.mock import AsyncMock

        from workflow.providers.quota import QuotaTracker
        from workflow.providers.router import FALLBACK_CHAINS, ProviderRouter

        qt = QuotaTracker()
        # Cool all API providers in the writer chain.
        for p in FALLBACK_CHAINS["writer"]:
            if p != "ollama-local":
                qt.cooldown(p, 120)

        # Make ollama-local fail too so the chain exhausts (no providers succeed).
        mock_local = AsyncMock()
        mock_local.name = "ollama-local"
        mock_local.complete.side_effect = Exception("local failed")

        router = ProviderRouter(providers={"ollama-local": mock_local}, quota=qt)

        from workflow.exceptions import AllProvidersExhaustedError
        with caplog.at_level(logging.WARNING, logger="workflow.providers.router"):
            with pytest.raises(AllProvidersExhaustedError):
                asyncio.run(router.call("writer", "prompt", "system"))

        assert any(
            "CHAIN_DRAINED" in record.message
            for record in caplog.records
        ), "CHAIN_DRAINED warning not emitted when all API providers in cooldown"


class TestGetStatusCooldownField:
    def test_get_status_has_per_provider_cooldown_remaining(self):
        """get_status must include per_provider_cooldown_remaining dict."""
        from workflow.universe_server import get_status
        payload = json.loads(get_status())
        assert "per_provider_cooldown_remaining" in payload
        assert isinstance(payload["per_provider_cooldown_remaining"], dict)

    def test_per_provider_cooldown_remaining_values_are_ints(self):
        """All values in per_provider_cooldown_remaining must be non-negative ints."""
        from workflow.universe_server import get_status
        remaining = json.loads(get_status())["per_provider_cooldown_remaining"]
        for provider, seconds in remaining.items():
            assert isinstance(seconds, int), f"{provider}: expected int, got {type(seconds)}"
            assert seconds >= 0, f"{provider}: negative cooldown seconds"

    def test_schema_contract_includes_per_provider_field(self):
        """Contract test: schema_version=1 contract must include the new field."""
        from workflow.universe_server import get_status
        payload = json.loads(get_status())
        assert "per_provider_cooldown_remaining" in payload, (
            "per_provider_cooldown_remaining not in get_status schema_version=1 response"
        )
