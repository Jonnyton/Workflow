# Community Loop Core Team v1

status: live
created: 2026-05-02

These are the host-provided core souls for the community-driven patch loop.
They are durable daemon identities, not prompt templates. Their job is to keep
the request loop moving when no qualified community daemon has claimed the
corresponding role.

## Team

| Role | Daemon | Fixed LLM | Soul file | Primary work |
|------|--------|-----------|-----------|--------------|
| Request intake | Ada Request Steward | `claude-haiku-4-5-20251001` | `ada-request-steward.md` | Preserve request records, classify kind/severity, keep wiki/GitHub labels coherent. |
| Investigation packet | Mira Investigation Planner | `claude-opus-4-7` | `mira-investigation-planner.md` | Turn a request into a bounded patch packet, feature spec, migration plan, or refusal. |
| Implementation writer | Noor Patch Writer | `claude-sonnet-4-6` | `noor-patch-writer.md` | Produce the implementation branch or PR as the fixed Claude writer. |
| Cross-family check | Soren Cross Checker | `gpt-5.3-codex` | `soren-cross-checker.md` | Verify Noor's Claude-written code, policy labels, tests, and Codex checker requirements. |
| Release observation | Vera Release Observer | `gpt-5.3-codex` | `vera-release-observer.md` | Watch CI, deploy, canaries, rendered user surfaces, and post-fix clean-use evidence. |
| Contract and claims | Elias Contract Arbiter | `claude-opus-4-7` | `elias-contract-arbiter.md` | Interpret gate, bounty, writer/checker, payment, and domain-claim requirements. |

## Live Registration

Registered in the host-local daemon registry on 2026-05-02 under
`C:\Users\Jonathan\AppData\Roaming\Workflow`.
The live daemon wikis were calibrated with the Claude/Codex family policy on
2026-05-02 without changing daemon IDs or copying souls. They were then pinned
to fixed model IDs on 2026-05-02; the pin is an active soul-version amendment,
not a new daemon identity.

| Daemon | daemon_id | Soul hash |
|--------|-----------|-----------|
| Ada Request Steward | `daemon::ada-request-steward::ef1e90335fa66274` | `ef1e90335fa66274179834ee4981cfc32bbc9b5ffa53e959fe273aba97550c20` |
| Mira Investigation Planner | `daemon::mira-investigation-planner::76cc0f5d70e2b2b0` | `76cc0f5d70e2b2b064707700d133720ba094a353d07e5a829ad248c294b732b6` |
| Noor Patch Writer | `daemon::noor-patch-writer::826a1bb7c26ea008` | `826a1bb7c26ea0084dcc6e8e192b5e4a6c9d36025b0e9cef20507f14596c81ee` |
| Soren Cross Checker | `daemon::soren-cross-checker::5afe4175e2a906bc` | `5afe4175e2a906bccd0813402d761a1a8d520c9f75cda85ba814b8c1a575fb5f` |
| Vera Release Observer | `daemon::vera-release-observer::cf176680e412aa36` | `cf176680e412aa3688197e583750922156a9ff2a41abe178982fcd7c2291dce2` |
| Elias Contract Arbiter | `daemon::elias-contract-arbiter::bae8302ee53fe623` | `bae8302ee53fe62316e99c528f41ecbb8f7b65fb041e328427b0f31298bbff64` |

## Routing Policy

Loop nodes should prefer the core daemon assigned to the node's role when there
is pending work and no better qualified claimant has already won the request.
More capacity attaches more runtime instances using that same daemon's fixed
model. A different model is a different executor: either a renamed/forked daemon
with lineage, or an external daemon borrowing the core role context. It does
not become the core daemon and does not copy the soul.

Community or house daemons can run loop work in two ways:

1. They present confirmed domain claims that satisfy the node's role
   requirements.
2. The node explicitly lends the corresponding core team soul and bounded wiki
   memory packet as temporary role context.

Borrowed-soul execution is not identity copying. The executor remains itself,
the borrowed core soul is cited as role context, and any learning signal should
be routed back to the corresponding core daemon wiki when the runtime supports
that write path.

## Fixed LLM Calibration

Research pass: 2026-05-02. Primary sources checked:

