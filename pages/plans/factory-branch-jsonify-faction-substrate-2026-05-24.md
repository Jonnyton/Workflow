---
title: Factory branch substrate improvement - JSONify faction registry
type: plan
status: working-draft
source_issue: 1050
request_id: WIKI-DESIGN
wiki_source_path: pages/plans/factory-branch-jsonify-faction-substrate-2026-05-24.md
wiki_source_import: partial-from-github-issue
wiki_source_imported: 2026-05-24
---

# Factory branch substrate improvement - JSONify faction registry

[[index]] [[factory-branch-remix-proof-stellar-front-2026-05-24]] [[splitroot-polish-art-direction-2026-05-24]] [[splitroot-polish-audio-direction-2026-05-24]]

Goal: `9171b100de33` (umbrella). Scope: **factory branch substrate**, not SPLITROOT-specific.

## Status

Working draft imported from Issue #1050. The source issue body was already truncated at 12,000 characters, so this page preserves the complete content available in the repository automation context and marks the missing tail explicitly. Do not treat the named-test list as complete until the original wiki body is recovered.

## Why this matters

The [[factory-branch-remix-proof-stellar-front-2026-05-24]] audit showed the substrate is genuinely remixable except for one friction point: faction-specific data lives in C++ - `EArchonFaction` enum switch cases inside `UArchonFactionMaterialBuilder`, `UArchonFactionAudioLibrary`, and `UArchonFactionMovementPolicyLibrary`.

That means a second canary, STELLAR FRONT or any other, must modify C++ to add factions. Substrate forks at the per-faction layer. Acceptable, but suboptimal.

This plan promotes per-faction data to JSON, making faction extensibility a **data change** rather than a code change. The substrate becomes truly remixable: same engine binary, different `factions.json`, different game.

## The current state (post SPLITROOT rung-2 prep)

| File | Hardcoded faction data |
|---|---|
| `Source/.../ArchonFactionTypes.h` | `EArchonFaction` enum - `None / VerdantChoir / KinwildCovenant / LenswrightCompact` |
| `Source/.../ArchonFactionMovementPolicyLibrary.cpp` | `GetMovementVerbForFaction` switch |
| `Source/.../ArchonFactionMaterialBuilder.cpp` (planned) | `GetFactionColor` switch |
| `Source/.../ArchonFactionAudioLibrary.cpp` (planned) | `GetFactionXxxCue` switch |
| `Source/.../ArchonHeroComponent` (planned) | `EArchonHeroFaction` derived from `EArchonFaction` |
| `FactoryContracts/factions.json v2` | Faction registry already exists in JSON; just under-used |

The disconnect: `factions.json` has the faction registry, but the C++ does not read it at runtime. It is documentation-only today.

## The target state

| File | New role |
|---|---|
| `FactoryContracts/factions.json v3` | Authoritative source. Adds palette, audio asset paths, movement-verb tuning, hero-locked-stats default override per faction. |
| `Source/.../ArchonFactionRegistry.h/.cpp` (new) | Singleton subsystem that loads `factions.json` at startup; exposes lookup API by `FName` faction id. |
| `EArchonFaction` enum | Deprecated but kept for backwards compatibility. Each entry maps to a canonical `FName` faction id. |
| `UArchonFactionRegistry::GetFactionByName(FName)` | Returns a `FArchonFactionRecord` with all the data the existing per-faction lookups would have returned. |
| `UArchonFactionMaterialBuilder::GetFactionColor` | Delegates to `FactionRegistry::GetFactionByName(...).GetPaletteSlot(slot)`. |
| `UArchonFactionMovementPolicyLibrary::GetMovementVerbForFaction` | Delegates to registry. |
| `UArchonFactionAudioLibrary` | Delegates to registry. |

The C++ enum becomes a thin compatibility layer over the JSON registry. Adding a new faction means adding a JSON entry plus, optionally, a new enum value for ergonomics.

## Schema - `factions.json v3`

