---
title: P0 auto-recovery trace — 2026-04-23 disk-full pattern
date: 2026-04-23
author: team-lead (trace) + navigator (narrative)
status: diagnostic record
related:
  - pages/bugs/bug-023-daemon-disk-full-after-one-heavy-wiki-session-no-storage-bud.md
  - STATUS.md Work Task #9 (Lane 4 revert-loop canary)
  - .github/workflows/p0-outage-triage.yml
---

# P0 auto-recovery trace — 2026-04-23

## Summary

Auto-recovery WORKED 3/3 times on 2026-04-23. Three p0-outage issues fired,
each triaged + repaired by `p0-outage-triage.yml` via the `disk_full` class
(`docker system prune -af`). The system self-healed every cycle. **But the
root cause kept refilling the disk faster than the prune could reclaim**,
so symptom recurred three times in 10h 28m until the worker was hard-stopped
manually.

This reframes the Concern. It is not "auto-recovery failed." It is
"auto-recovery succeeded per-cycle but was outrun by the generator."
The symptom is the disk; the cause is the revert-loop.

## Trace — three cycles 2026-04-23 UTC

| # | Fired | Class | Repair | Outcome |
|---|------|-------|--------|---------|
| Issue #51 | 11:43 UTC | `disk_full` | `docker system prune -af` | auto-recovered |
| Issue #52 | 17:49 UTC | `disk_full` | `docker system prune -af` | auto-recovered |
| Issue #53 | 22:11 UTC | `disk_full` | `docker system prune -af` | auto-recovered |

~6h between #51 and #52, ~4h between #52 and #53 — the gap is shrinking,
consistent with a generator that accelerates as available disk decreases
(likely because transcript-write contention degrades other paths that
trigger more retries). After #53 the host hard-stopped `workflow-worker`
(Exited 137) which broke the loop.

## Why per-cycle recovery wasn't enough

`p0-outage-triage.yml::disk_full` repair runs `docker system prune -af`.
That reclaims unused images + stopped-container layers + build cache. It
does NOT touch:

- Active run-transcript artifacts produced by the worker.
- LanceDB index growth from reindexing on revert.
- SqliteSaver checkpoint DB growth from committed-then-reverted steps.
- Activity log tail.

So the prune reclaims the backlog of previously-pruneable byte-debt, but
the worker's live revert-loop keeps producing fresh non-prune-eligible
artifacts. The generator outruns the pruner.

## Root-cause chain

1. Provider stack exhausted (ollama-local empty-prose cooldown-loop +
   codex quota + Gemini/Groq unregistered) → every scene's Draft phase
   returns empty prose → commit verdict REVERT.
2. Worker advances to next scene, writes another transcript, hits same
   empty-prose, commits another REVERT — and so on, scene after scene.
3. Each REVERT keeps its associated transcript/checkpoint/index artifacts
   (they're evidence of an attempt); `docker system prune` cannot reclaim
   them because they're inside the daemon's active data volume, not the
   Docker image layer cache.
4. Disk pressure rises monotonically until hitting 100%, pager fires,
   auto-recovery prunes what IT can prune (the Docker layer cache), the
   generator continues, disk refills, cycle repeats.

## What retires the symptom vs what retires the cause

- **BUG-023 storage observability (Task #8 dev-claiming):** retires the
  symptom. Rotation + soft/hard caps + storage_inspect surface mean the
  daemon knows its own disk state + rotates old transcripts before
  hitting 100%. Even under revert-loop conditions, disk stays under
  pressure threshold + pages at warn (80%) before critical (95%).
- **Lane 4 revert-loop canary (Task #9):** retires the CAUSE. Detects
  that the worker is active-but-broken (N consecutive REVERTs in window
  T) before disk pressure builds. Triggers hard-stop + .pause + page
  early — same action the host took manually on 2026-04-23, automated.
- **Provider-stack bundle (shipping):** retires the preconditions. Once
  bundle lands and Gemini+Groq register cleanly, providers stop
  exhausting the way they did on 2026-04-23. Doesn't eliminate all
  revert-loop scenarios (future empty-prose classes may appear) but
  removes the specific 2026-04-23 precipitant.

All three are complementary; each addresses a different failure layer.

## What host actions still remain

1. Expand droplet volume 25→50G via DO dashboard OR share DO API token.
   Reduces pressure headroom on normal-load growth; doesn't fix the
   revert-loop class.
2. (Was: fix provider-exhaustion — now absorbed into provider-stack
   bundle shipping this week.)

## Filed corroborating evidence

- BUG-023 (re-authored 2026-04-23) — storage-substrate diagnosis.
- BUG-024 — `_trim_to_budget` list-vs-bytes bug (context class).
- BUG-025 — claude-code subprocess unreachable in container.
- BUG-026 — world_rules.lp missing in container.
- BUG-027 — no startup file-probe (invariant violation class).
- BUG-028 — wiki slug-case mismatch (Layer-3 substrate corroboration).

## Takeaway for ops discipline

Auto-recovery in its current shape handles transient degradation well
(Docker layer-cache growth, env-perm regressions). It does NOT handle
sustained high-frequency generator failure — that class needs the
upstream canary (Lane 4) to cut the generator before symptom cascade.
The bug of 2026-04-23 wasn't that auto-recovery failed; it's that
auto-recovery was loaded as "what handles disk pressure" rather than
"what handles the specific subclasses of disk pressure that pruning
resolves." Lane 4 adds the missing upstream stage to the repair chain.
