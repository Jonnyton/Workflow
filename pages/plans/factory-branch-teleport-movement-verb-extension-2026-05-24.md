---
title: Factory branch teleport movement verb extension
type: plan
status: working-draft
source_issue: 1051
request_id: WIKI-DESIGN
wiki_source_path: pages/plans/factory-branch-teleport-movement-verb-extension-2026-05-24.md
filed: 2026-05-24
---

# Factory branch - teleport movement verb extension

[[index]] [[factory-branch-remix-proof-stellar-front-2026-05-24]] [[splitroot-s4-root-vault-contract-2026-05-23]] [[splitroot-kinwild-bound-leap-contract-2026-05-24]]

Goal: `9171b100de33` (source label; `python scripts/check_primitive_exists.py sha 9171b100de33` did not resolve it as a commit in this checkout on 2026-05-24). Scope: **factory branch substrate**, sets up sci-fi phase-step and fantasy spell-blink mechanics.

## What the STELLAR FRONT audit surfaced

Per [[factory-branch-remix-proof-stellar-front-2026-05-24]] section "Movement substrate":

> Phase-step needs a TELEPORT path the current launch impulse doesn't have - that's a SUBSTRATE EXTENSION, not a fail.

Current `UArchonFactionMovementComponent` applies impulse via `LaunchCharacter(Impulse, false, false)`. That is a velocity-based movement primitive: suitable for jump, jetpack, grav-slide, root-vault, bound-leap, and pressure-thrust. Teleport mechanics such as Hollow Order phase-step, future fantasy spell-blink, or ARMOR-cleared force-skip need a location-based primitive: `SetActorLocation(Target, sweep, hit)`.

This contract extends the substrate to support both primitives through a small movement-kind flag in the decision struct and a switch in the component. Existing launch verbs remain launch by default.

## Target files

- `Source/ArchonFactoryCanary/Public/ArchonFactionTypes.h`
- `Source/ArchonFactoryCanary/Public/ArchonFactionMovementPolicyLibrary.h`
- `Source/ArchonFactoryCanary/Private/ArchonFactionMovementPolicyLibrary.cpp`
- `Source/ArchonFactoryCanary/Public/ArchonFactionMovementComponent.h`
- `Source/ArchonFactoryCanary/Private/ArchonFactionMovementComponent.cpp`
- `Source/ArchonFactoryCanary/Private/Tests/ArchonFactionMovementPolicyTests.cpp`

These files are not present in the Workflow checkout that captured this plan. This page is therefore a durable implementation contract, not a completed code patch.

## Schema additions

Add a movement-kind enum:

```cpp
UENUM(BlueprintType)
enum class EArchonFactionMovementKind : uint8
{
    Launch UMETA(DisplayName = "Launch (impulse-based)"),
    Teleport UMETA(DisplayName = "Teleport (location-based)")
};
```

Extend `FArchonFactionMovementDecision`:

```cpp
UPROPERTY(BlueprintReadOnly, Category = "Archon|Locomotion")
EArchonFactionMovementKind MovementKind = EArchonFactionMovementKind::Launch;

UPROPERTY(BlueprintReadOnly, Category = "Archon|Locomotion")
FVector TeleportRelativeOffset = FVector::ZeroVector;

UPROPERTY(BlueprintReadOnly, Category = "Archon|Locomotion")
bool bTeleportSweepDuringMove = true;
```

Extend `FArchonFactionMovementTuning`:

```cpp
UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "Archon|Locomotion")
EArchonFactionMovementKind PreferredMovementKind = EArchonFactionMovementKind::Launch;

UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "Archon|Locomotion")
float TeleportDistance = 600.0f;

UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "Archon|Locomotion")
bool bTeleportAllowsThroughBlockers = false;
```

## Policy library extension

Add a teleport evaluator beside `EvaluateLaunch`:

```cpp
UFUNCTION(BlueprintCallable, Category = "Archon|Locomotion")
static FArchonFactionMovementDecision EvaluateTeleport(
    EArchonFaction Faction,
    const FArchonFactionMovementInputState& Input,
    const FArchonFactionMovementCooldown& CurrentCooldown,
    const FArchonFactionMovementTuning& Tuning);
```

Add a pure relative-offset helper:

```cpp
UFUNCTION(BlueprintPure, Category = "Archon|Locomotion")
static FVector ComputeTeleportRelativeOffset(
    const FVector& PawnForward,
    float TeleportDistance);
```

`ComputeTeleportRelativeOffset` should produce horizontal phase-step semantics: normalize the pawn-forward direction, clear Z, and multiply by `TeleportDistance`. The result always has `Z = 0`.

## Decision rules

`EvaluateTeleport` uses the same safety gates as `EvaluateLaunch`, plus a movement-kind check:

1. The faction must have a movement verb that maps to teleport.
2. `Tuning.PreferredMovementKind == EArchonFactionMovementKind::Teleport`.
3. `IsCooldownReady(CurrentCooldown)`.
4. `Input.bSprintHeld && Input.SprintHeldSeconds >= Tuning.MinSprintHeldSeconds`.
5. `Input.bJumpPressedThisFrame`.
6. If configured, `Input.bGrounded` per `Tuning.bRequireGroundedAtLaunch`.

On success, the decision should set:

