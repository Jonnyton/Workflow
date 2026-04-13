"""Base types for the provider layer.

Every provider implements :class:`BaseProvider`.  The router and all
consumers work with :class:`ProviderResponse` and :class:`ModelConfig`.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Configuration passed to every provider call."""

    timeout: int = 300
    """Subprocess / HTTP timeout in seconds."""

    max_tokens: int | None = None
    """Optional token cap (provider-specific interpretation)."""

    temperature: float = 0.7


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Uniform response envelope returned by every provider."""

    text: str
    provider: str
    model: str
    family: str
    latency_ms: float
    degraded: bool = False


# Sentinel for quality-floor-only degraded judge responses.
DEGRADED_JUDGE_RESPONSE = ProviderResponse(
    text="",
    provider="none",
    model="quality-floor-only",
    family="none",
    latency_ms=0.0,
    degraded=True,
)


class BaseProvider(abc.ABC):
    """Abstract base for all LLM providers."""

    name: str = ""
    """Short identifier used in fallback chains (e.g. ``'claude-code'``)."""

    family: str = ""
    """Model family for judge diversity enforcement."""

    @abc.abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str,
        config: ModelConfig,
    ) -> ProviderResponse:
        """Send *prompt* with *system* instructions and return a response."""
