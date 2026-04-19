"""Shim: ``fantasy_daemon.runtime`` IS ``workflow.runtime``.

Re-binding ``sys.modules`` so ``import fantasy_daemon.runtime`` returns
the same module object as ``import workflow.runtime``. A bare
``from workflow.runtime import *`` would only snapshot bindings at
import time, so writes via one alias would not be visible through the
other — that mismatch silently broke daemon/API state sharing.
"""
import sys

import workflow.runtime as _wr

sys.modules[__name__] = _wr
