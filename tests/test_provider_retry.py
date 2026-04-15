"""Tests for provider retry with tenacity."""

from __future__ import annotations

from unittest.mock import MagicMock

from domains.fantasy_author.phases import _provider_stub
from workflow.exceptions import AllProvidersExhaustedError


class TestProviderRetry:
    def setup_method(self):
        self._orig_mock = _provider_stub._FORCE_MOCK
        _provider_stub._FORCE_MOCK = False

    def teardown_method(self):
        _provider_stub._FORCE_MOCK = self._orig_mock

    def test_force_mock_bypasses_retry(self):
        _provider_stub._FORCE_MOCK = True
        result = _provider_stub.call_provider("test", fallback_response="mock")
        assert result == "mock"

    def test_force_mock_default_response(self):
        _provider_stub._FORCE_MOCK = True
        result = _provider_stub.call_provider("test")
        assert "[Mock response" in result

    def test_retry_succeeds_on_second_attempt(self):
        """Simulate transient exhaustion that clears on retry."""
        mock_router = MagicMock()
        mock_response = MagicMock()
        mock_response.provider = "test-provider"
        mock_response.text = "success after retry"

        # First call raises exhaustion, second succeeds
        mock_router.call_sync.side_effect = [
            AllProvidersExhaustedError("all exhausted"),
            mock_response,
        ]

        orig_router = _provider_stub._real_router
        _provider_stub._real_router = mock_router
        try:
            result = _provider_stub.call_provider("test prompt", role="writer")
            assert result == "success after retry"
            assert mock_router.call_sync.call_count == 2
        finally:
            _provider_stub._real_router = orig_router

    def test_retry_exhausted_falls_to_fallback(self):
        """After 3 retry attempts, falls back to fallback_response."""
        mock_router = MagicMock()
        mock_router.call_sync.side_effect = AllProvidersExhaustedError("exhausted")

        orig_router = _provider_stub._real_router
        _provider_stub._real_router = mock_router
        try:
            result = _provider_stub.call_provider(
                "test", role="writer", fallback_response="fallback text"
            )
            assert result == "fallback text"
            # Should have retried 3 times
            assert mock_router.call_sync.call_count == 3
        finally:
            _provider_stub._real_router = orig_router

    def test_retry_exhausted_no_fallback_returns_empty(self):
        """After exhaustion with no fallback, returns empty string."""
        mock_router = MagicMock()
        mock_router.call_sync.side_effect = AllProvidersExhaustedError("exhausted")

        orig_router = _provider_stub._real_router
        _provider_stub._real_router = mock_router
        try:
            result = _provider_stub.call_provider("test", role="writer")
            assert result == ""
            assert mock_router.call_sync.call_count == 3
        finally:
            _provider_stub._real_router = orig_router

    def test_non_retryable_error_does_not_retry(self):
        """Non-AllProvidersExhaustedError should not trigger retry."""
        mock_router = MagicMock()
        mock_router.call_sync.side_effect = RuntimeError("unexpected")

        orig_router = _provider_stub._real_router
        _provider_stub._real_router = mock_router
        try:
            result = _provider_stub.call_provider(
                "test", role="writer", fallback_response="fb"
            )
            assert result == "fb"
            # Only called once — no retry on generic RuntimeError
            assert mock_router.call_sync.call_count == 1
        finally:
            _provider_stub._real_router = orig_router

    def test_no_router_uses_fallback(self):
        """When _real_router is None, goes straight to fallback."""
        orig_router = _provider_stub._real_router
        _provider_stub._real_router = None
        try:
            result = _provider_stub.call_provider(
                "test", fallback_response="no router fallback"
            )
            assert result == "no router fallback"
        finally:
            _provider_stub._real_router = orig_router
