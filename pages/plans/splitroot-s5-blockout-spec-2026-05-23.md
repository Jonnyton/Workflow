---
title: S5 contract — SplitrootValley_V0 blockout
type: plan
status: working-draft
source_issue: 1032
wiki_source_path: pages/plans/splitroot-s5-blockout-spec-2026-05-23.md
---

# S5 contract — SplitrootValley_V0 blockout

[[index]] [[splitroot-first-60-seconds-slice-2026-05-23]] [[splitroot-in-flight-s3-s6-contracts-rook-2026-05-23]] [[splitroot-s3-map-table-widget-contract-2026-05-23]] [[splitroot-s4-root-vault-contract-2026-05-23]]

Goal: `9171b100de33`. Rung 1.

This contract defines the **first-60-seconds slice** of Splitroot
Valley — not the full v0 valley. The full v0 valley blockout
([[archon-fantasy-rts-fps-v0-map-blockout-2026-05-20]]) is much
larger; this slice carves out a small playable corner to prove the
goosebumps arc end-to-end.

## Goal of this map

A player loads, stands at the Verdant outpost, sees the central
splitroot tree ~200m east, sees a Lenswright ghost-keep silhouette
south-east in fog, drag-box-selects the four Thornbound, orders them
to the splitroot tree, closes the table, sprint-and-root-vaults
toward it across cover-stones placed at vault-distance spacing,
arrives first, fog lifts, squad arrives in overwatch, ghost-keep
state updates if sight extends that far.

## Files

- `Content/Maps/SplitrootValley_V0.umap` (new)
- `Content/Maps/SplitrootValley_V0_BuiltData.uasset` (build artifact)
- `Content/Blueprints/Verdant/BP_VerdantOutpost.uasset` (new — placeholder mesh actor)
- `Content/Blueprints/Lenswright/BP_LenswrightOutpost_Ghost.uasset` (new — placeholder mesh actor with ghost flag)
- `Content/Blueprints/Resource/BP_SplitrootTree_Central.uasset` (new — placeholder mesh actor)
- `Content/Blueprints/Cover/BP_CoverStone_RootVault.uasset` (new — placeholder mesh; multiple instances placed in map)

Placeholder meshes: Unreal Starter Content cubes/cylinders/rocks are
fine. Quixel-free trunks/stones better if quick to drop in. Material
swap to muted greens/browns ("mossy") for Verdant, dim brass/oxblood
for Lenswright ghost. No bespoke art at S5.

## World coordinates

Origin convention: world (0,0,0) is the center of the Verdant outpost
floor. +X = east (toward central splitroot). +Y = south (toward
Lenswright ghost-keep). +Z = up.

| Actor | World location (uu) | Notes |
|---|---|---|
| `PlayerStart` | (-300, 0, 100) | Just outside the outpost building, facing +X (east, toward splitroot tree). |
| `BP_VerdantOutpost` | (0, 0, 0) | Roughly 8m × 8m × 4m footprint (800x800x400 uu). Simple walled platform; the player spawns next to it. |
| `BP_SplitrootTree_Central` | (20000, 0, 0) | 200m east of outpost — the goosebumps destination. 6m × 6m × 12m placeholder (600x600x1200 uu) tree trunk. |
| AI squad start (4 pawns) | (-150, 400, 100), (-150, 480, 100), (-150, 560, 100), (-150, 640, 100) | Parade-rest line south of the outpost, facing +X. Spawn via `UArchonCanaryWorldSubsystem` extension. |
| `BP_LenswrightOutpost_Ghost` | (10000, 12000, 0) | 100m east + 120m south of outpost. ~6m × 6m × 6m brass-oxblood silhouette. Has `bIsGhost=true`. |
| Cover stones (root-vault path) | see below | A breadcrumb line of cover-stones from outpost to splitroot tree. |

### Cover-stone placement (root-vault breadcrumb)

S4 root-vault covers ~15m per launch from a sprinting start, with 3s
cooldown. Place 12 cover-stones from outpost to central splitroot at
~1700 uu spacing (≈17m, just past the sweet-spot) so the player can
chain three or four vaults before reaching the tree. Stones offer
vault take-off framing without forcing a strict path — flank routes
around them remain open.

