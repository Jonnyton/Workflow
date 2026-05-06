---
title: Coding Swarm Architecture Research
date: 2026-05-06
status: proposed
source_issue: 437
source_wiki_path: pages/notes/pages-notes-cowork-coding-swarm-architecture-research-2026-05-05.md
request_kind: project-design
---

# Coding Swarm Architecture Research

## Classification

Issue #437 is a project-design request. The smallest useful repository change
is this proposed design note. It does not imply runtime code changes, new MCP
actions, or a new daemon primitive.

The source wiki page named by the issue was not present in this checkout, and
the GitHub issue carried no additional comments. This note therefore preserves
the request as a Workflow-native architecture recommendation based on the issue
contract, current `PLAN.md`, and a fresh 2026-05-06 research pass.

## Research Snapshot

Current coding-agent products and research converge on a few patterns:

- OpenAI Codex cloud runs coding work in task-specific cloud environments and
  supports background parallel work; Codex subagents can spawn specialized
  agents in parallel and consolidate their results in one response.
- Claude Code subagents are optimized for specialization and context isolation;
  Claude's public guidance warns that multi-agent systems commonly spend
  3-10x the tokens of a comparable single-agent run, so parallelism should be
  reserved for independent research, clean interface splits, and black-box
  verification.
- GitHub Copilot cloud agent treats GitHub Issues, PRs, IDEs, CLI, mobile, and
  external MCP-capable tools as assignment entry points, then works in the
  background and raises a PR for review.
- CAID research names the durable software-engineering primitive set clearly:
  central task delegation, asynchronous execution, isolated workspaces,
  branch/merge integration, and executable test-based verification.
- BOAD research suggests swarm topologies should be measured and adjusted with
  evaluation signal rather than manually frozen; agent roles that help one repo
  or task class may hurt another.

Sources:

- OpenAI Codex docs, `Codex web` and `Subagents`:
  https://developers.openai.com/codex/cloud,
  https://developers.openai.com/codex/subagents
- Claude Code subagents docs:
  https://code.claude.com/docs/en/sub-agents
- Anthropic multi-agent guidance:
  https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
- GitHub Copilot cloud agent docs:
  https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/start-copilot-sessions
- CAID paper:
  https://arxiv.org/abs/2603.21489
- IBM BOAD publication:
  https://research.ibm.com/publications/boad-discovering-hierarchical-software-engineering-agents-via-bandit-optimization

## Workflow Fit

Workflow already has most of the swarm substrate in its process and product
architecture:

- `STATUS.md` and GitHub Issues are central delegation surfaces.
- `Files` and `Depends` cells are the collision and dependency graph.
- Branches, worktrees, and PRs provide isolated execution and merge review.
- The daemon request contract already names writer pools, checker families,
  gate requirements, and bounty settlement boundaries.
- `PLAN.md` already separates daemon identity from runtime instances and
  treats host fleet capacity as an operating-cost decision, not a platform cap.
- The quality gates already require opposite-family checking for substantive
  changes and rendered chatbot verification for public MCP behavior.

The implication is conservative: Workflow should not add a generic
`coding_swarm` action or special swarm runtime. The useful architecture is a
claimable swarm lane profile over existing primitives.

## Proposed Direction

Treat a coding swarm as a bounded, inspectable lane with these fields:

- source request: GitHub issue or wiki filing;
- central manager: one lead provider/session responsible for splitting work,
  integration, and final answer;
- workers: Claude/Codex/Copilot/other eligible coding agents selected by the
  request contract and gate requirements;
- checker: opposite-family verifier for code-changing work;
- isolation: one branch/worktree or cloud task per write scope;
- write boundary: exact `Files` claim per worker;
- dependency boundary: exact `Depends` edge before any overlap;
- evidence: tests, lint, review notes, and user-surface proof where applicable;
- fanout cap: explicit maximum worker count and maximum nesting depth;
- stop rule: cancel or merge back to a single integrator when coordination
  overhead exceeds useful parallel work.

This preserves the benefits of coding swarms without hiding work behind an
opaque orchestrator. A fresh checkout should still be able to reconstruct who
owns what from GitHub, `STATUS.md`, `_PURPOSE.md`, and the branch diff.

## Admission Rules

Use swarm execution only when at least one of these is true:

- independent research paths can run without sharing mutable state;
- implementation slices have clean file or API boundaries;
- black-box verification can run independently of the implementation context;
- the task is long-running enough that asynchronous execution beats a single
  local session;
- the request contract explicitly requires multiple eligible writer/checker
  families.

Do not use swarm execution when:

- a single agent can handle the task within one context and one write boundary;
- the split is by generic roles such as planner/coder/tester/reviewer but the
  same context must be handed back and forth repeatedly;
- the work touches shared storage, auth, migrations, public MCP behavior, or
  deploy paths without a clear lead integrator and independent verification;
- the branch has no current `STATUS.md` row, `_PURPOSE.md`, or PR metadata that
  explains why it exists.

## Future Implementation Candidates

No implementation is recommended from this issue alone. Later work can be
scoped if repeated swarm lanes show the same manual burden:

1. A docs-only "swarm lane checklist" in `AGENTS.md` if multiple providers keep
   mis-splitting swarm work.
2. A diagnostic report that compares active `STATUS.md` file claims against
   branch/worktree metadata and flags missing lead/checker/fanout fields.
3. A metrics note tracking swarm outcomes: elapsed time, review failures,
   merge conflicts, token/runtime cost, and post-merge defect rate.

Those candidates should each clear the five `PLAN.md` scoping rules before
they become platform work. In particular, any new runtime primitive must prove
it is not just a convenience over GitHub Issues, `STATUS.md`, worktrees, PRs,
and existing gate requirements.

## Open Questions

- Should swarm lane metadata live only in `_PURPOSE.md` and PR bodies, or does
  `STATUS.md` need optional lead/checker/fanout columns once this becomes
  common?
- What minimum evaluation signal is enough to compare one topology against
  another for Workflow tasks?
- Should paid-market requests declare a maximum coordination budget before
  daemons may fan out to multiple paid workers?
- How should browser-only users inspect a swarm lane without reading raw GitHub
  branches and provider logs?
