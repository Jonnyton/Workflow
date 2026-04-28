---
title: Trust-graduation observability metric (dry-inspect skip rate)
date: 2026-04-27
author: codex-gpt5-desktop
status: proposed
type: design-note
companion:
  - ideas/INBOX.md (2026-04-27 trust-graduation entry)
  - ideas/PIPELINE.md (trust-graduation row)
load-bearing-question: Does this make the user's chatbot better at serving the user's real goal?
audience: navigator, dev, observability implementers
---

# Trust-graduation observability metric (dry-inspect skip rate)

## Goal

Operationalize one concrete metric for confidence progression:

`pct_skip_dry_inspect_on_session_n`

Interpretation: as users gain trust, they skip explicit dry-inspect confirmation steps in later sessions.

## Event contract (minimum)

Emit one event per branch run request:

- `event_name`: `run_request_submitted`
- required fields:
  - `user_id_hash`
  - `session_index_for_user` (1-based)
  - `used_dry_inspect` (boolean)
  - `timestamp`

## Metric definition

For session index `N`:

`pct_skip_dry_inspect_on_session_n =`
`count(events where session_index_for_user=N and used_dry_inspect=false) /`
`count(events where session_index_for_user=N)`

Track for N=1..5 initially.

## Guardrails

- Do not collect raw user identifiers; hash/pseudonymize upstream.
- Do not infer quality from this metric alone; pair with failure/retry/error rates.
- Treat low-volume cohorts as statistically unstable.

## Success criterion

Metric is considered implemented when:

1. event schema is emitted consistently,
2. N=1..5 aggregates are queryable weekly,
3. dashboard or report can show trend over time.

## Next actions

1. Add event instrumentation ticket when observability lane opens.
2. Add one query/aggregation helper for weekly snapshots.
3. Add a brief interpretation rubric (healthy vs unhealthy trend patterns).
