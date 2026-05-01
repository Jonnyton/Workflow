"""Tests for BUG-029: thundering-herd chain-drain detection + backoff.

Part A: QuotaTracker.all_api_providers_in_cooldown + get_status exposure.
Part B: ProviderRouter raises AllProvidersExhaustedError when chain-drained
        and local provider returns empty prose N consecutive times.
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

    def test_first_empty_local_does_not_raise(self):
        """First empty response: threshold=2, no raise yet."""
        router, _, _ = _router_with_local(local_text="", threshold=2)
        resp = _run(router.call("writer", "p", "s"))
        assert resp.text == ""

    def test_second_empty_local_raises_when_chain_drained(self):
        """Second consecutive empty from local when all APIs in cooldown raises."""
        router, _, _ = _router_with_local(local_text="", threshold=2)
        _run(router.call("writer", "p", "s"))  # first empty — no raise
        with pytest.raises(AllProvidersExhaustedError, match="empty prose"):
            _run(router.call("writer", "p", "s"))

    def test_raise_message_includes_provider_name_and_count(self):
        router, _, _ = _router_with_local(local_text="", threshold=2)
        _run(router.call("writer", "p", "s"))
        with pytest.raises(AllProvidersExhaustedError) as exc_info:
            _run(router.call("writer", "p", "s"))
        msg = str(exc_info.value)
        assert "ollama-local" in msg
        assert "2" in msg

    def test_empty_counter_resets_on_non_empty_response(self):
        """After a non-empty response, the counter resets; no raise on next empty."""
        quota = QuotaTracker()
        call_num = 0

        class _AlternatingProvider(BaseProvider):
            name = "ollama-local"
            family = "fake"

            async def complete(self, prompt, system, config):
                nonlocal call_num
                call_num += 1
                text = "" if call_num % 2 == 1 else "content"
                return ProviderResponse(
                    text=text, provider="ollama-local",
                    model="fake", family="fake", latency_ms=0.0,
                )

        api_chain = [p for p in FALLBACK_CHAINS["writer"] if p != "ollama-local"]
        for p in api_chain:
            quota.cooldown(p, 120)

        router = ProviderRouter(
            providers={"ollama-local": _AlternatingProvider()},
            quota=quota,
            chain_drain_empty_threshold=2,
        )
        _run(router.call("writer", "p", "s"))   # empty (count=1)
        _run(router.call("writer", "p", "s"))   # content (reset)
        # Next empty is count=1 again — no raise
        resp = _run(router.call("writer", "p", "s"))
        assert resp.text == ""

    def test_threshold_1_raises_on_first_empty(self):
        router, _, _ = _router_with_local(local_text="", threshold=1)
        with pytest.raises(AllProvidersExhaustedError):
            _run(router.call("writer", "p", "s"))

    def test_no_raise_when_api_provider_available(self):
        """Empty local response does NOT raise when an API provider is available."""
        quota = QuotaTracker()
        local = _FakeProvider("ollama-local", text="")
        api = _FakeProvider("claude-code", text="")
        router = ProviderRouter(
            providers={"claude-code": api, "ollama-local": local},
            quota=quota,
            chain_drain_empty_threshold=2,
        )
        # claude-code is available (not in cooldown). It should be tried first.
        # Even if it returns empty, chain is NOT drained, so no raise.
        resp = _run(router.call("writer", "p", "s"))
        assert resp.text == ""
        resp = _run(router.call("writer", "p", "s"))
        assert resp.text == ""

    def test_empty_non_local_provider_falls_through_to_next_provider(self):
        """BUG-036: empty prose from a primary provider is not a successful run."""
        empty_primary = _FakeProvider("claude-code", text="")
        fallback = _FakeProvider("codex", text="fallback content")
        router = ProviderRouter(
            providers={"claude-code": empty_primary, "codex": fallback},
            chain_drain_empty_threshold=2,
        )

        resp = _run(router.call("writer", "p", "s"))

        assert resp.text == "fallback content"
        assert resp.provider == "codex"
        assert empty_primary.call_count == 1
        assert fallback.call_count == 1
