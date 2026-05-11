---
title: Provider As Node Composition
date: 2026-05-11
author: codex-wiki-design
status: proposed
request_id: WIKI-PATCH
github_issue: 798
wiki_source: pages/patch-requests/pr-106-pr-106-llm-providers-should-be-user-composable-nodes-with-us.md
scope: design-only; no runtime code in this branch
builds_on:
  - PLAN.md#scoping-rules
  - PLAN.md#canonical-work-substrate-vocabulary
  - PLAN.md#providers
  - docs/vetted-specs.md#llm-policy-override-per-node
---

# Provider As Node Composition

## 1. Classification

Issue #798 is a project-design patch request. The request asks for LLM
providers to be user-composable nodes with user-redesignable chains. That is
architectural language, not a localized runtime bug report, so the useful
change is a proposed design note rather than a code change.

## 2. Recommendation Summary

Accept the user need: users should be able to redesign which LLM providers are
used, in what order, with what fallback or diversity behavior, at the same
level where they redesign a workflow graph.

Do not add `Provider` as a seventh canonical substrate concept and do not add a
new MCP action such as `provider_as_node` in v1. Under the current substrate
vocabulary, provider selection is best represented as:

- `Node` policy when a typed work unit needs an LLM call.
- `Edge` policy when routing depends on provider outcome, cost, latency,
  evaluator score, or failure class.
- `State` and `Run` evidence when a provider attempt happens.
- `Scope` authority when a user, branch, daemon, host, or commons template is
  allowed to choose or constrain providers.

That preserves the minimal-primitives rule while making provider chains
user-redesignable through ordinary graph editing.

## 3. Design Shape

Provider choice should be graph-visible, not hidden in daemon process config.
A user-authored node can declare an `llm_policy` that names the provider chain
or selection strategy for that node. The graph compiler and runner then turn
that policy into provider attempts, recording the effective route in run
evidence.

Example policy shape:

```yaml
node:
  id: draft-outline
  kind: prompt_template
  llm_policy:
    preferred:
      provider: claude
      model: opus
    fallback_chain:
      - provider: codex
        trigger: unavailable
      - provider: gemini
        trigger: quota_or_cooldown
    diversity:
      mode: parallel_judge
      candidates:
        - provider: claude
        - provider: groq
      evaluator: clarity_and_grounding
```

The provider entries are not separate substrate objects. They are policy
attached to a node or edge. If users want a visible "provider node" in a graph
builder UI, the UI can render an LLM-backed `Node` with its provider policy
expanded as an editable panel or subnode. The persisted graph should still map
back to canonical `Node`, `Edge`, `State`, `Scope`, `Run`, and `Trigger`.

## 4. User-Redesignable Chains

Provider chains become redesignable when users can perform these operations
through existing graph/page handles:

1. Inspect the effective provider policy on a node or branch default.
2. Edit the preferred provider, fallback chain, timeout, budget, and evaluator
   strategy within their authority scope.
3. Attach conditional edges to provider outcomes such as exhausted, skipped,
   quota, sandbox unavailable, low evaluator score, or accepted.
4. Replay a run against the changed policy and compare run evidence.
5. Publish successful provider-policy patterns as commons templates that other
   users can remix.

This is composable from `read.graph`, `write.graph`, `run.graph`, `read.page`,
and `write.page`. A future implementation may need better editor affordances or
schema validation, but it does not need a new user-facing primitive.

## 5. Boundaries

In scope for the eventual runtime/editor work:

- Node-level `llm_policy` authoring and dry inspection.
- Branch-level defaults that nodes can override.
- Conditional routing based on typed provider attempt diagnostics.
- Run evidence that reports the effective provider chain, skipped providers,
  attempts, costs when known, latency, failure classes, and caveats.
- Commons templates for provider policies.

Out of scope:

- A platform-level `Provider` substrate concept.
- A new MCP action dedicated to provider-chain editing.
- Hiding provider changes in daemon config with no graph-visible evidence.
- Silent fallback to providers that were not registered and probed at startup.
- Provider-specific UX that only works in one chatbot host.

## 6. Minimal Implementation Path

The smallest later implementation should build on the existing per-node
`llm_policy` direction rather than replacing provider routing:

1. Stabilize the graph schema for node-level `llm_policy` plus branch defaults.
2. Add graph inspection output that shows the resolved policy before execution.
3. Add editor/chatbot wording that lets users change policy in their own terms:
   "use local first, then Claude if local is unavailable" should compile to the
   structured policy.
4. Route execution through the existing provider router and diagnostics.
5. Record provider attempt diagnostics in `Run` evidence so users can compare
   redesigns.

No runtime code is changed by this note.

## 7. Verification For This Note

Documentation-only verification:

- `python scripts/check_primitive_exists.py action provider_as_node`
- `python scripts/check_primitive_exists.py action route_provider`
- `python scripts/check_primitive_exists.py action compose_provider_chain`
- `python -m ruff check` is not applicable because no Python files are
  changed.

