"""Back-compat helpers for the Author -> Daemon rename transition.

Active during Phases 1-4. Flipped off (and file removed) in Phase 5.
See docs/exec-plans/active/2026-04-15-author-to-daemon-rename.md.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import os
import sys
import types

_ALIAS_FINDER_KEY = "_workflow_rename_alias_finder"

_FLAG_ENV = "WORKFLOW_AUTHOR_RENAME_COMPAT"


def rename_compat_enabled() -> bool:
    """Return True when back-compat shims/aliases should be exported."""
    raw = os.environ.get(_FLAG_ENV, "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


class _RenameAliasLoader(importlib.abc.Loader):
    """Loader that returns the canonical target module for an alias path."""

    def __init__(
        self,
        alias_name: str,
        target_name: str,
        target_spec: importlib.machinery.ModuleSpec,
    ) -> None:
        self._alias_name = alias_name
        self._target_name = target_name
        self._target_spec = target_spec

    def create_module(
        self,
        spec: importlib.machinery.ModuleSpec,
    ) -> object | None:
        target_module = importlib.import_module(self._target_name)
        module = _AliasModuleProxy(self._alias_name, self._target_name, target_module)
        module.__dict__["__file__"] = getattr(target_module, "__file__", None)
        module.__dict__["__package__"] = self._alias_name.rpartition(".")[0]
        module.__dict__["__doc__"] = getattr(target_module, "__doc__", None)
        if hasattr(target_module, "__path__"):
            module.__dict__["__path__"] = list(getattr(target_module, "__path__", []))
        if hasattr(target_module, "__all__"):
            module.__dict__["__all__"] = getattr(target_module, "__all__")
        sys.modules[self._alias_name] = module
        return module

    def exec_module(self, module: object) -> None:
        # The target module is already initialized by ``create_module``.
        return None

    def get_code(self, fullname: str):
        loader = self._target_spec.loader
        if loader is None:
            return None
        get_code = getattr(loader, "get_code", None)
        if get_code is None:
            return None
        return get_code(self._target_name)

    def get_source(self, fullname: str):
        loader = self._target_spec.loader
        if loader is None:
            return None
        get_source = getattr(loader, "get_source", None)
        if get_source is None:
            return None
        return get_source(self._target_name)

    def is_package(self, fullname: str) -> bool:
        return self._target_spec.submodule_search_locations is not None


class _RenameAliasFinder(importlib.abc.MetaPathFinder):
    """Meta-path finder that maps alias import prefixes onto target prefixes."""

    def __init__(self) -> None:
        self._prefix_pairs: dict[str, str] = {}

    def register(self, alias_prefix: str, target_prefix: str) -> None:
        self._prefix_pairs[alias_prefix] = target_prefix

    def find_spec(
        self,
        fullname: str,
        path: object | None,
        target: object | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        for alias_prefix, target_prefix in self._prefix_pairs.items():
            if fullname != alias_prefix and not fullname.startswith(alias_prefix + "."):
                continue
            target_name = target_prefix + fullname[len(alias_prefix):]
            target_spec = importlib.machinery.PathFinder.find_spec(target_name, path)
            if target_spec is None:
                return None
            is_package = target_spec.submodule_search_locations is not None
            spec = importlib.machinery.ModuleSpec(
                fullname,
                _RenameAliasLoader(fullname, target_name, target_spec),
                is_package=is_package,
            )
            spec.origin = target_spec.origin
            if is_package:
                spec.submodule_search_locations = list(
                    target_spec.submodule_search_locations or []
                )
            return spec
        return None


class _AliasModuleProxy(types.ModuleType):
    """Forward an alias module's behavior onto its canonical target module."""

    def __init__(
        self,
        alias_name: str,
        target_name: str,
        target_module: types.ModuleType,
    ) -> None:
        super().__init__(alias_name)
        self.__dict__["_alias_target_name"] = target_name
        self.__dict__["_alias_target_module"] = target_module

    def __getattr__(self, name: str):
        return getattr(self.__dict__["_alias_target_module"], name)

    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_alias_") or name.startswith("__"):
            self.__dict__[name] = value
            return
        setattr(self.__dict__["_alias_target_module"], name, value)

    def __delattr__(self, name: str) -> None:
        if name.startswith("_alias_") or name.startswith("__"):
            self.__dict__.pop(name, None)
            return
        delattr(self.__dict__["_alias_target_module"], name)

    def __dir__(self) -> list[str]:
        return sorted(
            set(super().__dir__()) | set(dir(self.__dict__["_alias_target_module"]))
        )

    def __call__(self, *args, **kwargs):
        leaf_name = self.__name__.rpartition(".")[2]
        target_callable = getattr(self.__dict__["_alias_target_module"], leaf_name, None)
        if not callable(target_callable):
            raise TypeError(f"Module {self.__name__!r} is not callable")
        return target_callable(*args, **kwargs)


def _alias_finder() -> _RenameAliasFinder:
    finder = getattr(sys, _ALIAS_FINDER_KEY, None)
    if finder is None:
        finder = _RenameAliasFinder()
        setattr(sys, _ALIAS_FINDER_KEY, finder)
        sys.meta_path.insert(0, finder)
    return finder


def install_module_alias(alias_prefix: str, target_prefix: str) -> None:
    """Bind ``alias_prefix`` to ``target_prefix`` for current + future imports.

    This keeps old and new import paths pointing at the exact same module
    objects, including deep submodules imported later. That matters for the
    rename window because test patches and module-level state must propagate
    across both paths.
    """
    finder = _alias_finder()
    finder.register(alias_prefix, target_prefix)

    target_module = importlib.import_module(target_prefix)
    sys.modules[alias_prefix] = target_module

    prefix = target_prefix + "."
    for name, module in list(sys.modules.items()):
        if not name.startswith(prefix):
            continue
        alias_name = alias_prefix + name[len(target_prefix):]
        sys.modules[alias_name] = module
