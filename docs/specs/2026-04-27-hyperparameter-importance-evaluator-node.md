---
status: active
---

# Hyperparameter Importance Evaluator Node (Science-Domain Pre-Spec)

**Date:** 2026-04-27
**Author:** codex-gpt5-desktop
**Status:** Pre-draft spec. Domain-node contract only. Engine changes out of scope until scientific-computing module lane opens.

## 1. Scope

Define a science-domain evaluator node named `hyperparameter_importance` that ranks which sweep parameters most influence target metrics.

This is a domain-node parity feature (W&B-style), not a core engine primitive.

## 2. Inputs

- `sweep_results` (required): tabular run results with parameter columns + metric columns
- `target_metric` (required): metric to explain (e.g. `val_auc_mean`)
- `direction` (optional): `maximize` (default) or `minimize`
- `top_k` (optional int): number of parameters to return (default 10)
- `method` (optional): `permutation` (default), `anova`, `model_based`

## 3. Outputs

- `ok` (bool)
- `target_metric` (string)
- `ranking` (array), each element:
  - `parameter`
  - `importance_score`
  - `confidence` (optional)
  - `notes` (optional)
- `artifacts`:
  - `importance_table_csv`
  - `importance_plot_png` (optional)

## 4. Semantics

- v1 default method: permutation-style importance over observed sweep table.
- v1 is observational, not causal; output must state this explicitly.
- missing/constant parameters are excluded with warning entries.

## 5. Error model

- missing `target_metric` column → validation error
- insufficient rows for stable ranking → structured insufficiency error
- no tunable parameters present → validation error

## 6. Test matrix (domain module)

1. stable ranking on fixed fixture dataset
2. deterministic output ordering for tied scores (name-sort fallback)
3. clear error when metric missing
4. clear warning for constant parameters
5. artifact paths included when generation enabled

## 7. Rollout constraints

- implement only inside scientific-computing module scope
- no changes to engine dispatch API for v1
- wire as domain-node recipe callable by existing evaluator surfaces

## 8. Acceptance

Ready to implement when scientific-computing module lane opens and fixture data is available.
