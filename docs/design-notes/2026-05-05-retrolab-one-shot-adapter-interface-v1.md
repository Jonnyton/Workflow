---
title: RetroLab One-Shot Adapter Interface v1
date: 2026-05-05
status: research
source: pages/plans/retrolab-one-shot-adapter-interface-v1.md
source_issue: 357
---

# RetroLab One-Shot Adapter Interface v1

Community wiki source:
`pages/plans/retrolab-one-shot-adapter-interface-v1.md`, retrieved from the
live wiki on 2026-05-05. This repository note keeps the proposal visible to
coding sessions without promoting it to canonical `PLAN.md` truth.

## Classification

Request kind: docs/ops.

Smallest useful repo change: preserve the wiki plan as a tracked design
reference and record the implementation boundaries future RetroLab work should
respect. No runtime code change is implied by this issue.

## Adapter Interface Summary

RetroLab one-shot branch v1 proposes a universal `RuntimeAdapter` contract for
game/runtime families. Every adapter targeting v1 must declare:

- identity and compatibility fields: `adapter_id`, `schema_version`,
  `display_name`, `host_target`, `license`, `upstream_pin`, and `family`;
- artifact pins for the runtime, plus family-specific `cores` or `firmware`
  arrays when required;
- generated configuration templates for config-driven runtimes;
- launch templates for normal execution and headless proof execution;
- expected log markers with timing, stream, regex, and purpose;
- window readiness signals and screenshot-proof metadata when applicable;
- proof capabilities, deterministic status, and referenced prerequisite PRs;
- no-cheating attestations, failure modes, family linter gates, and blockers.

The proposed family enum is:

```text
scummvm
chocolate-doom
dosbox-staging
otvdm
retroarch-portable
fs-uae-aros
native-windows
classic-mac
```

## Family Obligations

Each runtime family adds constraints beyond the universal fields:

| Family | Required attestations | Forbidden or blocked |
|---|---|---|
| `scummvm` | Runtime zip artifact. | Per-game runtime config; the engine handles game IDs. |
| `chocolate-doom` | Runtime zip artifact and `-warp` plus `-timer` headless proof support. | Menu-navigation proof procedures. |
| `dosbox-staging` | Runtime zip artifact and generated per-game `.conf` templates. | Hardcoded host paths in `.conf` files. |
| `otvdm` | Runtime zip from `github.com/otya128/winevdm` releases and per-game `.ini` when needed. | Requiring a Microsoft Windows 3.x license. |
| `retroarch-portable` | Runtime `7z`, non-empty `cores`, portable `retroarch.cfg`, and `.portable` marker. | Shipping ROMs beside the runtime. |
| `fs-uae-aros` | Runtime zip, open-source replacement firmware, and per-game `.fs-uae`. | Requiring Cloanto Amiga Forever ROMs as the default path. |
| `native-windows` | Runtime artifact may be null when the game runs natively; optional shim artifacts. | DRM-locked games or games requiring uninstaller cleanup. |
| `classic-mac` | Family-level blocked until a freely licensed Apple System ROM path exists. | Not applicable while blocked. |

## Audit-Chain Anchors

Every adapter's no-cheating attestation must cover at least these anchors:

- `pc1_shortcut_bound`: process launch payload is byte-equal to parsed shortcut
  data;
- `pc2_engine_logged`: family-specific engine initialization appears in logs;
- `pc3_content_loaded`: content load proof is stronger than title-screen-only
  evidence;
- `pc4_screenshot_real`: PNG decodes, has sufficient entropy, and dimensions
  match the window;
- `pc5_clean_exit`: process exits through close handling within the allowed
  timeout;
- `pc6_audit_chain`: proof actions form an unbroken hash chain.

Adapters may add additional family-specific anchors. Title-screen-only proof
is rejected by the proposed curator linter.

## Schema Dependencies

The wiki plan names these prerequisite implementation pieces:

- `PR-026 LINTER-001 schema_cores_and_firmware` for `cores` and `firmware`
  slots;
- `PR-027 LINTER-002 platform_specific_gates` for family-gate enforcement;
- `PR-019 RUNNER-006 fs_write_text` for rendering generated config templates;
- `PR-015 RUNNER-001..005` for runner-side execution.

Until the runner-side work exists, adapter specs described by this plan are
paste-ready cartridge labels, not runnable Workflow branches.

## Drafted Adapter Specs

The wiki plan points at drafted or planned adapters:

- `scummvm-2026.2.0`;
- `chocolate-doom-3.1.1`;
- `dosbox-staging-0.83.0`;
- `retroarch-portable-v1` for Stella and Mesen;
- `fs-uae-aros-v1`;
- `native-windows-v1`, proposed under `PR-028` but not yet authored;
- `otvdm-v1`, proposed under `PR-029` but not yet authored.

## Relationship To Current Plan

This proposal is domain-specific RetroLab branch design. It aligns with
`PLAN.md` in two limited ways:

- `Engine And Domains` keeps Workflow runtime infrastructure separate from
  domain-specific graph and adapter shape.
- `Work Targets And Review Gates` expects work targets to carry role,
  lifecycle, tags, artifact refs, and review gates before promotion.

It does not change canonical engine APIs, linter schemas, or runner behavior by
itself. Future code work should promote the relevant schema and runner changes
into concrete specs or work rows before implementation.

## Follow-Up Boundaries

Future RetroLab implementation should preserve these boundaries:

- keep adapter metadata structured and lintable rather than prose-only;
- do not use proprietary firmware or ROMs as default shipped artifacts;
- keep proof requirements family-specific where runtime behavior differs;
- require stronger proof than title-screen reachability;
- keep blocker PRs explicit until runner and linter dependencies land.
