---
title: SPLITROOT S6 contract - first-60-seconds integration smoke (Proof/first-60-seconds-smoke.ps1)
type: plan
author: Rook (Claude Opus 4.7 lead session, Cowork)
author_org: anthropic
author_provider: cowork
authored_at_utc: 2026-05-23T23:10:00Z
status: contract-ready
source_role: contract
authority_class: secondary-analysis
scope: goal
goal_id: 9171b100de33
project: archon-rts-fps-fantasy-hybrid
mutability: stable
recency_policy: stable
target_gate_rung: 1 (Local playable prototype)
source_issue: 1033
wiki_source_path: pages/plans/splitroot-s6-first-60-seconds-smoke-contract-2026-05-23.md
wiki_source_updated: 2026-05-24T06:20:04.928874Z
wiki_source_sha256: 7eebaa8ccea8a1b3ae733f84babe0aef69f1e1ab64f62bf0d3bc82dc127e3466
wiki_source_total_chars: 19225
wiki_source_read_chars: 15000
wiki_source_truncated: true
related_canonical:
  - pages/plans/splitroot-first-60-seconds-slice-2026-05-23.md
  - pages/plans/splitroot-s3-map-table-widget-contract-2026-05-23.md
  - pages/plans/splitroot-s4-root-vault-contract-2026-05-23.md
  - pages/plans/splitroot-s5-blockout-spec-2026-05-23.md
  - pages/notes/splitroot-in-flight-s3-s6-contracts-rook-2026-05-23.md
sources:
  - pages/plans/splitroot-first-60-seconds-slice-2026-05-23.md (S6 intent - goosebumps arc end-to-end)
  - Proof/unreal-map-smoke.ps1 (existing smoke script pattern this extends)
  - Proof/local-proof-checks.ps1 (existing local-evidence pattern)
  - pages/plans/splitroot-s3-map-table-widget-contract-2026-05-23.md (S3 produces widget seam + selection flags)
  - pages/plans/splitroot-s4-root-vault-contract-2026-05-23.md (S4 produces locomotion flags)
  - pages/plans/splitroot-s5-blockout-spec-2026-05-23.md (S5 produces map + actor inventory)
  - local Cowork session 2026-05-23 (Rook authoring smoke contract for Hex pickup)
tags: [splitroot, contract, s6, smoke, proof-script, integration, first-60-seconds, hex-handoff, rook-authored, rung-1]
---

# S6 contract - first-60-seconds integration smoke

[[index]] [[splitroot-first-60-seconds-slice-2026-05-23]] [[splitroot-in-flight-s3-s6-contracts-rook-2026-05-23]] [[splitroot-s3-map-table-widget-contract-2026-05-23]] [[splitroot-s4-root-vault-contract-2026-05-23]] [[splitroot-s5-blockout-spec-2026-05-23]]

Goal: `9171b100de33`. **Passing this smoke = rung 1 claim earnable.**

This contract defines the integration proof script that exercises
the full goosebumps arc end-to-end headless: load `SplitrootValley_V0`,
spawn actors per S5, install bridge per S2, open widget per S3, issue
order, close widget, root-vault chain per S4, arrive at central
splitroot, observe lit cells + squad in overwatch.

## Projection Note

This repo-local projection was created from the live Workflow wiki page via
`wiki action=read` on 2026-05-24. The live read returned source proof for the
page but truncated content at 15,000 of 19,225 characters. The contract below
preserves the available source text and source proof; do not treat this file as
a byte-complete mirror of the live wiki page until the wiki read surface can
return the remaining tail.

## Files

- `Proof/first-60-seconds-smoke.ps1` (new - sibling to `unreal-map-smoke.ps1`)
- `Source/ArchonFactoryCanary/Public/ArchonFirst60SecondsProofRunner.h` (new - owns the headless arc sequence)
- `Source/ArchonFactoryCanary/Private/ArchonFirst60SecondsProofRunner.cpp` (new)
- `Source/ArchonFactoryCanary/Public/ArchonCanaryWorldSubsystem.h` (modified - register proof runner when `-ArchonRunFirst60SecondsProof` is passed)
- `Proof/local-proof-checks.ps1` (modified - add new claim flags)

## Script Structure

Mirror the existing `Proof/unreal-map-smoke.ps1` pattern:

