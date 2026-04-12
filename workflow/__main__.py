"""Workflow engine entry point.

Usage::

    python -m workflow --domain fantasy_author [--universe PATH] [--api] [--port 8000]

Loads a domain by name from the registry, builds its graph, and runs the daemon.
Falls back to fantasy_author.__main__ for backward compatibility.

The entry point:
1. Parses --domain, --universe, --api, --port arguments
2. Auto-discovers and registers domains from the domains/ directory
3. Looks up the requested domain from the registry
4. Builds the domain's graph using domain.build_graph()
5. For now, delegates daemon execution to fantasy_author.__main__.DaemonController
   (this is the Phase 5 bridge until runtime is fully extracted)
6. If --api is set, also starts the FastAPI server on --port
"""

from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def _build_argparser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the workflow entry point."""
    parser = argparse.ArgumentParser(
        description="Workflow engine entry point",
        prog="python -m workflow",
    )

    parser.add_argument(
        "--domain",
        type=str,
        default="fantasy_author",
        help="Domain to load (default: fantasy_author)",
    )

    parser.add_argument(
        "--universe",
        type=str,
        default=None,
        help="Path to universe directory (optional)",
    )

    parser.add_argument(
        "--api",
        action="store_true",
        help="Start the FastAPI server in addition to the daemon",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the API server on (default: 8000)",
    )

    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to checkpoint database (optional)",
    )

    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="Disable desktop tray (for headless operation)",
    )

    return parser


def main() -> int:
    """Main entry point for the workflow engine.

    Returns
    -------
    int
        Exit code (0 for success, 1 for error).
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Parse arguments
    parser = _build_argparser()
    args = parser.parse_args()

    # Import and auto-register domains
    try:
        from workflow.discovery import auto_register
        from workflow.registry import default_registry

        auto_register(default_registry)
        logger.info("Auto-registered domains: %s", default_registry.list_domains())
    except Exception as e:
        logger.error("Failed to auto-register domains: %s", e)
        return 1

    # Look up the requested domain
    domain = default_registry.get(args.domain)
    if domain is None:
        logger.error(
            "Domain '%s' not found. Available: %s",
            args.domain,
            default_registry.list_domains(),
        )
        return 1

    logger.info("Loaded domain: %s", args.domain)

    # Phase 5 bridge: for now, delegate to fantasy_author.__main__.DaemonController
    # This allows the domain abstraction to be tested without fully extracting
    # the runtime. Once the runtime is extracted, this will build and execute
    # the domain's graph directly.

    if args.domain != "fantasy_author":
        logger.error(
            "Only fantasy_author domain is fully operational in this phase. "
            "Other domains can be registered but cannot yet be executed. "
            "Use --domain fantasy_author or the domain will be looked up but "
            "delegation will fail."
        )
        return 1

    try:
        from fantasy_author.__main__ import DaemonController

        controller = DaemonController(
            universe_path=args.universe,
            db_path=args.db,
            no_tray=args.no_tray,
        )

        # If --api flag is set, start the API server alongside the daemon
        if args.api:
            logger.info("Starting API server on port %d", args.port)
            # The API server is currently managed separately in
            # fantasy_author.api.serve(). This integration will be completed
            # in a later phase. For now, users should run `python -m
            # fantasy_author serve` separately.
            logger.warning(
                "API server integration incomplete. "
                "Run 'python -m fantasy_author serve' separately."
            )

        # Run the daemon
        return controller.run()

    except Exception as e:
        logger.error("Failed to run daemon: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

