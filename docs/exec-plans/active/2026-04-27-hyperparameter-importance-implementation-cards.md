# Hyperparameter Importance Implementation Cards

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: ready when science-domain lane opens

## Card A — Node interface wiring

- **Files:** scientific module evaluator node package, tests
- **Goal:** wire `hyperparameter_importance` input/output envelope
- **Done when:** schema contract from pre-spec is enforced

## Card B — Permutation method baseline

- **Goal:** implement v1 permutation-based importance scoring
- **Done when:** stable ranking passes fixture snapshots

## Card C — Error/warning paths

- **Goal:** implement missing metric and constant parameter handling
- **Done when:** explicit structured errors/warnings match fixture outputs

## Card D — Artifact generation

- **Goal:** emit CSV summary; optional plot artifact path
- **Done when:** output envelope includes artifact refs

## Card E — Verification and docs

- **Goal:** run focused tests + add quick usage note in domain docs
- **Done when:** test matrix is green and usage example is published

## Sequence

A -> B -> C -> D -> E