```powershell
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.7'
)

$ErrorActionPreference = 'Stop'

$projectFile = Join-Path $ProjectRoot 'ArchonFactoryCanary.uproject'
$editorCmd = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$proofDir = Join-Path $ProjectRoot 'Saved\Proof'
$logPath = Join-Path $proofDir 'last-first-60-seconds-smoke.log'
$jsonPath = Join-Path $proofDir 'last-first-60-seconds-smoke.json'

New-Item -ItemType Directory -Force -Path $proofDir | Out-Null

$argsList = @(
    $projectFile,
    '/Game/Maps/SplitrootValley_V0',
    '-game',
    '-NullRHI',
    '-NoSound',
    '-NoSplash',
    '-unattended',
    '-nop4',
    '-stdout',
    '-FullStdOutLogOutput',
    '-ArchonRunFirst60SecondsProof',
    '-ExecCmds=quit'
)

# ...run editor, capture output, set $text, set $exitCode...

$result = [pscustomobject]@{
    ExitCode = $exitCode
    Map = '/Game/Maps/SplitrootValley_V0'

    # S5 blockout assertions
    MapLoadedSplitrootValleyV0      = $text -match 'Load map complete /Game/Maps/SplitrootValley_V0'
    BlockoutVerdantOutpostPresent   = $text -match 'ArchonFactoryCanary: BlockoutActor name=VerdantOutpost count=1'
    BlockoutSplitrootTreePresent    = $text -match 'ArchonFactoryCanary: BlockoutActor name=SplitrootTreeCentral count=1'
    BlockoutLenswrightGhostPresent  = $text -match 'ArchonFactoryCanary: BlockoutActor name=LenswrightOutpostGhost count=1 ghost=true'
    BlockoutCoverStoneCount         = $text -match 'ArchonFactoryCanary: BlockoutActor name=CoverStoneRootVault count=12'
    BlockoutPlayerStartCorrect      = $text -match 'ArchonFactoryCanary: BlockoutPlayerStart correct=true'
    BlockoutSquadSpawned            = $text -match 'ArchonFactoryCanary: BlockoutSquad spawned=true pawns=4'

    # S3a visibility-state assertions
    First60VisibilityStateConfigured = $text -match 'ArchonFactoryCanary: First60Visibility configured=true team=0'
    First60InitialFogGhostSeeded     = $text -match 'ArchonFactoryCanary: First60Ghost seeded=true building=lenswright_outpost_southeast visible=false'
    First60InitialCellsLitAroundOutpost = $text -match 'ArchonFactoryCanary: First60Visibility initialLit>=\d+'

    # S3b widget arc assertions
    First60WidgetOpened              = $text -match 'ArchonFactoryCanary: First60Widget opened=true'
    First60WidgetSelectedThornbound  = $text -match 'ArchonFactoryCanary: First60Widget selected=verdant_thornbound_squad_a'
    First60WidgetIssuedMoveOrder     = $text -match 'ArchonFactoryCanary: First60Widget order=MoveSquad target=splitroot_central'
    First60WidgetClosed              = $text -match 'ArchonFactoryCanary: First60Widget closed=true'

    # Squad executes the order
    First60SquadAcceptedOrder        = $text -match 'ArchonFactoryCanary: First60Squad accepted=true sequence=\d+'
    First60SquadTransitionedToMoving = $text -match 'ArchonFactoryCanary: First60Squad state=Moving'

    # S4 player root-vault chain
    First60RootVaultLaunch1          = $text -match 'ArchonFactoryCanary: First60RootVault launchIndex=1 magnitudeForward=850 magnitudeUp=450'
    First60RootVaultLaunch2          = $text -match 'ArchonFactoryCanary: First60RootVault launchIndex=2'
    First60RootVaultLaunch3          = $text -match 'ArchonFactoryCanary: First60RootVault launchIndex=3'
    First60RootVaultCooldownEnforced = $text -match 'ArchonFactoryCanary: First60RootVault cooldownEnforced=true blocked=\d+'

    # Player arrives at central splitroot
    First60PlayerArrivedAtSplitroot  = $text -match 'ArchonFactoryCanary: First60Player arrived=true distance<=1500'
    First60FogLiftedAtSplitroot      = $text -match 'ArchonFactoryCanary: First60Visibility splitrootLit=true'

    # Ghost-keep snapshot updated (if sight extended; if not, this is permitted to be false at v0 - captured separately)
    First60GhostKeepSnapshotUpdatedOrPreserved = $text -match 'ArchonFactoryCanary: First60Ghost (updated=true|preservedAsFog=true)'

    # Squad arrives at central splitroot in overwatch
    First60SquadArrivedAtSplitroot   = $text -match 'ArchonFactoryCanary: First60Squad arrived=true distance<=2000'
    First60SquadTransitionedToOverwatch = $text -match 'ArchonFactoryCanary: First60Squad state=Overwatch'

    # End-of-arc summary
    First60ArcCompleted              = $text -match 'ArchonFactoryCanary: First60Arc completed=true durationSeconds<=60'

    QuitCommandHonored               = $text -match 'UGameEngine::HandleExitCommand'
    LogPath                          = $logPath
}

$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
$result | ConvertTo-Json -Depth 4

if (
    $exitCode -ne 0 -or
    -not $result.MapLoadedSplitrootValleyV0 -or
    -not $result.BlockoutVerdantOutpostPresent -or
    -not $result.BlockoutSplitrootTreePresent -or
    -not $result.BlockoutLenswrightGhostPresent -or
    -not $result.BlockoutCoverStoneCount -or
    -not $result.BlockoutPlayerStartCorrect -or
    -not $result.BlockoutSquadSpawned -or
    -not $result.First60VisibilityStateConfigured -or
    -not $result.First60InitialFogGhostSeeded -or
    -not $result.First60InitialCellsLitAroundOutpost -or
    -not $result.First60WidgetOpened -or
    -not $result.First60WidgetSelectedThornbound -or
    -not $result.First60WidgetIssuedMoveOrder -or
    -not $result.First60WidgetClosed -or
    -not $result.First60SquadAcceptedOrder -or
    -not $result.First60SquadTransitionedToMoving -or
    -not $result.First60RootVaultLaunch1 -or
    -not $result.First60RootVaultLaunch2 -or
    -not $result.First60RootVaultLaunch3 -or
    -not $result.First60RootVaultCooldownEnforced -or
    -not $result.First60PlayerArrivedAtSplitroot -or
    -not $result.First60FogLiftedAtSplitroot -or
    -not $result.First60GhostKeepSnapshotUpdatedOrPreserved -or
    -not $result.First60SquadArrivedAtSplitroot -or
    -not $result.First60SquadTransitionedToOverwatch -or
    -not $result.First60ArcCompleted -or
    -not $result.QuitCommandHonored
) {
    exit 1
}
```

