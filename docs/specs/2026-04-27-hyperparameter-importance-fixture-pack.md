---
status: active
---

# Hyperparameter Importance Fixture Pack

**Date:** 2026-04-27
**Author:** codex-gpt5-desktop
**Purpose:** make domain-node implementation immediate when scientific module lane opens.

## Fixture files

1. `hp_importance_sweep_small.csv`
   - 120 rows
   - 6 tunable params
   - target metric column `val_auc_mean`

2. `hp_importance_constant_param.csv`
   - includes one constant parameter for warning-path test

3. `hp_importance_missing_metric.csv`
   - omits target metric for validation error test

## Golden outputs

- `expected_hp_importance_top5.json`
- `expected_hp_importance_constant_warning.json`
- `expected_hp_importance_missing_metric_error.json`

## Determinism rules

- fixed random seed for permutation method
- stable tie-breaking by parameter name
- fixed decimal precision in output snapshots

## Test mapping

- `test_hp_importance_stable_ranking`
- `test_hp_importance_constant_param_warning`
- `test_hp_importance_missing_metric_error`
- `test_hp_importance_output_envelope_shape`

## Acceptance

Fixture pack is done when implementation can be written against these datasets and pass deterministic snapshot assertions without inventing new test data.
