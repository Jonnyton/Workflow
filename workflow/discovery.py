"""Domain auto-discovery for the workflow engine.

Scans the domains/ directory to find domain packages with skill.py files
and provides functions to dynamically import and register them.

Usage
-----
from workflow.discovery import discover_domains, auto_register
from workflow.registry import default_registry

domains = discover_domains()
auto_register(default_registry)

# Now all found domains are registered in default_registry
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def discover_domains() -> list[str]:
    """Scan the domains/ directory for domain packages.

    A domain package is identified by the presence of a skill.py file
    in the domains/<name>/ directory.

    Returns
    -------
    list[str]
        List of domain names (directory names with skill.py).
        Results are sorted for deterministic ordering.

    Notes
    -----
    This function assumes the domains/ directory exists at the same level
    as the workflow/ package. If it does not exist, returns an empty list.
    """
    # Locate the domains directory relative to this module
    workflow_dir = Path(__file__).parent.parent
    domains_dir = workflow_dir / "domains"

    if not domains_dir.exists():
        logger.debug("domains/ directory not found at %s", domains_dir)
        return []

    domain_names: list[str] = []

    for domain_path in sorted(domains_dir.iterdir()):
        if not domain_path.is_dir():
            continue

        skill_file = domain_path / "skill.py"
        if skill_file.exists():
            domain_names.append(domain_path.name)
            logger.debug("Discovered domain: %s", domain_path.name)

    return domain_names


def auto_register(registry: Any) -> None:
    """Discover and auto-register all domains in the registry.

    Scans the domains/ directory for skill.py files, imports the
    FantasyAuthorDomain class (or equivalent) from each domain's skill.py,
    and calls registry.register() with an instantiated domain.

    Parameters
    ----------
    registry : DomainRegistry
        Registry to populate. Expected to have a register(domain) method
        that accepts a Domain protocol instance.

    Notes
    -----
    If a domain fails to import or register, a warning is logged and
    the process continues with the next domain. Imports follow the
    expected pattern: domains.<name>.skill.

    For fantasy_author, imports domains.fantasy_author.skill.FantasyAuthorDomain.
    For research_probe, imports domains.research_probe.skill.ResearchProbeDomain.
    """
    discovered = discover_domains()

    if not discovered:
        logger.debug("No domains discovered")
        return

    for domain_name in discovered:
        try:
            # Construct the module path: domains.fantasy_author.skill
            module_path = f"domains.{domain_name}.skill"
            module = importlib.import_module(module_path)

            # Try to find the domain class. Use a heuristic:
            # FantasyAuthorDomain, ResearchProbeDomain, etc.
            # Also accept a generic "Domain" export.
            class_name = None
            if hasattr(module, "FantasyAuthorDomain") and domain_name == "fantasy_author":
                class_name = "FantasyAuthorDomain"
            elif hasattr(module, "ResearchProbeDomain") and domain_name == "research_probe":
                class_name = "ResearchProbeDomain"
            else:
                # Try to find any class that looks like a domain class
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and attr_name.endswith("Domain")
                        and attr_name != "Domain"
                    ):
                        class_name = attr_name
                        break

            if class_name is None:
                logger.warning(
                    "No domain class found in %s (expected %sDomain or Domain export)",
                    module_path,
                    "".join(word.capitalize() for word in domain_name.split("_")),
                )
                continue

            domain_class = getattr(module, class_name)
            domain_instance = domain_class()

            registry.register(domain_instance)
            logger.info("Registered domain %s from %s.%s", domain_name, module_path, class_name)

        except ImportError as e:
            logger.warning("Failed to import domain %s: %s", domain_name, e)
        except Exception as e:
            logger.warning("Failed to register domain %s: %s", domain_name, e)


__all__ = ["discover_domains", "auto_register"]
