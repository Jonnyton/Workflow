"""Tests for BUG-029: thundering-herd chain-drain detection + backoff.

Part A: QuotaTracker.all_api_providers_in_cooldown + get_status exposure.
Part B: ProviderRouter raises AllProvidersExhaustedError when chain-drained
        and local provider returns empty prose.
"""
from __future__ import annotations

import asyncio

import pytest

from workflow.exceptions import AllProvidersExhaustedError
from workflow.providers.base import BaseProvider, ModelConfig, ProviderResponse
from workflow.providers.quota import QuotaTracker
from workflow.providers.router import FALLBACK_CHAINS, ProviderRouter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeProvider(BaseProvider):
    def __init__(self, name: str, text: str = "content") -> None:
        self.name = name
        self.family = "fake"
        self._text = text
        self.call_count = 0

    async def complete(
        self, prompt: str, system: str, config: ModelConfig
    ) -> ProviderResponse:
        self.call_count += 1
        return ProviderResponse(
            text=self._text, provider=self.name,
            model="fake", family="fake", latency_ms=0.0,
        )


def _run(coro):
    return asyncio.run(coro)


def _router_with_local(
    local_text: str = "content",
    threshold: int = 2,
) -> tuple[ProviderRouter, QuotaTracker, _FakeProvider]:
    """Return (router, quota, local_provider) with all API providers in cooldown."""
    quota = QuotaTracker()
    local = _FakeProvider("ollama-local", text=local_text)
    router = ProviderRouter(
        providers={"ollama-local": local},
        quota=quota,
        chain_drain_empty_threshold=threshold,
    )
    # Put all API providers in the writer chain into cooldown.
    api_chain = [p for p in FALLBACK_CHAINS["writer"] if p != "ollama-local"]
    for p in api_chain:
        quota.cooldown(p, seconds=120)
    return router, quota, local


# ---------------------------------------------------------------------------
# Part A — QuotaTracker.all_api_providers_in_cooldown
# ---------------------------------------------------------------------------


class TestAllApiProvidersInCooldown:
    def test_returns_true_when_all_api_in_cooldown(self):
        qt = QuotaTracker()
        chain = ["claude-code", "codex", "ollama-local"]
        qt.cooldown("claude-code", 120)
        qt.cooldown("codex", 120)
        assert qt.all_api_providers_in_cooldown(chain) is True

    def test_returns_false_when_one_api_available(self):
        qt = QuotaTracker()
        chain = ["claude-code", "codex", "ollama-local"]
        qt.cooldown("claude-code", 120)
        # codex not in cooldown
        assert qt.all_api_providers_in_cooldown(chain) is False

    def test_returns_false_when_chain_is_local_only(self):
        qt = QuotaTracker()
        chain = ["ollama-local"]
        # No API providers in chain — returns False (nothing to drain).
        assert qt.all_api_providers_in_cooldown(chain) is False

    def test_custom_local_providers_respected(self):
        qt = QuotaTracker()
        chain = ["api-provider", "my-local"]
        qt.cooldown("api-provider", 120)
        assert qt.all_api_providers_in_cooldown(chain, local_providers={"my-local"}) is True

    def test_returns_false_when_no_providers(self):
        qt = QuotaTracker()
        assert qt.all_api_providers_in_cooldown([]) is False

    def test_cooldown_remaining_dict_includes_all_providers(self):
        qt = QuotaTracker()
        qt.cooldown("claude-code", 60)
        result = qt.cooldown_remaining_dict(["claude-code", "codex"])
        assert "claude-code" in result
        assert result["claude-code"] > 0
        assert result["codex"] == 0


# ---------------------------------------------------------------------------
# Part B — ProviderRouter raises AllProvidersExhaustedError on chain-drain
# ---------------------------------------------------------------------------


class TestChainDrainBackoff:
    def test_normal_local_response_returned_without_raise(self):
        """When chain-drained but local produces content, return normally."""
        router, _, _ = _router_with_local(local_text="real content")
        resp = _run(router.call("writer", "p", "s"))
        assert resp.text == "real content"

    def test_empty_local_raises_when_chain_drained(self):
        """Empty local output is provider exhaustion, not successful prose."""
        router, _, _ = _router_with_local(local_text="", threshold=2)
        with pytest.raises(AllProvidersExhaustedError, match="All providers exhausted"):
            _run(router.call("writer", "p", "s"))

    def test_empty_local_records_empty_response_diagnostic(self):
        router, _, _ = _router_with_local(local_text="", threshold=2)
        with pytest.raises(AllProvidersExhaustedError) as exc_info:
            _run(router.call("writer", "p", "s"))
        attempts = {attempt.provider: attempt for attempt in exc_info.value.attempts}
        assert attempts["ollama-local"].skip_class == "empty_response"

    def test_empty_response_diagnostic_includes_provider_name(self):
        router, _, _ = _router_with_local(local_text="", threshold=2)
        with pytest.raises(AllProvidersExhaustedError) as exc_info:
            _run(router.call("writer", "p", "s"))
        providers = [attempt.provider for attempt in exc_info.value.attempts]
        assert "ollama-local" in providers

    def test_non_empty_response_after_empty_fallback_is_returned(self):
        quota = QuotaTracker()
        call_num = 0

        class _AlternatingProvider(BaseProvider):
            name = "claude-code"
            family = "fake"

            async def complete(self, prompt, system, config):
                nonlocal call_num
                call_num += 1
                text = "" if call_num % 2 == 1 else "content"
                return ProviderResponse(
                    text=text, provider="claude-code",
                    model="fake", family="fake", latency_ms=0.0,
                )

        local = _FakeProvider("ollama-local", text="local content")

        router = ProviderRouter(
            providers={
                "claude-code": _AlternatingProvider(),
                "ollama-local": local,
            },
            quota=quota,
            chain_drain_empty_threshold=2,
        )
        resp = _run(router.call("writer", "p", "s"))
        assert resp.text == "local content"

    def test_threshold_1_raises_on_first_empty(self):
        router, _, _ = _router_with_local(local_text="", threshold=1)
        with pytest.raises(AllProvidersExhaustedError):
            _run(router.call("writer", "p", "s"))

    def test_empty_api_provider_falls_back_to_local_content(self):
        """Empty API provider output does not block a later non-empty provider."""
        quota = QuotaTracker()
        local = _FakeProvider("ollama-local", text="local content")
        api = _FakeProvider("claude-code", text="")
        router = ProviderRouter(
            providers={"claude-code": api, "ollama-local": local},
            quota=quota,
            chain_drain_empty_threshold=2,
        )
        resp = _run(router.call("writer", "p", "s"))
        assert resp.text == "local content"
