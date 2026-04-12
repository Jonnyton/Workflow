"""Provider layer -- multi-provider routing with fallback chains.

Re-exports
----------
ProviderRouter    -- routes calls across providers with fallback + quota
ProviderResponse  -- uniform response envelope
ModelConfig       -- per-call configuration
BaseProvider      -- ABC for implementing new providers

Provider implementations are imported on demand to avoid hard
dependencies on optional packages (google-genai, groq).
"""

from workflow.providers.base import (
    DEGRADED_JUDGE_RESPONSE,
    BaseProvider,
    ModelConfig,
    ProviderResponse,
)
from workflow.providers.router import ProviderRouter

__all__ = [
    "BaseProvider",
    "DEGRADED_JUDGE_RESPONSE",
    "ModelConfig",
    "ProviderResponse",
    "ProviderRouter",
]
