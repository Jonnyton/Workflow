---
title: Cross-AI Shared Goal Auto-Discovery
date: 2026-05-06
status: proposed
source_issue: 474
source_request: BUG-068 sibling, operator-AI layer
---

# Cross-AI Shared Goal Auto-Discovery

## Classification

Request kind: patch.

This is not a runtime bug. The request asks for an operator-AI convention that
helps Claude, Codex, Cursor, Cowork, and future providers discover when they
are working on the same broad Goal. It is a sibling to BUG-068, which already
landed daemon-layer blocked-pattern learning in `8face925`; this note covers
the human/operator-AI layer only.

Smallest useful repo change: document the convention and add the session-start
rule to `AGENTS.md`. No new MCP action or runtime primitive is proposed.

## Problem

Cross-provider sessions often encounter the same Goal through different entry
points: a wiki patch request, a design note, a `STATUS.md` row, an idea feed
entry, or a local worktree. If the connection only lives in one chat thread,
the next AI starts cold and may duplicate analysis, miss related work, or build
a convenience feature instead of using existing community context.

## Proposed Convention

Use three lightweight operator-layer records:

1. **Topic aggregation page.** A durable page summarizes the shared Goal,
   source issues/pages, current decisions, active lanes, and read-before-build
   links. It may live in wiki when the wiki page exists, or in tracked docs
   when a repository-visible coordination artifact is needed.
2. **Page-write trigger.** When an AI writes a durable page that introduces or
   materially changes a shared Goal, it checks whether a topic aggregation page
   exists. If the page exists, update its pointer set in the same change. If it
   does not exist and the topic is likely to recur, create a small proposed
   design note or idea entry rather than adding runtime code.
3. **Read-on-resume node body.** Any task/node/worktree expected to be resumed
   by another AI should include a compact `Read on resume:` line with the
   aggregation page, source issue, relevant `PLAN.md` section, and active
   `STATUS.md` row or branch.

## Scope Boundaries

- This convention does not add a `page_write` MCP action.
- It does not require platform-side private-data indexing.
- It does not replace `STATUS.md` claims, `_PURPOSE.md`, or
  `provider_context_feed.py`; it gives those surfaces a stable shared-goal link
  to carry.
- It applies to operator coordination first. Daemon self-learning remains the
  already-landed BUG-068 Phase A lane.

## Relationship To PLAN.md

This aligns with:

- `Harness And Coordination`: provider memories and automations are inputs to
  the GitHub/worktree spine, not hidden planning authorities.
- `Multi-User Evolutionary Design`: many branches and sessions can pursue the
  same Goal without collapsing into one canonical workflow.
- `Scoping Rules`: this is community/process composition over existing wiki,
  docs, claim, and worktree primitives, not a new platform primitive.

## Verification

For this patch, verification is documentation-only:

- `AGENTS.md` names the read/write convention for future sessions.
- This proposed design note preserves the issue request in a tracked artifact.
- No runtime files are changed, so no plugin mirror rebuild is required.