- `MovementKind = EArchonFactionMovementKind::Teleport`
- `bShouldLaunch = true` until the existing decision field can be renamed to movement-neutral language
- `TeleportRelativeOffset = ComputeTeleportRelativeOffset(PawnForward, Tuning.TeleportDistance)`
- `ForwardImpulse = 0.0f`
- `VerticalImpulse = 0.0f`
- `NewCooldown = full cooldown`
- `VerbTriggered =` the faction's teleport verb

`EvaluateLaunch` should reject teleport tuning by returning `bShouldLaunch = false` when `Tuning.PreferredMovementKind == EArchonFactionMovementKind::Teleport`.

## Component behavior

In `UArchonFactionMovementComponent::TickComponent`, route by `PreferredMovementKind`:

```cpp
FArchonFactionMovementDecision Decision;
if (Tuning.PreferredMovementKind == EArchonFactionMovementKind::Teleport)
{
    Decision = UArchonFactionMovementPolicyLibrary::EvaluateTeleport(
        Faction, Input, Cooldown, Tuning);
}
else
{
    Decision = UArchonFactionMovementPolicyLibrary::EvaluateLaunch(
        Faction, Input, Cooldown, Tuning);
}
```

When the decision fires, switch on `Decision.MovementKind`:

```cpp
if (Decision.MovementKind == EArchonFactionMovementKind::Teleport)
{
    const FVector CurrentLocation = OwningCharacter->GetActorLocation();
    const FVector TargetLocation = CurrentLocation + Decision.TeleportRelativeOffset;

    FHitResult HitResult;
    OwningCharacter->SetActorLocation(
        TargetLocation,
        Decision.bTeleportSweepDuringMove,
        &HitResult,
        ETeleportType::TeleportPhysics);
}
else
{
    const FVector Direction = ComputeForwardImpulseDirection();
    const FVector Impulse =
        Direction * Decision.ForwardImpulse + FVector(0, 0, Decision.VerticalImpulse);
    OwningCharacter->LaunchCharacter(Impulse, false, false);
}
```

With `bTeleportSweepDuringMove = true` and `bTeleportAllowsThroughBlockers = false`, phase-step stops at blockers instead of blinking through walls.

## STELLAR FRONT Hollow Order example

```cpp
FArchonFactionMovementTuning HollowOrderTuning;
HollowOrderTuning.PreferredMovementKind = EArchonFactionMovementKind::Teleport;
HollowOrderTuning.TeleportDistance = 600.0f;
HollowOrderTuning.bTeleportAllowsThroughBlockers = false;
HollowOrderTuning.CooldownSeconds = 4.0f;
HollowOrderTuning.MinSprintHeldSeconds = 0.15f;
HollowOrderTuning.bRequireGroundedAtLaunch = false;
```

`GetMovementVerbForFaction(EArchonFaction::HollowOrder)` returns `EArchonFactionMovementVerb::HollowPhaseStep`. The component sees `MovementKind == Teleport` and uses `SetActorLocation` instead of `LaunchCharacter`. The input discipline remains the same; only the physics path changes.

## Required tests

| Test | Expected outcome |
|---|---|
| `ArchonFactory.Locomotion.TeleportTuningRequiresPreferredKindFlag` | Launch tuning returns launch-kind behavior; teleport tuning returns teleport-kind behavior for the same valid input. |
| `ArchonFactory.Locomotion.TeleportAcceptsSameGatesAsLaunch` | Valid sprint, sprint-window, jump, grounded, and cooldown input triggers teleport when tuning kind is teleport. |
| `ArchonFactory.Locomotion.TeleportRejectsOnCooldown` | Teleport tuning plus active cooldown returns `bShouldLaunch = false`. |
| `ArchonFactory.Locomotion.TeleportRejectsWithoutSprint` | Teleport keeps the same anti-accident sprint gate as launch. |
| `ArchonFactory.Locomotion.TeleportRelativeOffsetMatchesForwardDistance` | `ComputeTeleportRelativeOffset(FVector::ForwardVector, 600.0f) == FVector(600, 0, 0)`. |
| `ArchonFactory.Locomotion.TeleportPreservesZeroZ` | `ComputeTeleportRelativeOffset` always returns `Z = 0`. |
| `ArchonFactory.Locomotion.TeleportDecisionCarriesKindAndOffset` | Decision has teleport kind, non-zero teleport offset, and zero launch impulses. |
| `ArchonFactory.Locomotion.LaunchAndTeleportDecisionsAreMutuallyExclusive` | `EvaluateLaunch` with teleport tuning returns `bShouldLaunch = false`. |

## Backwards compatibility

- Existing Verdant root-vault remains launch because `PreferredMovementKind` defaults to `Launch`.
- Existing Kinwild bound-leap remains launch for the same reason.
- Existing locomotion tests should keep passing; the new tests cover only the teleport extension and launch/teleport mutual exclusion.

## Hills check

- **Factory branch is product:** This extension expands the substrate from impulse-only to impulse-or-location movement.
- **Faction verbs matter:** Teleport verbs differ from impulse-launch verbs at the decision and physics levels.
- **Standard FPS:** Swept teleport respects collision and avoids teleport-through-everything power creep by default.
- **Movement before content:** This is movement substrate, not content dressing.
- **Proof ladder sacred:** The contract names the eight tests required before the substrate is considered complete.

## Pickup notes

This is a small substrate contract. It should be implemented only in a checkout that actually contains the `Source/ArchonFactoryCanary` Unreal files listed above. In this Workflow checkout, the safe action is preserving the design page and avoiding synthetic code that cannot compile here.