```json
{
  "schema": "tinyassets.game_factory.factions.v3",
  "schema_evolution": "v2 -> v3: added palette + audio_assets + movement_verb + hero_defaults per faction",
  "factions": [
    {
      "id": "verdant_choir",
      "display_name": "Verdant Choir",
      "direction": "forest, root, choral plant power",
      "no_gunpowder": false,
      "palette": {
        "primary": [0.30, 0.55, 0.25, 1.0],
        "secondary": [0.96, 0.91, 0.78, 1.0],
        "tertiary": [0.11, 0.23, 0.12, 1.0],
        "accent": [0.66, 0.82, 0.38, 1.0]
      },
      "material": {
        "metallic": 0.10,
        "roughness": 0.70
      },
      "movement_verb": {
        "verb_id": "VerdantRootVault",
        "tuning": {
          "LaunchImpulseForward": 850.0,
          "LaunchImpulseVertical": 450.0,
          "CooldownSeconds": 3.0,
          "MinSprintHeldSeconds": 0.15,
          "bRequireGroundedAtLaunch": true
        }
      },
      "audio_assets": {
        "weapon_fire": "Content/Audio/Verdant/SC_VerdantBowFire",
        "weapon_impact": "Content/Audio/Verdant/SC_VerdantArrowImpact",
        "footstep": "Content/Audio/Verdant/SC_VerdantFootstep",
        "hero_ambient_loop": "Content/Audio/Verdant/SC_ChoirHumLoop",
        "death": "Content/Audio/Verdant/SC_VerdantDeath"
      },
      "weapon_defaults": {
        "weapon_class": "VerdantThornsproutBow",
        "body_damage": 35.0,
        "head_damage": 80.0,
        "limb_damage": 22.0,
        "falloff_start_uu": 3000.0,
        "falloff_end_uu": 6000.0,
        "min_damage": 12.0,
        "quiver_capacity": 3,
        "fire_cycle_s": 1.2,
        "reload_s": 1.8,
        "projectile_speed": 8000.0
      },
      "hero_defaults": {
        "max_health": 350.0,
        "speed_multiplier": 1.15,
        "weapon_damage_multiplier": 1.3,
        "ability_one_cooldown_s": 12.0,
        "ultimate_cooldown_s": 60.0
      }
    },
    {
      "id": "kinwild_covenant",
      "same_structure": "different values"
    },
    {
      "id": "lenswright_compact",
      "same_structure": "different values"
    }
  ],
  "legal_distinctness": "These are original fantasy directions and should not copy protected units, names, art, lore, or UI from reference games.",
  "engine_enum_compat": [
    { "id": "verdant_choir", "enum_value": 1 },
    { "id": "kinwild_covenant", "enum_value": 2 },
    { "id": "lenswright_compact", "enum_value": 3 }
  ]
}
```

`engine_enum_compat` keeps the existing `EArchonFaction` enum working for any code that already passes an enum value. The registry resolves enum to `FName` and `FName` to enum.

## Public surface - `UArchonFactionRegistry`

```cpp
USTRUCT(BlueprintType)
struct FArchonFactionPaletteRecord
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Faction")
    FLinearColor Primary = FLinearColor::White;

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Faction")
    FLinearColor Secondary = FLinearColor::White;

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Faction")
    FLinearColor Tertiary = FLinearColor::Black;

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Faction")
    FLinearColor Accent = FLinearColor::White;
};

USTRUCT(BlueprintType)
struct FArchonFactionMaterialRecord
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Faction")
    float Metallic = 0.1f;

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Faction")
    float Roughness = 0.7f;
};

USTRUCT(BlueprintType)
struct FArchonFactionRecord
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FName Id;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FText DisplayName;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FString Direction;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    bool bNoGunpowder = false;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FArchonFactionPaletteRecord Palette;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FArchonFactionMaterialRecord Material;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FName MovementVerbId;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FArchonFactionMovementTuning MovementTuning;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    TMap<FName, FSoftObjectPath> AudioAssetPaths;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FArchonWeaponStats WeaponDefaults;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FArchonWeaponDamageProfile WeaponDamageProfile;

    UPROPERTY(BlueprintReadOnly, Category = "Archon|Faction")
    FArchonHeroLockedStats HeroDefaults;
};

UCLASS()
class ARCHONFACTORYCANARY_API UArchonFactionRegistry : public UEngineSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;

    UFUNCTION(BlueprintPure, Category = "Archon|Faction")
    static UArchonFactionRegistry* Get();

    UFUNCTION(BlueprintPure, Category = "Archon|Faction")
    bool GetFactionByName(FName Id, FArchonFactionRecord& OutRecord) const;

    UFUNCTION(BlueprintPure, Category = "Archon|Faction")
    bool GetFactionByEnum(EArchonFaction Faction, FArchonFactionRecord& OutRecord) const;

    UFUNCTION(BlueprintPure, Category = "Archon|Faction")
    FName ResolveEnumToName(EArchonFaction Faction) const;

    UFUNCTION(BlueprintPure, Category = "Archon|Faction")
    EArchonFaction ResolveNameToEnum(FName Id) const;

    UFUNCTION(BlueprintPure, Category = "Archon|Faction")
    TArray<FName> GetAllFactionIds() const;

    UFUNCTION(BlueprintCallable, Category = "Archon|Faction")
    bool ReloadFromDisk();

    UFUNCTION(BlueprintCallable, Category = "Archon|Faction")
    bool LoadFromJsonString(const FString& JsonContent);

private:
    TMap<FName, FArchonFactionRecord> Registry;
    TMap<EArchonFaction, FName> EnumToName;
    TMap<FName, EArchonFaction> NameToEnum;
};
```

