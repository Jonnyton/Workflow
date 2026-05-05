"""Lint GameRecipe artifact schema for classic-game runtime recipes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CORE_ROLES = frozenset(
    {
        "libretro_core",
        "retroarch_core",
        "browser_emulator",
        "native_emulator",
        "amiga_emulator",
    }
)

FIRMWARE_ROLES = frozenset(
    {
        "system_bios",
        "kickstart_rom",
        "kickstart_replacement",
        "firmware_blob",
    }
)

FIRMWARE_RIGHTS = frozenset(
    {
        "bundled_open",
        "host_rights_cleared",
        "user_provided",
        "not_bundled",
        "open_source",
    }
)


class GameRecipeLintError(ValueError):
    """Raised when a GameRecipe document violates the artifact schema."""


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GameRecipeLintError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise GameRecipeLintError(f"{path} must be a list")
    return value


def _require_non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GameRecipeLintError(f"{path} must be a non-empty string")
    return value.strip()


def _lint_role(entry: dict[str, Any], *, path: str, allowed_roles: frozenset[str]) -> None:
    role = _require_non_empty_string(entry.get("role"), f"{path}.role")
    if role not in allowed_roles:
        allowed = ", ".join(sorted(allowed_roles))
        raise GameRecipeLintError(f"{path}.role must be one of: {allowed}")
    _require_non_empty_string(entry.get("name"), f"{path}.name")


def _lint_core(entry: Any, path: str) -> None:
    core = _require_mapping(entry, path)
    _lint_role(core, path=path, allowed_roles=CORE_ROLES)


def _lint_firmware(entry: Any, path: str) -> None:
    firmware = _require_mapping(entry, path)
    _lint_role(firmware, path=path, allowed_roles=FIRMWARE_ROLES)
    rights = _require_non_empty_string(firmware.get("rights"), f"{path}.rights")
    if rights not in FIRMWARE_RIGHTS:
        allowed = ", ".join(sorted(FIRMWARE_RIGHTS))
        raise GameRecipeLintError(f"{path}.rights must be one of: {allowed}")
    if "required" in firmware and not isinstance(firmware["required"], bool):
        raise GameRecipeLintError(f"{path}.required must be a boolean when present")


def lint_game_recipe(recipe: dict[str, Any]) -> list[str]:
    """Validate the GameRecipe artifacts contract.

    The linter is intentionally schema-shaped and side-effect-free. It accepts
    existing recipes that do not have artifact metadata yet, but once
    ``artifacts.cores`` or ``artifacts.firmware`` is present each entry must
    declare a role, name, and firmware rights status where applicable.
    """
    _require_mapping(recipe, "recipe")
    if recipe.get("kind") not in (None, "GameRecipe"):
        raise GameRecipeLintError("kind must be GameRecipe when present")

    artifacts = recipe.get("artifacts")
    if artifacts is None:
        return []
    artifacts_map = _require_mapping(artifacts, "artifacts")

    cores = artifacts_map.get("cores", [])
    firmware = artifacts_map.get("firmware", [])
    for index, entry in enumerate(_require_list(cores, "artifacts.cores")):
        _lint_core(entry, f"artifacts.cores[{index}]")
    for index, entry in enumerate(_require_list(firmware, "artifacts.firmware")):
        _lint_firmware(entry, f"artifacts.firmware[{index}]")

    return []


def lint_game_recipe_file(path: Path) -> list[str]:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    return lint_game_recipe(recipe)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    args = parser.parse_args()

    lint_game_recipe_file(args.recipe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
