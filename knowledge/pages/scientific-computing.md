---
title: Scientific Computing — Key Disambiguations
date: 2026-04-20
status: living page
---

# Scientific Computing — Key Disambiguations

## maxnet vs. Java MaxEnt GUI

Two separate implementations of maximum entropy species distribution modelling.
The chatbot treats the user's stated implementation as authoritative — **do not
translate `maxnet` to `MaxEnt` or vice versa**.

| Dimension | `maxnet` (R package) | Java MaxEnt GUI |
|---|---|---|
| **Primary citation** | Phillips et al. 2017, *Ecography* | Phillips et al. 2006, *Ecography* |
| **Language / runtime** | Native R; no Java dependency | Java desktop application |
| **Wrapper packages** | `maxnet` directly; ENMeval / kuenm call it | `dismo::maxent()` shells the JAR |
| **Output object** | `maxnet` S3 object; `lambda` list coefficients | `.lambdas` text file (per-feature lambdas) |
| **Default feature classes** | LQHPT (linear, quadratic, hinge, product, threshold) | LQHPT; but GUI defaults differ slightly by version |
| **Regularisation** | `regmult` multiplier applied to regularisation betas | `beta_multiplier` in GUI / `dismo::maxent(args=)` |
| **Seed / reproducibility** | `set.seed()` in R session before fitting | `--randomseed` flag or GUI checkbox |
| **Prediction method** | `predict.maxnet(type="cloglog"/"logistic"/"exponential")` | `maxent.jar` predict sub-command; `dismo::predict` wrapper |
| **Presence-background vs. presence-only** | Presence-background explicit | Presence-only with background sampling built-in |

### Why the distinction matters for the chatbot

- A user who says "`maxnet`" is using the R package. Suggesting `dismo::maxent()` syntax
  will break their code.
- A user who says "MaxEnt" or "the MaxEnt software" is likely using the Java GUI or
  `dismo::maxent()`. Do not assume they have the R `maxnet` package installed.
- Output formats differ: `maxnet` produces R objects; Java MaxEnt produces `.lambdas`
  and `.csv` files. Telling a `maxnet` user to look for a `.lambdas` file will confuse them.
- Feature-class defaults and regularisation parameter names differ — always confirm
  which implementation before suggesting tuning code.

### Quick identification heuristic

If the user's code contains:

- `library(maxnet)` / `maxnet::maxnet()` → they are using the R `maxnet` package.
- `dismo::maxent()` / references to a `.jar` file → they are using the Java MaxEnt GUI via `dismo`.
- ENMeval / kuenm → likely wrapping `maxnet` by default in recent versions; confirm.

### References

- Phillips, S.J., Anderson, R.P., Dudík, M., Schapire, R.E., Blair, M.E. (2017).
  Opening the black box: an open-source release of Maxent. *Ecography*, 40(7), 887–893.
  (This is the `maxnet` R paper.)
- Phillips, S.J., Anderson, R.P., Schapire, R.E. (2006). Maximum entropy modeling of
  species geographic distributions. *Ecological Modelling*, 190(3–4), 231–259.
  (This is the original Java MaxEnt paper.)
