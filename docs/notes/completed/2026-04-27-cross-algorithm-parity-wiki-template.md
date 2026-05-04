# Cross-Algorithm Parity Wiki Template

> **Superseded 2026-04-28** by wiki page `pages/concepts/cross-algorithm-parity-rf-vs-maxent.md` (RF vs MaxEnt seed instance promoted). Template + seed merged into the canonical page; sister pages (GLM/GAM, RF/neural-net, MaxEnt/ensemble) will follow the same structure when authored.

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: superseded-by-wiki

## Usage

Use this template for wiki concept pages that prevent invalid cross-algorithm comparisons in user-facing analysis.

---

## Concept Title

`<Algorithm A> vs <Algorithm B> methodological parity`

## 1) Comparison intent

- What question is being compared?
- What outcome metric is the user trying to optimize?

## 2) Assumption delta

- Algorithm A requires:
- Algorithm B requires:
- Critical mismatch risks:

## 3) Data preparation parity

- Presence/absence or background/pseudo-absence policy
- Feature preprocessing parity
- Leakage controls

## 4) Evaluation parity

- Fold strategy parity (spatial/temporal/random)
- Thresholding parity
- Prevalence/class imbalance handling parity
- Metrics that are directly comparable vs non-comparable

## 5) Common invalid conclusions

- Mistake 1:
- Mistake 2:
- Mistake 3:

## 6) Chatbot checklist (copy/paste)

1. Are both algorithms using equivalent data-split policy?
2. Are pseudo-absence/background choices explicitly documented for both arms?
3. Are thresholds and prevalence assumptions aligned?
4. Are compared metrics valid under both methods' assumptions?
5. Is any claimed superiority robust after harmonizing assumptions?

## 7) Minimum evidence package

- Config table for both algorithms
- Data prep details
- Fold strategy details
- Metric definitions
- Repro script or run artifact references

---

## Seed Instance: RF vs MaxEnt

### Assumption delta (example)

- RF typically consumes explicit labels and can work with engineered pseudo-absences.
- MaxEnt commonly depends on carefully designed background/pseudo-absence strategy.

### High-risk mistake (example)

- Claiming "RF beats MaxEnt on AUC" when pseudo-absence/background generation differs across algorithm arms.

### Required parity checks (example)

- Same pseudo-absence/background policy across both arms, or explicit normalization rationale.
- Same spatial fold strategy for both methods.
- Thresholding and prevalence adjustments documented and harmonized.