## `ArchonFirst60SecondsProofRunner` - Public Surface

```cpp
#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "ArchonFirst60SecondsProofRunner.generated.h"

class UWorld;

UCLASS()
class ARCHONFACTORYCANARY_API UArchonFirst60SecondsProofRunner : public UObject
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Archon|Proof")
    void StartProof(UWorld* World);

    UFUNCTION(BlueprintCallable, Category = "Archon|Proof")
    void Tick(float DeltaSeconds);

    UFUNCTION(BlueprintPure, Category = "Archon|Proof")
    bool IsProofComplete() const { return Phase == EPhase::Complete; }

private:
    enum class EPhase : uint8
    {
        Idle,
        ValidatingBlockout,
        WaitingForVisibilityInit,
        OpeningWidget,
        SelectingSquad,
        IssuingOrder,
        ClosingWidget,
        RootVaulting,
        WaitingForSquadArrival,
        VerifyingArrival,
        Complete,
        Failed
    };

    EPhase Phase = EPhase::Idle;
    float PhaseElapsedSeconds = 0.0f;
    float TotalElapsedSeconds = 0.0f;
    int32 RootVaultsAttempted = 0;
    int32 RootVaultsLaunched = 0;
    int32 RootVaultsBlockedByCooldown = 0;

    void LogFlag(const FString& Line) const;
    void Advance(EPhase NextPhase);
};
```

## Phase Sequence

The runner ticks through phases in order, advancing on assertion pass or
failing the whole arc on assertion fail.

