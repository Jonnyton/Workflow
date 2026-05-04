"""Back-compat shim: ``domains.fantasy_author.phases`` mirrors
``domains.fantasy_daemon.phases``.

This package stays separate from the canonical target package so imports like
``from domains.fantasy_author.phases import orient`` keep returning the
re-exported callables even after old-path submodules are imported elsewhere.
Deep submodule imports still resolve to the canonical modules via the shared
rename-alias finder.
"""

from __future__ import annotations

import sys
import types
import warnings

from workflow._rename_compat import install_module_alias, rename_compat_enabled

if not rename_compat_enabled():
    raise ImportError(
        "domains.fantasy_author.phases is deprecated; import "
        "domains.fantasy_daemon.phases instead. Set "
        "WORKFLOW_AUTHOR_RENAME_COMPAT=1 to temporarily re-enable the "
        "back-compat shim."
    )

warnings.warn(
    "domains.fantasy_author.phases is a back-compat alias; migrate imports "
    "to domains.fantasy_daemon.phases",
    DeprecationWarning,
    stacklevel=2,
)

_alias_module = sys.modules[__name__]
import domains.fantasy_daemon.phases as _phases  # noqa: E402

install_module_alias(__name__, "domains.fantasy_daemon.phases")
sys.modules[__name__] = _alias_module
__doc__ = _phases.__doc__
__all__ = list(getattr(_phases, "__all__", ()))
__path__ = list(getattr(_phases, "__path__", ()))

from domains.fantasy_daemon.phases import (  # noqa: E402,F401
    activity_log,
    book_close,
    commit,
    consolidate,
    diagnose,
    draft,
    learn,
    orient,
    plan,
    reflect,
    select_task,
    universe_cycle,
    worldbuild,
)


class _PhaseAliasModule(types.ModuleType):
    """Keep callable phase exports stable even after old-path submodule imports."""

    _target_module: types.ModuleType
    _callable_exports: set[str]

    def __setattr__(self, name: str, value) -> None:
        if (
            name in object.__getattribute__(self, "_callable_exports")
            and isinstance(value, types.ModuleType)
        ):
            target = object.__getattribute__(self, "_target_module")
            target_value = getattr(target, name, None)
            if callable(target_value):
                return
        super().__setattr__(name, value)


_alias_module.__class__ = _PhaseAliasModule
_alias_module._target_module = _phases
_alias_module._callable_exports = set(__all__)


def __getattr__(name: str):
    return getattr(_phases, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_phases)))
