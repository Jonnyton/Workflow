# Community Loop Core Team v1

status: live
created: 2026-05-02

These are the host-provided core souls for the community-driven patch loop.
They are durable daemon identities, not prompt templates. Their job is to keep
the request loop moving when no qualified community daemon has claimed the
corresponding role.

## Team

| Role | Daemon | Soul file | Primary work |
|------|--------|-----------|--------------|
| Request intake | Ada Request Steward | `ada-request-steward.md` | Preserve request records, classify kind/severity, keep wiki/GitHub labels coherent. |
| Investigation packet | Mira Investigation Planner | `mira-investigation-planner.md` | Turn a request into a bounded patch packet, feature spec, migration plan, or refusal. |
| Implementation writer | Noor Patch Writer | `noor-patch-writer.md` | Produce the implementation branch or PR using approved Claude/Codex writer lanes. |
| Cross-family check | Soren Cross Checker | `soren-cross-checker.md` | Verify code, policy labels, tests, and opposite-family review requirements. |
| Release observation | Vera Release Observer | `vera-release-observer.md` | Watch CI, deploy, canaries, rendered user surfaces, and post-fix clean-use evidence. |
| Contract and claims | Elias Contract Arbiter | `elias-contract-arbiter.md` | Interpret gate, bounty, writer/checker, payment, and domain-claim requirements. |

## Live Registration

Registered in the host-local daemon registry on 2026-05-02 under
`C:\Users\Jonathan\AppData\Roaming\Workflow`.
The live daemon wikis were calibrated with the Claude/Codex family policy on
2026-05-02 without changing daemon IDs or copying souls.

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
More capacity attaches more runtime instances to the same daemon identity; it
does not copy the soul.

Community or house daemons can run loop work in two ways:

1. They present confirmed domain claims that satisfy the node's role
   requirements.
2. The node explicitly lends the corresponding core team soul and bounded wiki
   memory packet as temporary role context.

Borrowed-soul execution is not identity copying. The executor remains itself,
the borrowed core soul is cited as role context, and any learning signal should
be routed back to the corresponding core daemon wiki when the runtime supports
that write path.

## Claude/Codex Calibration

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
- OpenAI Codex docs describe Codex as a coding agent that can read, edit, run
  code, work in background cloud environments, create PRs, and review PRs.
  Source: https://developers.openai.com/codex/cloud
- OpenAI Codex review guidance emphasizes high-signal review for serious bugs,
  repository guidance through `AGENTS.md`, and human/owner responsibility for
  final merge decisions.
  Sources: https://developers.openai.com/codex/integrations/github and
  https://developers.openai.com/codex/guides/build-ai-native-engineering-team

As-built Workflow loop alignment:

- `.github/workflows/auto-fix-bug.yml` is the current reference free claimant.
  It picks Claude OAuth first, Codex subscription second, and never falls
  through to API-key billing lanes for default daemon writing.
- `daemon-request-policy.yml` enforces `writer:claude -> checker:codex` and
  `writer:codex -> checker:claude`.
- `community_change_context` already presents PR/issue state with a review
  standard that requires Claude-family checking for Codex-written PRs.

Family use is therefore role-specific, not a fixed "all-Claude" or
"all-Codex" team:

| Role | Family policy |
|------|---------------|
| Ada Request Steward | Family-neutral; can run on either family. Prefer lower-cost/classifier-capable runtime because output is a durable request envelope, not code. |
| Mira Investigation Planner | Claude-family preferred for narrative synthesis and refusal quality; Codex-family acceptable when the packet needs deeper repository/file impact analysis. |
| Noor Patch Writer | Uses the workflow-selected writer family: Claude primary when `CLAUDE_CODE_OAUTH_TOKEN` is visible, Codex fallback when `WORKFLOW_CODEX_AUTH_JSON_B64` is visible. Must emit the matching `writer:*` label. |
| Soren Cross Checker | Must run opposite the actual writer family. If writer is Claude, Soren's checker runtime is Codex; if writer is Codex, Soren's checker runtime is Claude. |
| Vera Release Observer | Family-neutral; can run on either family. It must use concrete run IDs, canary output, rendered-chat proof, and clean-use evidence rather than model confidence. |
| Elias Contract Arbiter | Claude-family preferred for policy interpretation; Codex-family acceptable for mechanical label/contract checks. Eligibility decisions must cite concrete claim proof. |

Design consequence: the core team is a workflow with durable role identities,
not six unconstrained autonomous agents. The loop should pass compact artifacts
between roles: request envelope -> change packet -> branch/PR -> review
verdict -> release observation. This matches the dev's current loop, which is
issue/label/workflow/PR driven rather than a private multi-agent chat.

## Non-Goals

- Do not make authoring depend on these daemons. Users can still create, fork,
  and bind community branches with zero daemons online.
- Do not make these souls privileged platform truth. They are host-provided
  reference workers for the loop.
- Do not let a same-family writer/checker pair pass machine-authored code.
- Do not use API-key billing lanes for default project writer/checker work.
