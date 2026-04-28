---
title: CONTRIBUTORS authoring surface — file-first decision
date: 2026-04-27
author: codex-gpt5-desktop
status: proposed
type: design-note
companion:
  - AGENTS.md (Hard Rule #10)
  - ideas/INBOX.md (2026-04-25 CONTRIBUTORS entry)
  - ideas/PIPELINE.md (CONTRIBUTORS row)
  - CONTRIBUTORS.md
load-bearing-question: Does this make the user's chatbot better at serving the user's real goal?
audience: lead, navigator, future dev/spec author
---

# CONTRIBUTORS authoring surface — file-first decision

## Decision

Adopt a file-first surface (`CONTRIBUTORS.md`) as the canonical source now.

Do not add daemon/MCP write APIs for attribution at this stage.

## Why

- Hard Rule #10 already codifies commit-time behavior against `CONTRIBUTORS.md`.
- Attribution is a durable convention problem before it is an API problem.
- File-first avoids introducing new auth, write, and conflict surfaces.
- It is immediately usable by all providers and existing git workflows.

## Canonical schema (minimum)

Each actor entry should include:

1. `actor_id` (stable key used by attribution rows)
2. display name
3. GitHub handle
4. optional notes/aliases

## Commit-time behavior

When attribution rows exist:

1. read `CONTRIBUTORS.md`
2. map each `actor_id` to a GitHub handle
3. emit `Co-Authored-By:` trailer lines for resolved actors
4. silently skip missing mappings (non-blocking)

This matches Hard Rule #10 and keeps commit flow deterministic.

## Deferred API path (only if needed later)

Only consider daemon/MCP attribution APIs if all become true:

1. repeated merge conflicts on `CONTRIBUTORS.md` become operationally expensive
2. chatbot authoring requires transactional attribution writes during run-time
3. file-based workflow measurably slows contribution throughput

Until then, API surface expansion is unnecessary.

## Next actions

1. Add/confirm `CONTRIBUTORS.md` schema examples in docs conventions if missing.
2. Keep attribution integration scoped to commit-time trailer emission.
3. Reassess API need after real-user attribution volume exists.
