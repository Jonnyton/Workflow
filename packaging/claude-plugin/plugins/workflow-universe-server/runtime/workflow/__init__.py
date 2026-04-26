"""Workflow -- goal-agnostic daemon engine on LangGraph."""

__version__ = "0.1.0"

from workflow.discovery import auto_register, discover_domains
from workflow.protocols import Domain, DomainConfig
from workflow.registry import DomainRegistry, default_registry

__all__ = [
    "Domain",
    "DomainConfig",
    "DomainRegistry",
    "auto_register",
    "default_registry",
    "discover_domains",
]
