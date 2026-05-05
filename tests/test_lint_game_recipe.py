import pytest

from scripts.lint_game_recipe import GameRecipeLintError, lint_game_recipe


def test_retroarch_recipe_accepts_core_and_firmware_artifacts():
    recipe = {
        "kind": "GameRecipe",
        "runtime_family": "retroarch",
        "artifacts": {
            "cores": [
                {
                    "role": "libretro_core",
                    "name": "snes9x",
                    "source": "system package",
                }
            ],
            "firmware": [
                {
                    "role": "system_bios",
                    "name": "optional cartridge firmware",
                    "required": False,
                    "rights": "not_bundled",
                }
            ],
        },
    }

    assert lint_game_recipe(recipe) == []


def test_amiga_recipe_accepts_emulator_core_and_kickstart_firmware():
    recipe = {
        "kind": "GameRecipe",
        "runtime_family": "amiga",
        "artifacts": {
            "cores": [
                {
                    "role": "browser_emulator",
                    "name": "vAmigaWeb",
                    "source": "https://vamigaweb.github.io/",
                }
            ],
            "firmware": [
                {
                    "role": "kickstart_rom",
                    "name": "Kickstart 1.3",
                    "path": "licensed/kickstart-a500-1.3.rom",
                    "required": True,
                    "rights": "host_rights_cleared",
                },
                {
                    "role": "kickstart_replacement",
                    "name": "AROS Kickstart replacement",
                    "required": False,
                    "rights": "open_source",
                },
            ],
        },
    }

    assert lint_game_recipe(recipe) == []


def test_game_recipe_rejects_unknown_core_role():
    recipe = {
        "kind": "GameRecipe",
        "runtime_family": "retroarch",
        "artifacts": {
            "cores": [{"role": "dll", "name": "snes9x"}],
            "firmware": [],
        },
    }

    with pytest.raises(GameRecipeLintError, match="artifacts.cores\\[0\\].role"):
        lint_game_recipe(recipe)


def test_game_recipe_rejects_firmware_without_rights_status():
    recipe = {
        "kind": "GameRecipe",
        "runtime_family": "amiga",
        "artifacts": {
            "cores": [{"role": "browser_emulator", "name": "vAmigaWeb"}],
            "firmware": [{"role": "kickstart_rom", "name": "Kickstart 1.3"}],
        },
    }

    with pytest.raises(GameRecipeLintError, match="artifacts.firmware\\[0\\].rights"):
        lint_game_recipe(recipe)