## Files

- `Source/.../ArchonFactionRegistry.h/.cpp` - new `UEngineSubsystem`
- `FactoryContracts/factions.json` - v3 schema with palette/material/audio/weapon/hero per-faction
- `Source/.../ArchonFactionMovementPolicyLibrary.cpp` - modify `GetMovementVerbForFaction` to delegate to registry
- `Source/.../ArchonFactionMaterialBuilder.h/.cpp` (planned art polish slice) - implement via registry from day one
- `Source/.../ArchonFactionAudioLibrary.h/.cpp` (planned audio polish slice) - implement via registry from day one
- `Source/.../ArchonHeroComponent.cpp` (planned hero implementation) - read locked-stats defaults from registry
- `Source/.../Tests/ArchonFactionRegistryTests.cpp` - new test file

## Named tests

| Test | Expected outcome |
|---|---|
| `ArchonFactory.FactionRegistry.LoadsAllThreeSplitrootFactions` | After `ReloadFromDisk`, registry has `verdant_choir`, `kinwild_covenant`, `lenswright_compact`. |
| `ArchonFactory.FactionRegistry.VerdantPaletteMatchesArtDirectionSpec` | `GetFactionByName(verdant_choir).Palette.Primary == FLinearColor(0.30, 0.55, 0.25, 1.0)`. |
| `ArchonFactory.FactionRegistry.LenswrightNoGunpowderFlagSet` | `GetFactionByName(lenswright_compact).bNoGunpowder == true`. Hill enforcement in data. |
| `ArchonFactory.FactionRegistry.VerdantNoGunpowderFalse` | Verdant and Kinwild have `bNoGunpowder = false`. |
| `ArchonFactory.FactionRegistry.VerdantMovementVerbIsRootVault` | `MovementVerbId == "VerdantRootVault"`. |
| `ArchonFactory.FactionRegistry.VerdantMovementTuningMatchesS4Contract` | `LaunchImpulseForward=850`, `LaunchImpulseVertical=450`, `CooldownSeconds=3.0`, `MinSprintHeldSeconds=0.15`. |
| `ArchonFactory.FactionRegistry.KinwildMovementTuningMatchesBoundLeap` | Per [[splitroot-kinwild-bound-leap-contract-2026-05-24]] values. |
| `ArchonFactory.FactionRegistry.EnumNameRoundTrip` | `ResolveNameToEnum(ResolveEnumToName(EArchonFaction::VerdantChoir)) == EArchonFaction::VerdantChoir`. |
| `ArchonFactory.FactionRegistry.UnknownFactionIdReturnsFalse` | `GetFactionByName("not_a_faction")` returns false. |
| `ArchonFactory.FactionRegistry.ReloadFromMalformedJsonRejected` | `LoadFromJsonString("{not valid")` returns false; existing registry unchanged. |
| `ArchonFactory.FactionRegistry.ReloadFromSyntheticGameJson` | Load a synthetic JSON with 4 hypothetical factions; registry populates; original registry can be restored via `ReloadFromDisk`. Proves remix surface. |
| `ArchonFactory.FactionRegistry.HeroDefaultsConsistentAcrossSplitrootFactions` | All three SPLITROOT factions return identical hero locked-stats defaults: `350/1.15/1.3/12/60`. Hill enforcement: paid heroes horizontal-only at faction level. |
| `ArchonFactory.FactionRegistry.WeaponDefaultProfileMatchesC1Spec` | Verdant: `35/80/22/12 + 3000/6000` falloff. Lenswright row was truncated in the source issue. |

## Import gap

The auto-filed issue ends with:

```text
_Source wiki body truncated at 12000 characters._
```

The original wiki page should be recovered before this plan is promoted from working draft to implementation authority. Until then, the missing tail most likely affects the complete named-test inventory and any detailed Lenswright/Kinwild faction values not shown above.

## Implementation guardrails

- Keep the C++ enum as compatibility only; JSON IDs are the canonical faction identity.
- Reject malformed JSON without mutating the active registry.
- Preserve enum-to-name and name-to-enum round trips for existing call sites.
- Make the synthetic multi-faction JSON test mandatory; it is the proof that a second canary does not need per-faction C++ edits.
- Treat `no_gunpowder` and horizontal hero defaults as data-enforced constraints, not comments in the art/audio plan.
