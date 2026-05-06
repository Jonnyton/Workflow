---
title: RetroLab gap burndown v1
date: 2026-05-05
status: research
source: pages/plans/retrolab-gap-burndown-v1.md
source_issue: 346
---

# RetroLab Gap Burndown v1

Community wiki source:
`pages/plans/retrolab-gap-burndown-v1.md`, retrieved from the live wiki on
2026-05-05. This repository note keeps the proposal visible to coding sessions
without promoting it to canonical `PLAN.md` truth.

## Classification

Request kind: docs/ops.

Smallest useful repo change: preserve the wiki plan as a tracked design
reference and extract its implementation implications for future RetroLab work.
No runtime code change is implied by this issue.

## Catalog Snapshot

The wiki plan defines RetroLab's current recipe catalog in three buckets:

| Bucket | Count | Items |
| --- | ---: | --- |
| PASS | 2 | Beneath a Steel Sky (`bass-cd-1.2-scummvm-2026.2.0`); Lure of the Temptress (`lure-1.1-scummvm-2026.2.0`) |
| Near-PASS | 3 | DOOM shareware E1; Jill of the Jungle vol. 1; Alter Ego NES homebrew |
| Candidate research | 3 | Tyrian 2000; Catacomb Abyss; Lan Master |

The two PASS recipes both use the `scummvm-2026.2.0` adapter, so the current
verified platform family is ScummVM-engine adventures. The near-PASS set is
mostly blocked by missing hash pins, missing legal evidence pins, and runner
capabilities rather than by unresolved recipe shape.

## Near-PASS Blockers

The fastest catalog expansion path is:

1. Pin `chocolate-doom-3.1.1-win64.zip` for the DOOM shareware recipe. The
   wiki plan reports legal evidence and DOOM artifact hashes already verified,
   leaving one curator fetch and hash compute before PASS.
2. Capture Wayback snapshots for the BASS and Lure legal/source evidence URLs
   to close LINT-G4 warnings. This is cleanup for already-PASS recipes.
3. Advance Jill of the Jungle after RUNNER-006 (`fs_write_text`) lands, then
   pin three hashes and decide the primary legal host.
4. Advance Alter Ego after RUNNER-007 (`fs_extract_formats`) lands, with hashes
   pre-pinnable while the runner work is pending.

## Patch Ticket Graph

The wiki page organizes the runner work as this dependency chain:

| Ticket | Capability | Direct effect |
| --- | --- | --- |
| PR-015 / RUNNER-001..005 | Paired runner bootstrap: install, launch, screenshot, audit chain | Required before any user-host recipe can be proven |
| PR-019 / RUNNER-006 | `fs_write_text` for generated config files | Unblocks Jill and future DOSBox per-game recipes |
| PR-020 / RUNNER-007 | Archive extraction formats including 7z, tar.gz, and split files | Unblocks Alter Ego and broader RetroArch/console-homebrew recipes |
| PR-021 / RUNNER-008 | Uniform process launch log contract | Simplifies RetroArch and cross-runtime marker handling |
| PR-022 / RUNNER-009 | Window wait / non-black-frame stability primitive | Reduces fixed sleeps and screenshot timing flake |
| PR-016 / CONNECTOR-001 | `extensions.build_branch` schema for the recipe forge | Makes the curator pipeline executable as a workflow |

Critical path by recipes unlocked: PR-015 first, PR-019 second, PR-020 third.
PR-021, PR-022, and PR-016 are useful but should not outrank catalog growth
unless their absence becomes the active blocker.

## Platform Family State

The plan's capability matrix implies these review constraints for future
RetroLab branches:

- ScummVM-engine adventures are ready for more recipe work; remaining tasks are
  per-recipe evidence and hash pins.
- DOSBox recipes need RUNNER-006 for per-game `.conf` generation before they
  are a repeatable family.
- RetroArch console/homebrew recipes need RUNNER-007 for 7z extraction and
  likely RUNNER-006/RUNNER-008 for config and log handling.
- Source-port DOS recipes can move one by one when runtime artifacts are pinned.
- Early Windows, Amiga, GBA, SNES, and Game Boy need adapter and legal-source
  research before code implementation.
- Classic Mac is blocked by the ROM licensing gap and should stay out of build
  lanes until that legal/runtime premise changes.

## Candidate Research Queue

The wiki page proposes three non-ScummVM candidates for week-one research, all
still research-grade. The retrieved markdown is source-incomplete: the
frontmatter and heading say the queue has three candidates, and the schedule
names Tyrian 2000, Catacomb Abyss, and Lan Master, but the page body retrieved
on 2026-05-05 ends in the Catacomb Abyss blocker list before a detailed Lan
Master section appears.

| Candidate | Runtime path | Main blockers |
| --- | --- | --- |
| Tyrian 2000 | DOSBox-Staging, with OpenTyrian as a possible native contrast | Rights-holder/free-distribution evidence, artifact hashes, RUNNER-006 cycle config |
| Catacomb Abyss | DOSBox-Staging | Primary 3D Realms legal evidence or Wayback proof; artifact hash pins |
| Lan Master | RetroArch/Mesen NES, inferred from the platform-family table | Mentioned as a research candidate, but detailed legal/artifact blockers are absent from the retrieved page body |

These candidates should become draft recipes only after legal evidence and
artifact provenance are pinned. They are not implementation authority by
themselves.

## Relationship To Current Plan

This proposal aligns with the `PLAN.md` Community Evolvable Optimization
principle: optimization and catalog growth should use typed artifacts,
repeatable evaluators, lineage, and explicit merge policy rather than hidden
manual experimentation. It also fits Work Targets And Review Gates: every
candidate recipe needs a declared editable surface, evidence chain, acceptance
test, and review gate before it can move from research to build.

The page is not a canonical architecture decision. It is a RetroLab work-target
map for future specs, claims, and review.

## Follow-Up Candidates

Future work should be split into concrete lanes before code changes begin:

1. Runner PR-015 proof lane: prove the BASS harness end to end on a paired
   Windows host.
2. RUNNER-006 lane: implement and audit allowlisted config-file writes.
3. Curator evidence lane: pin DOOM runtime hash and archive Wayback evidence for
   BASS/Lure.
4. RUNNER-007 lane: implement archive extraction coverage for 7z, tar.gz, and
   split DOS archives.
5. Candidate research lane: verify Tyrian 2000 and Catacomb Abyss primary
   legal sources before drafting recipes, then re-read or repair the wiki page
   before treating Lan Master as more than a named research candidate.

Each lane should be promoted into a `STATUS.md` row or specific GitHub issue
with exact file boundaries before implementation.