| Stone # | World location (uu) | Footprint (uu) |
|---|---|---|
| 1 | (1700, 0, 0) | 200x200x150 |
| 2 | (3400, 0, 0) | 200x200x150 |
| 3 | (5100, 0, 0) | 200x200x150 |
| 4 | (6800, 0, 0) | 200x200x150 |
| 5 | (8500, 0, 0) | 200x200x150 |
| 6 | (10200, 0, 0) | 200x200x150 |
| 7 | (11900, 0, 0) | 200x200x150 |
| 8 | (13600, 0, 0) | 200x200x150 |
| 9 | (15300, 0, 0) | 200x200x150 |
| 10 | (17000, 0, 0) | 200x200x150 |
| 11 | (18700, 0, 0) | 200x200x150 |
| 12 | (19500, -800, 0) | 300x300x200 (larger; pre-tree approach) |

(Two-third of the stones can be auto-placed via a small editor utility
or a construction script on a `BP_CoverStoneRow` actor — Hex's call.)

## Bounds for S3 widget

`UArchonMapTableWidget::ConfigureWorldRect` reads:

- `WorldOrigin = FVector(-2000.0f, -2000.0f, 0.0f)`
- `WorldExtents = FVector(24000.0f, 16000.0f, 0.0f)`

This frames the playable corner with a small margin around all
relevant actors. The S3 visibility grid (`75 × 50 cells × 400uu`) at
those same anchor coords covers exactly this rect.

## `BP_VerdantOutpost` — public surface

```cpp
// Header (if pulled native; otherwise Blueprint variables)
UPROPERTY(EditAnywhere, BlueprintReadWrite)
int32 TeamId = 0;  // v0 Verdant team

UPROPERTY(EditAnywhere, BlueprintReadWrite)
float VisionRadius = 2400.0f;  // 24m sight from outpost (per fog decision)

UPROPERTY(EditAnywhere, BlueprintReadWrite)
FName BuildingId = TEXT("verdant_outpost_west");
```

On `BeginPlay`: register as a visibility source on the team-0
`UArchonTeamVisibilityStateComponent` if one exists in the world.

## `BP_SplitrootTree_Central` — public surface

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite)
FName ResourceNodeId = TEXT("central_splitroot");

UPROPERTY(EditAnywhere, BlueprintReadWrite)
int32 ControllingTeamId = INDEX_NONE;  // unowned at v0; capture mechanics deferred
```

No capture logic at v0. The actor exists so the widget can target it
and the squad/player can arrive at a meaningful spot.

## `BP_LenswrightOutpost_Ghost` — public surface

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite)
int32 OwnerTeamId = 1;  // notional Lenswright team

UPROPERTY(EditAnywhere, BlueprintReadWrite)
float VisionRadius = 0.0f;  // ghost contributes no sight (it's not really there from the team-0 perspective)

UPROPERTY(EditAnywhere, BlueprintReadWrite)
FName BuildingId = TEXT("lenswright_outpost_southeast");

UPROPERTY(EditAnywhere, BlueprintReadWrite)
bool bIsGhost = true;
```

On `BeginPlay` (server): submit one initial `FArchonBuildingVisionReport`
to team-0's visibility state with `bCurrentlyVisible = false` and
`ObservedState = "intact"`. This seeds the snapshot so the team-0
widget renders the ghost from the start of the match. Mechanics
permitting later: when team-0 sight reaches the ghost-keep location,
the next vision report flips `bCurrentlyVisible=true` and the snapshot
updates to whatever the live Lenswright state actually is (at v0:
just the same placeholder mesh; the visual demonstration is
"snapshot updated" rather than "real change observed").

## `BP_CoverStone_RootVault` — public surface

Simple static-mesh actor. No special components. Footprint placement
is the contract; no logic.

## Lighting

- Single directional light, low sun angle (sun pitch ≈ -30°, yaw ≈ 30° for warm late-afternoon).
- Skylight with default sky cubemap.
- Lighting build: production preset (low-quality bake acceptable at v0; visual feel deferred to polish slice).
- No dynamic time-of-day, no fog particles beyond default exponential height fog.
- Post-process volume: default, slight bloom + tonemap.

## Performance constraints

This slice should run smoothly headless on the smoke script and in
editor PIE. No demands beyond "don't blow up". The cover-stone count
(12 instances of a 200x200 mesh) plus three building actors is
trivial.

## Named tests / smoke assertions

These tests are mostly map-load assertions, no policy library needed.
Add to `Proof/unreal-map-smoke.ps1`:

| Assertion | Smoke flag |
|---|---|
| Map `SplitrootValley_V0` loads in PIE without error | `MapLoadedSplitrootValleyV0=true` |
| Exactly one `BP_VerdantOutpost` actor present | `BlockoutVerdantOutpostPresent=true` |
| Exactly one `BP_SplitrootTree_Central` present | `BlockoutSplitrootTreePresent=true` |
| Exactly one `BP_LenswrightOutpost_Ghost` present with `bIsGhost=true` | `BlockoutLenswrightGhostPresent=true` |
| Exactly 12 `BP_CoverStone_RootVault` actors present | `BlockoutCoverStoneCount=12` |
| Player start at expected location ± 5uu | `BlockoutPlayerStartCorrect=true` |
| AI squad spawns 4 pawns at parade-rest line | `BlockoutSquadSpawned=true` |

`Proof/local-proof-checks.ps1` parses claim flags:
- `ClaimsBlockoutSplitrootValleyV0=true`

## What's out of scope for S5

Deferred:

- The full v0 valley blockout from [[archon-fantasy-rts-fps-v0-map-blockout-2026-05-20]] — multiple lanes, second resource nodes, mid-map landmarks, all-three-faction footholds. This is just the **first 60 seconds corner**.
- Real Verdant/Lenswright art. Placeholder meshes + tinted materials only.
- Audio environments (wind, ambience).
- Foliage scatter beyond a few placeholder bramble decals at root-vault take-off points (optional — purely visual).
- Navmesh tuning beyond Unreal defaults (the AI squad pathfinds straight lines for now).
- Skybox replacement.
- Day/night cycle.
- Mid-map control points or capture rings.

## Hills check

- **Movement before content**: ✓ The geometry is *for* the root-vault chain, not decoration.
- **Faction verbs matter**: ✓ Cover-stones spaced for Verdant root-vault range specifically; later faction slices will need new spacing patterns for Kinwild bound-leap and Lenswright pressure-thrust.
- **Standard Archon**: ✓ Map exposes one outpost, four squad units at parade rest, one resource node — standard RTS spawn-and-rally feel.
- **Lenswright no gunpowder**: ✓ Ghost-keep is a brass-oxblood silhouette; no muzzle flash, no powder smoke implied.
- **Factory branch**: The actor BPs (`BP_VerdantOutpost`, `BP_LenswrightOutpost_Ghost`) are remixable — future games swap meshes/team-id without touching the blockout-load logic. ✓
- **Proof ladder**: Smoke verifies actor presence + counts + flags. Feel of the corridor is **NOT claimed from automation**; manual playtest required. ✓

## Hex pickup

1. Create `Content/Maps/SplitrootValley_V0.umap` (new level, default mode `AArchonCanaryGameMode` if it exists, else default game mode set in `DefaultEngine.ini`).
2. Create the four BP actor classes under `Content/Blueprints/`. Stub mesh placeholders.
3. Place actors per the world coordinate table.
4. Extend `UArchonCanaryWorldSubsystem` (or the level's level-script BP) to spawn the four-pawn AI squad at parade-rest positions on map load.
5. Wire `BP_VerdantOutpost::BeginPlay` to register as a visibility source on team-0 (depends on S3a `UArchonTeamVisibilityStateComponent` being available).
6. Wire `BP_LenswrightOutpost_Ghost::BeginPlay` to submit the initial ghost vision report (depends on S3a).
7. Extend `Proof/unreal-map-smoke.ps1` to load `SplitrootValley_V0` instead of (or as a sibling case to) `Lvl_FirstPerson`; assert the seven smoke flags.
8. Update `Proof/local-proof-checks.ps1` with `ClaimsBlockoutSplitrootValleyV0=true`.
9. Draft proof note `pages/notes/splitroot-s5-blockout-proof-<date>.md` with smoke flags + a screenshot of the editor viewport (since this slice is mostly visual). Include `sources:` in frontmatter.
10. Cross-review handoff: Rook will read the proof note + screenshot and look for (a) cover-stones at correct spacing, (b) the ghost-keep visible in the team-0 widget through fog, (c) any drift from the world-coord table.

S5 has a hard dependency on S3a (`UArchonTeamVisibilityStateComponent`)
for the visibility-source wiring. If Hex implements S5 before S3a, the
`BP_VerdantOutpost::BeginPlay` registration step is a stub
(comment-out + TODO). Stub-then-fill is fine; proof note must call out
the stub.

— Rook (Claude Opus 4.7, Cowork)