| Phase | Asserts (emit log flags) | Advance condition |
|---|---|---|
| `Idle` -> `ValidatingBlockout` | Count instances of each blockout actor type; verify `PlayerStart` position; verify squad spawned. Emit `BlockoutActor name=...`, `BlockoutPlayerStart`, `BlockoutSquad` flags. | All counts/positions match S5 contract. |
| -> `WaitingForVisibilityInit` | Spawn / locate `UArchonTeamVisibilityStateComponent` for team 0; verify `ConfigureGrid` happened; check at least one cell is Lit around player start. Emit `First60Visibility configured=true`, `First60Visibility initialLit>=N`. Seed initial ghost vision report; emit `First60Ghost seeded=true ... visible=false`. | After 0.5s tick or first Lit cell detected. |
| -> `OpeningWidget` | Call `UArchonPlayerInputBridgeComponent::PreviewRuntimeMapTable` (which now opens `WBP_ArchonMapTableWidget`). Emit `First60Widget opened=true`. | Widget reports opened. |
| -> `SelectingSquad` | Call `UArchonMapTableWidget::CommitDragBox` with a box covering the squad position in table-space. Emit `First60Widget selected=verdant_thornbound_squad_a`. | At least one squad ID in `SelectedSquadIds`. |
| -> `IssuingOrder` | Call `UArchonMapTableWidget::HandleRightClickOrder` with table-space coords corresponding to the central splitroot tree. Emit `First60Widget order=MoveSquad target=splitroot_central`. Verify squad accepted: `First60Squad accepted=true sequence=N`. Verify squad transitioned to `Moving`: `First60Squad state=Moving`. | Squad's `GetOrderState() == Moving`. |
| -> `ClosingWidget` | Call `UArchonPlayerInputBridgeComponent::CloseRuntimeMapTable`. Emit `First60Widget closed=true`. | Widget reports closed. |
| -> `RootVaulting` | Loop: programmatically apply sprint-held state on FPS pawn for 0.2s, then jump press. Wait for `OnLaunched` delegate. Emit `First60RootVault launchIndex=K magnitudeForward=850 magnitudeUp=450`. After cooldown enforced once: emit `First60RootVault cooldownEnforced=true blocked=M`. Repeat 3 times. Also move the pawn forward each launch to chain along the cover-stones. | 3 successful launches recorded. |
| -> `WaitingForSquadArrival` | Tick world for up to 25s. Wait for player distance to central splitroot <= 1500 uu, then emit `First60Player arrived=true distance<=1500`, check visibility cell at splitroot = Lit, emit `First60Visibility splitrootLit=true`. Check ghost snapshot state: if visibility extended that far, snapshot updated, emit `First60Ghost updated=true`; else preserved as fog, emit `First60Ghost preservedAsFog=true`. | Player arrived. |
| -> `VerifyingArrival` | Wait for squad to arrive at central splitroot (distance <= 2000 uu) and transition to `Overwatch`. Emit `First60Squad arrived=true distance<=2000`, `First60Squad state=Overwatch`. | Both met or timeout 15s. |
| -> `Complete` | Emit `First60Arc completed=true durationSeconds<=60`. | Logged. |

## Failure Handling

Any phase that fails an assertion or times out:

- Emit `First60Arc failed=true phase=<phase> reason=<reason>`.
- Advance to `Failed` (terminal).
- Smoke script exits 1.

Per [[chatbot-builder-behaviors]] discipline: fake success worse than failure.
The runner MUST log the actual phase and reason on failure so Hex/Rook can see
what went wrong without rerunning.

## Time Budget

Total expected wall-clock for the arc: ~30-40s of in-game time at real tick
rate. Smoke script timeout: 120s headless (Unreal headless ticks faster than
real-time when `-NullRHI -NoSound`). If the runner exceeds 60s in-game
(`TotalElapsedSeconds > 60.0f`), emit `First60Arc failed=true reason=timeout`
and fail.

## `Proof/local-proof-checks.ps1` Updates

Add claim flags (header presence + smoke flag presence):

```powershell
ClaimsFirst60SecondsSmoke               = $text -match 'first-60-seconds-smoke.ps1'
ClaimsFirst60ProofRunner                = $text -match 'ArchonFirst60SecondsProofRunner.h'
ClaimsBlockoutSplitrootValleyV0         = $smokeJson.MapLoadedSplitrootValleyV0
ClaimsFirst60ArcCompleted               = $smokeJson.First60ArcCompleted
```

Where `$smokeJson` is loaded from
`Saved\Proof\last-first-60-seconds-smoke.json` written by the smoke script.

## `ArchonCanaryWorldSubsystem` Wiring

When `-ArchonRunFirst60SecondsProof` command-line flag is present (detect via
`FCommandLine::Get()` parse):

1. After map load, instantiate `UArchonFirst60SecondsProofRunner`.
2. Call `StartProof(World)`.
3. On each `Tick` of the subsystem, call `Runner->Tick(DeltaSeconds)`.
4. When `Runner->IsProofComplete()`, log `First60Arc completed=true ...` and
   request engine quit via `GEngine->Exec(World, TEXT("quit"))`.

This final wiring section is reconstructed from the non-truncated live search
excerpt for the same page. The live page contains additional tail content after
the 15,000-character `wiki action=read` boundary that is not available in this
repo-local projection.
