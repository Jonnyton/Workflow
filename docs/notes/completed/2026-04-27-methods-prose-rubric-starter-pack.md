# Methods-Prose Rubric Starter Pack (Community Build)

> **Superseded 2026-04-28** by wiki page `pages/plans/methods-prose-rubric.md` (promoted clean, 47 promoted total). This note is retained as the historical drafting record.

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: superseded-by-wiki

## Intent

Provide reusable wiki rubric content so chatbots can validate methods prose through composition (existing evaluator surface + rubric), without adding new platform primitives.

## Rubric A — Version Accuracy

Check:

1. Every library/tool version claim in prose appears in run artifacts or manifests.
2. Claimed package names map to actual runtime package identifiers.

Fail examples:

- prose says `maxnet 0.1.4`; manifest shows `0.1.5`
- prose claims package not present in runtime environment

## Rubric B — Configuration Completeness

Check:

1. Core hyperparameter ranges are present.
2. Fold strategy is stated.
3. Evaluation metric definition is stated.
4. Random seed/repro seed policy is stated when relevant.

Fail examples:

- fold strategy omitted
- metric named without aggregation detail

## Rubric C — Reproducibility Anchors

Check:

1. Prose references concrete artifact(s) or script(s) used for reproduction.
2. Re-run path is at least minimally specified (what to run and from where).

Fail examples:

- "results are reproducible" with no script/artifact anchor
- references missing file names

## Rubric D — Claim/Evidence Consistency

Check:

1. Directional claims ("better", "improved") are consistent with reported metrics.
2. Confidence language matches evidence strength.

Fail examples:

- superiority claim without supporting metric comparison
- deterministic wording for noisy/uncertain outcomes

## Suggested chatbot output shape

- `checks_passed`
- `checks_failed`
- `evidence_snippets`
- `recommended_prose_patch`

## Seed domain note (RF/MaxEnt ecology)

Include pseudo-absence/background policy and spatial fold strategy in required fields when RF/MaxEnt comparisons are present.
