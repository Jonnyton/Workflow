"""Provider router -- fallback chains across six providers.

Hard invariant: every call has a fallback chain that terminates at
``ollama-local``.  The system NEVER stops due to provider
unavailability unless local models are also down.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging

from fantasy_author.exceptions import (
    AllProvidersExhaustedError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from fantasy_author.providers.base import (
    DEGRADED_JUDGE_RESPONSE,
    BaseProvider,
    ModelConfig,
    ProviderResponse,
)
from fantasy_author.providers.quota import (
    COOLDOWN_OTHER,
    COOLDOWN_TIMEOUT,
    COOLDOWN_UNAVAILABLE,
    QuotaTracker,
)

logger = logging.getLogger(__name__)

def _default_config() -> ModelConfig:
    """Build default ModelConfig from universe config if available."""
    try:
        from fantasy_author import runtime

        cfg = runtime.universe_config
        return ModelConfig(
            temperature=cfg.temperature,
            timeout=cfg.timeout,
            max_tokens=cfg.max_tokens,
        )
    except Exception:
        return ModelConfig()

# Fallback chains per role (spec Section 8.3).
FALLBACK_CHAINS: dict[str, list[str]] = {
    "writer": ["claude-code", "codex", "gemini-free", "groq-free", "grok-free", "ollama-local"],
    "judge": ["codex", "gemini-free", "groq-free", "grok-free", "ollama-local"],
    "extract": ["codex", "gemini-free", "groq-free", "ollama-local"],
    "embed": ["ollama-local"],
}

# Judge providers to fan out to in parallel.  Every available provider
# gets one call; results are collected and aggregated.  No chains,
# no fallbacks — just "call everyone, return all responses."
_JUDGE_PROVIDERS: list[str] = [
    "codex", "gemini-free", "groq-free", "grok-free", "ollama-local",
]


class ProviderRouter:
    """Routes LLM calls across providers with fallback and quota tracking.

    Parameters
    ----------
    providers : dict[str, BaseProvider]
        Map from provider name to provider instance.  Only providers
        present in this dict are reachable.
    quota : QuotaTracker | None
        Shared quota tracker.  A default is created if not supplied.
    """

    def __init__(
        self,
        providers: dict[str, BaseProvider] | None = None,
        quota: QuotaTracker | None = None,
    ) -> None:
        self._providers: dict[str, BaseProvider] = providers or {}
        self._quota = quota or QuotaTracker()

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def register(self, provider: BaseProvider) -> None:
        """Add or replace a provider in the registry."""
        self._providers[provider.name] = provider

    @property
    def available_providers(self) -> list[str]:
        return list(self._providers)

    # ------------------------------------------------------------------
    # Core routing
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_preference(chain: list[str], preferred: str) -> list[str]:
        """Reorder *chain* so *preferred* comes first (if present)."""
        if not preferred or preferred not in chain:
            return chain
        return [preferred] + [p for p in chain if p != preferred]

    async def call(
        self,
        role: str,
        prompt: str,
        system: str,
        config: ModelConfig | None = None,
    ) -> ProviderResponse:
        """Route a single call through the fallback chain for *role*.

        Returns a :class:`ProviderResponse` on success.  For judge role,
        returns a degraded sentinel when all providers are exhausted.
        For other roles, raises :class:`AllProvidersExhaustedError`.
        """
        cfg = config or _default_config()
        chain = FALLBACK_CHAINS.get(role, FALLBACK_CHAINS["writer"])

        # Apply per-universe provider preference from config.yaml
        try:
            from fantasy_author import runtime
            ucfg = runtime.universe_config
            if role == "writer" and ucfg.preferred_writer:
                chain = self._apply_preference(chain, ucfg.preferred_writer)
            elif role == "judge" and ucfg.preferred_judge:
                chain = self._apply_preference(chain, ucfg.preferred_judge)
        except Exception:
            pass

        for provider_name in chain:
            provider = self._providers.get(provider_name)
            if provider is None:
                logger.info("Provider %s not in registry, skipping", provider_name)
                continue
            if not self._quota.available(provider_name):
                logger.info("Skipping %s (quota/cooldown)", provider_name)
                continue

            logger.info("Trying provider %s for role=%s", provider_name, role)
            try:
                resp = await provider.complete(prompt, system, cfg)
                self._quota.record_success(provider_name)
                return resp
            except ProviderUnavailableError:
                self._quota.cooldown(provider_name, COOLDOWN_UNAVAILABLE)
                logger.warning(
                    "Provider %s unavailable, cooldown %ds",
                    provider_name, COOLDOWN_UNAVAILABLE,
                )
            except ProviderTimeoutError:
                self._quota.cooldown(provider_name, COOLDOWN_TIMEOUT)
                logger.warning(
                    "Provider %s timed out, cooldown %ds",
                    provider_name, COOLDOWN_TIMEOUT,
                )
            except ProviderError as exc:
                self._quota.cooldown(provider_name, COOLDOWN_OTHER)
                logger.warning(
                    "Provider %s error, cooldown %ds: %s",
                    provider_name, COOLDOWN_OTHER, exc,
                )
            except Exception:
                self._quota.cooldown(provider_name, COOLDOWN_OTHER)
                logger.exception("Unexpected error from %s", provider_name)

        # All providers exhausted.
        if role == "judge":
            logger.warning("All judge providers exhausted -- returning degraded response")
            return DEGRADED_JUDGE_RESPONSE

        raise AllProvidersExhaustedError(
            f"All providers exhausted for role={role}. "
            "Daemon should retry with backoff."
        )

    # ------------------------------------------------------------------
    # Synchronous wrapper (for use from sync graph nodes)
    # ------------------------------------------------------------------

    _thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def call_sync(
        self,
        role: str,
        prompt: str,
        system: str,
        config: ModelConfig | None = None,
    ) -> ProviderResponse:
        """Synchronous version of :meth:`call` for use from sync code.

        Runs the async ``call`` in a dedicated thread with its own event
        loop, avoiding the "loop already running" problem that blocks
        ``loop.run_until_complete`` inside LangGraph nodes.
        """
        cfg = config or _default_config()
        # Allow the subprocess timeout to fire first (+30s margin for
        # async overhead, fallback attempts, etc.)
        sync_timeout = cfg.timeout + 30

        def _run() -> ProviderResponse:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self.call(role, prompt, system, config)
                )
            finally:
                loop.close()

        future = self._thread_pool.submit(_run)
        try:
            return future.result(timeout=sync_timeout)
        except concurrent.futures.TimeoutError:
            logger.warning(
                "call_sync timed out after %ds for role=%s",
                sync_timeout, role,
            )
            raise ProviderTimeoutError(
                f"call_sync exceeded {sync_timeout}s hard timeout for role={role}"
            )

    # ------------------------------------------------------------------
    # Judge ensemble (model family diversity)
    # ------------------------------------------------------------------

    async def call_judge_ensemble(
        self,
        prompt: str,
        system: str,
        config: ModelConfig | None = None,
    ) -> list[ProviderResponse]:
        """Fan out to ALL available judge providers in parallel.

        Calls every registered, non-cooldown provider once.  Never
        calls the same provider twice.  Returns 1-N responses
        depending on how many providers are healthy.
        """
        cfg = config or _default_config()

        # Find all available judge providers
        available: list[tuple[str, BaseProvider]] = []
        for name in _JUDGE_PROVIDERS:
            provider = self._providers.get(name)
            if provider is None:
                continue
            if not self._quota.available(name):
                logger.debug("Judge provider %s in cooldown, skipping", name)
                continue
            available.append((name, provider))

        if not available:
            logger.warning("No judge providers available")
            return []

        # Fan out in parallel
        async def _call_one(
            name: str, provider: BaseProvider,
        ) -> ProviderResponse | None:
            try:
                resp = await provider.complete(prompt, system, cfg)
                self._quota.record_success(name)
                return resp
            except ProviderUnavailableError:
                self._quota.cooldown(name, COOLDOWN_UNAVAILABLE)
            except ProviderTimeoutError:
                self._quota.cooldown(name, COOLDOWN_TIMEOUT)
            except Exception:
                self._quota.cooldown(name, COOLDOWN_OTHER)
            return None

        tasks = [_call_one(name, prov) for name, prov in available]
        raw_results = await asyncio.gather(*tasks)

        results = [r for r in raw_results if r is not None]
        logger.info(
            "Judge ensemble: %d/%d providers responded",
            len(results), len(available),
        )
        return results
