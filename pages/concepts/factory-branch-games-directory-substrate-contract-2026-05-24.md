---
title: Factory Branch Games Directory Substrate Contract
type: concept
status: proposed
created: 2026-05-24
source_issue: 1048
wiki_source_path: pages/concepts/factory-branch-games-directory-substrate-contract-2026-05-24.md
tags: [factory-branch, canary, games-directory, substrate, unreal]
---

# Factory Branch - Games Directory Substrate Contract

## Purpose

This page records the target physical contract for the factory branch after it
moves from a single top-level canary layout to a multi-canary
`games/<gameName>/` layout. It is a project-design record for the external
`archon-rts-fps-factory` substrate, not an instruction to restructure this
Workflow repository.

The contract exists because the factory substrate is intended to spawn more
than one playable canary. A second canary, such as `stellar-front`, needs a
physical home that does not collide with the current SPLITROOT canary while
still inheriting the shared engine substrate and proof discipline.

## Target Layout

The factory repository should separate shared substrate from per-game assets:

```text
archon-rts-fps-factory/
├── Source/
│   ├── ArchonFactoryCanary/
│   ├── ArchonFactoryCanary.Target.cs
│   └── ArchonFactoryCanaryEditor.Target.cs
├── FactoryContracts/
│   ├── factions_schema.v3.json
│   ├── session_routes_schema.json
│   ├── entitlement_policy_schema.json
│   ├── strategic_audio_events_schema.json
│   ├── asset_manifest_schema.md
│   └── archon_adapter_contract.md
├── games/
│   ├── splitroot/
│   │   ├── Content/
│   │   ├── Config/
│   │   ├── FactoryConfig/
│   │   ├── Proof/
│   │   ├── Launchers/
│   │   ├── SplitrootCanary.uproject
│   │   ├── README.md
│   │   └── game.json
│   ├── stellar-front/
│   └── <future-canaries>/
├── scripts/
│   ├── new-canary.ps1
│   └── canary-template/
├── .agents/skills/
├── .claude/skills/
├── .claude/agents/
├── AGENTS.md
├── CLAUDE.md
├── CODEX.md
└── README.md
```

## Shared vs Per-Game Boundary

Shared root-level substrate:

- C++ engine substrate in `Source/ArchonFactoryCanary/`.
- Schema specifications in `FactoryContracts/`.
- Agent definitions, shared skills, and session-start docs.
- Build helpers and the canary template in `scripts/`.

Per-game substrate under `games/<gameName>/`:

- Unreal `Content/` assets such as maps, blueprints, materials, and widgets.
- Unreal `Config/` overrides for that canary.
- Concrete `FactoryConfig/` JSON instances that conform to shared schemas.
- `Proof/` smoke and proof scripts for the canary's arcs.
- `Launchers/` desktop shortcuts.
- The per-canary `.uproject`.
- `README.md` and `game.json`.

Engine-managed binaries, `DerivedDataCache`, `Intermediate`, and `Saved`
remain out of this contract and should be git-ignored per canary.

## Canary Manifest

Every `games/<gameName>/` directory owns a `game.json` manifest so tools can
enumerate available canaries and their current proof state.

```json
{
  "schema": "tinyassets.factory_branch.canary_manifest.v1",
  "canary_id": "splitroot",
  "display_name": "SPLITROOT",
  "genre_tag": "fantasy-rts-fps-hybrid",
  "lineage_ancestor": null,
  "goal_id_on_connector": "9171b100de33",
  "branch_def_id_on_connector": "56603af00516",
  "uproject_filename": "SplitrootCanary.uproject",
  "default_level_path": "/Game/Maps/SplitrootValley_V1",
  "factory_config_path": "FactoryConfig/",
  "proof_scripts_path": "Proof/",
  "launchers_path": "Launchers/",
  "content_path": "Content/",
  "current_rung_claimed": 1,
  "current_rung_claim_id": "0681f48a73dd4af6",
  "rung_ladder_authority": "connector_goal",
  "created_at_utc": "2026-05-20T00:00:00Z"
}
```

For a second canary, `lineage_ancestor` should name the source canary, for
example `"splitroot"`.

## Second-Canary Spawn Workflow

Once the restructure exists, adding a new canary should be a template-driven
operation:

```powershell
powershell .\scripts\new-canary.ps1 `
  -CanaryId stellar-front `
  -DisplayName "STELLAR FRONT" `
  -GenreTag "scifi-rts-fps-hybrid" `
  -GoalIdOnConnector "<new goal id>"
```

The script should create `games/stellar-front/` with empty `Content/` and
`Config/`, placeholder `FactoryConfig/` JSON, copied proof and launcher
scripts, a `<CanaryId>Canary.uproject` scaffold, `README.md`, and populated
`game.json`.

After scaffolding:

1. Author the per-game seed packet in `FactoryConfig/`.
2. Add placeholder maps and content.
3. Run the canary proof scripts from `games/stellar-front/Proof/`.
4. Iterate through the same proof-ladder discipline as SPLITROOT.
5. Claim the new goal's rung only after the proof evidence exists.

## Migration Contract

The existing single-canary layout migrates into `games/splitroot/`:

1. Move or rename the root `.uproject` to `games/splitroot/SplitrootCanary.uproject`.
2. Move per-game `Content/`, `Config/`, `Proof/`, and `Launchers/`.
3. Move concrete JSON instances from `FactoryContracts/` to `games/splitroot/FactoryConfig/`.
4. Keep schema specifications in root `FactoryContracts/`.
5. Update proof scripts and skill references to the new paths.
6. Add `games/splitroot/README.md` and `games/splitroot/game.json`.
7. Add `scripts/canary-template/` and `scripts/new-canary.ps1`.
8. Re-run all relevant proof scripts from the new per-game locations.

## Connector-Wiki Follow-Ups

After the migration lands in the factory repository:

- Update the SPLITROOT state page's operational artifacts paths.
- Update the `unreal-canary-playtest` and `unreal-archon-game-factory` skill
  descriptions for the multi-canary layout.
- Add a one-time migration note under `pages/notes/` documenting path changes
  for in-flight contracts.

## Unblocked Work

- A STELLAR FRONT prototype can exist without an engine fork.
- Multiple canaries can iterate on per-game assets without file conflicts.
- Factory marketing can point at `games/` as proof of spawned playable games.
- Entitlement policy can gate launchable games while sharing one substrate.
- Per-canary proof cadence becomes isolated.

## Non-Changes

- The shared C++ substrate remains single and root-level.
- Per-canary C++ is deferred; v0 canaries are data and content.
- This page does not authorize real spend, bounty settlement, or paid provider
  execution.

## Verification Notes

- 2026-05-24, local checkout:
  `rg 'factory-branch-games-directory|games/|new-canary|FactoryContracts|splitroot|stellar-front' pages docs .agents/skills scripts -S`
  found no existing local copy of this concept page.
- 2026-05-24, local checkout:
  `python scripts/check_primitive_exists.py action claim` exited clean against
  `origin/main`, while current local code does include `gates action=claim`.
  Treat command examples as connector-goal workflow references, not proof that
  the external factory repository has already migrated.

## References

- GitHub issue #1048
- Connector wiki page:
  `pages/concepts/factory-branch-games-directory-substrate-contract-2026-05-24.md`
- Related factory pages named in the source filing:
  `factory-branch-remix-proof-stellar-front-2026-05-24`,
  `factory-branch-substrate-state-ledger-2026-05-24`,
  `factory-branch-jsonify-faction-substrate-2026-05-24`