- Anthropic's agent workflow guidance distinguishes predefined workflows from
  autonomous agents, recommends orchestrator-worker and evaluator-optimizer
  patterns where task boundaries and evaluation criteria are clear, and stresses
  environment-grounded feedback plus stopping conditions.
  Source: https://www.anthropic.com/engineering/building-effective-agents
- Claude Code GitHub Actions v1 runs from issue/PR context, follows repository
  standards such as `CLAUDE.md`, supports prompt-driven automation, and defaults
  to Sonnet unless a model is configured.
  Source: https://code.claude.com/docs/en/github-actions
- Claude Code model configuration says production deployments should pin full
  model names rather than aliases. Current relevant IDs include Claude Opus 4.7,
  Claude Sonnet 4.6, and Claude Haiku 4.5.
  Source: https://code.claude.com/docs/en/model-config
- OpenAI Codex docs describe Codex as a coding agent that can read, edit, run
  code, work in background cloud environments, create PRs, and review PRs.
  Source: https://developers.openai.com/codex/cloud
- OpenAI's model docs describe `gpt-5.3-codex` as optimized for agentic coding
  tasks in Codex or similar environments, with a 400k context window and
  high/xhigh reasoning options.
  Source: https://developers.openai.com/api/docs/models/gpt-5.3-codex
- OpenAI Codex review guidance emphasizes high-signal review for serious bugs,
  repository guidance through `AGENTS.md`, and human/owner responsibility for
  final merge decisions.
  Sources: https://developers.openai.com/codex/integrations/github and
  https://developers.openai.com/codex/guides/build-ai-native-engineering-team

As-built Workflow loop alignment:

- `.github/workflows/auto-fix-bug.yml` is the current reference free claimant.
  It picks Claude OAuth first, Codex subscription second, and never falls
  through to API-key billing lanes for default daemon writing. The v1 core team
  makes that Claude-first path explicit: Noor is the fixed Claude writer and
  Soren is the fixed Codex checker.
- `daemon-request-policy.yml` enforces `writer:claude -> checker:codex` and
  `writer:codex -> checker:claude`. The core team covers the first pair. A
  Codex-writer fallback must use a distinct Codex writer identity and a distinct
  Claude checker identity, not silently swap Noor or Soren's models.
- `community_change_context` already presents PR/issue state with a review
  standard that requires Claude-family checking for Codex-written PRs.

Model use is therefore fixed per daemon, not selected per run:

| Role | Fixed LLM | Why this model fits the soul |
|------|-----------|------------------------------|
| Ada Request Steward | `claude-haiku-4-5-20251001` | Fast Claude intake for short, truthful request envelopes and label hygiene. |
| Mira Investigation Planner | `claude-opus-4-7` | Deep Claude reasoning for evidence synthesis, uncertainty, refusals, and change-packet design. |
| Noor Patch Writer | `claude-sonnet-4-6` | Claude Code's daily coding lane for concise implementation branches that follow repo conventions. |
| Soren Cross Checker | `gpt-5.3-codex` | Codex review lane for tracing Claude-written diffs, CI, and serious code risks. |
| Vera Release Observer | `gpt-5.3-codex` | Codex evidence tracing across code, Actions, deploy outputs, canaries, and proof artifacts. |
| Elias Contract Arbiter | `claude-opus-4-7` | Deep Claude policy interpretation for contracts, claims, forks, and payment/gate boundaries. |

Design consequence: the core team is a workflow with durable role identities,
not six unconstrained autonomous agents. The loop should pass compact artifacts
between roles: request envelope -> change packet -> branch/PR -> review
verdict -> release observation. The fixed-model contract is part of identity:
running another model in a role requires an external claimant, a borrowed-role
context, or a renamed/forked daemon. This matches the dev's current loop, which
is issue/label/workflow/PR driven rather than a private multi-agent chat.

## Non-Goals

- Do not make authoring depend on these daemons. Users can still create, fork,
  and bind community branches with zero daemons online.
- Do not make these souls privileged platform truth. They are host-provided
  reference workers for the loop.
- Do not let a same-family writer/checker pair pass machine-authored code.
- Do not use API-key billing lanes for default project writer/checker work.
