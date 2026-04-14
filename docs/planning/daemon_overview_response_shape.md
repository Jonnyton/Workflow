# `daemon_overview` Response Shape

Phase H aggregated-view schema. MCP action:

```
universe action=daemon_overview universe_id=<uid> [limit=<int|"full">]
```

Returns a single JSON payload with the following shape:

```json
{
  "universe_id": "test-uni",
  "dispatcher": {
    "tier_status_map": {
      "host_request": "live",
      "user_request": "live",
      "owner_queued": "live",
      "goal_pool": "stubbed (Phase F)",
      "paid_bid": "stubbed (Phase G)",
      "opportunistic": "stubbed"
    },
    "config": {
      "accept_external_requests": true,
      "accept_goal_pool": false,
      "accept_paid_bids": false,
      "allow_opportunistic": false,
      "bid_coefficient": 0.0,
      "bid_term_cap": 30.0
    }
  },
  "queue": {
    "pending_count": 0,
    "top": [],
    "archived_recent_count": 0
  },
  "subscriptions": {
    "goals": ["maintenance"],
    "drift_flag": "ok",
    "pool_status_per_goal": {"maintenance": 0},
    "pool_flag_enabled": false
  },
  "bids": {
    "open_count": 0,
    "claimed_count": 0,
    "top_open": [],
    "daemon_capabilities": {
      "serves_llm_types": [],
      "paid_market_enabled": false,
      "bid_coefficient": 0.0
    }
  },
  "settlements": {
    "count_total": 0,
    "count_unsettled": 0,
    "recent": []
  },
  "gates": {
    "total_claims": 0,
    "recent_claims": []
  },
  "activity_tail": [],
  "run_state": {
    "current_phase": "",
    "status": "",
    "last_verdict": "",
    "total_words": 0,
    "total_chapters": 0,
    "last_updated": ""
  }
}
```

## Limits

The `limit` parameter controls top-N cutoffs. Defaults:

| Field | Default | Absolute cap (`limit="full"`) |
|---|---|---|
| `queue.top` | 20 | 500 |
| `bids.top_open` | 20 | 500 |
| `settlements.recent` | 10 | 500 |
| `gates.recent_claims` | 10 | 200 |
| `activity_tail` | 30 | 1000 |

Passing `limit=<int>` applies that cap uniformly to all lists (bounded by the absolute cap per field).

## Freshness

1-second TTL cache per `(universe_id, limit)` pair. Write actions that affect the response (`set_tier_config`, `queue_cancel`, …) invalidate the cache for that universe so the next call returns fresh data.

## Error handling

- Unknown universe → `{"error": "Universe 'X' not found."}`.
- Individual subsystem read failures log WARN and return empty defaults for that field — the response never errors globally because one source is down.

## Read-only contract

`daemon_overview` MUST NOT mutate state. Cached reads are consistent within the 1-second TTL (preflight §4.3 invariant 1).
