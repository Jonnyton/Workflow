"""Exception hierarchy for Workflow.

Every exception in the system inherits from FantasyAuthorError so callers
can catch broadly when appropriate.
"""


class FantasyAuthorError(Exception):
    """Base exception for all Workflow errors."""


# ---------------------------------------------------------------------------
# Provider errors
# ---------------------------------------------------------------------------

class ProviderError(FantasyAuthorError):
    """A provider call failed for a non-transient reason."""


class ProviderTimeoutError(ProviderError):
    """A provider subprocess exceeded the activity timeout."""


class ProviderUnavailableError(ProviderError):
    """Provider returned a signal that it is temporarily unreachable
    (e.g. exit code 1 within <5 s, rate-limit header, auth failure).
    Triggers a sticky cooldown on the provider.
    """


class AllProvidersExhaustedError(ProviderError):
    """Every provider in the fallback chain failed or is in cooldown."""


# ---------------------------------------------------------------------------
# Graph / checkpoint errors
# ---------------------------------------------------------------------------

class CheckpointError(FantasyAuthorError):
    """Failed to save or load a LangGraph checkpoint."""


class GraphCompilationError(FantasyAuthorError):
    """A StateGraph could not be compiled (topology issue)."""


# ---------------------------------------------------------------------------
# State / validation errors
# ---------------------------------------------------------------------------

class StateValidationError(FantasyAuthorError):
    """State dict is missing required keys or has invalid types."""


class ConstraintViolationError(FantasyAuthorError):
    """ASP solver reported an unsatisfiable model (world rule breach)."""
