# Trust-Graduation Query Pack

Date: 2026-04-27
Author: codex-gpt5-desktop
Status: implementation-ready query contract

## Metric recap

Primary metric:

- `pct_skip_dry_inspect_on_session_n`

Event source contract:

- `run_request_submitted`
- fields: `user_id_hash`, `session_index_for_user`, `used_dry_inspect`, `timestamp`

## Query examples (pseudocode SQL)

### Q1: Weekly session-N skip rate

```sql
SELECT
  DATE_TRUNC('week', timestamp) AS week_start,
  session_index_for_user AS session_n,
  AVG(CASE WHEN used_dry_inspect = false THEN 1.0 ELSE 0.0 END) AS pct_skip
FROM run_request_submitted
WHERE session_index_for_user BETWEEN 1 AND 5
GROUP BY 1,2
ORDER BY 1,2;
```

### Q2: Cohort trend by first-seen week

```sql
WITH first_seen AS (
  SELECT user_id_hash, MIN(DATE_TRUNC('week', timestamp)) AS cohort_week
  FROM run_request_submitted
  GROUP BY 1
)
SELECT
  f.cohort_week,
  r.session_index_for_user AS session_n,
  AVG(CASE WHEN r.used_dry_inspect = false THEN 1.0 ELSE 0.0 END) AS pct_skip
FROM run_request_submitted r
JOIN first_seen f USING (user_id_hash)
WHERE r.session_index_for_user BETWEEN 1 AND 5
GROUP BY 1,2
ORDER BY 1,2;
```

### Q3: Guardrail pair metrics

```sql
SELECT
  DATE_TRUNC('week', timestamp) AS week_start,
  AVG(CASE WHEN used_dry_inspect = false THEN 1.0 ELSE 0.0 END) AS pct_skip,
  AVG(CASE WHEN run_status = 'error' THEN 1.0 ELSE 0.0 END) AS pct_error
FROM run_request_submitted
GROUP BY 1
ORDER BY 1;
```

## Dashboard sketch

Panel 1: session-N skip curve (N=1..5) over time
Panel 2: cohort heatmap (`cohort_week` x `session_n`)
Panel 3: skip-vs-error overlay (guardrail)

## Interpretation guidance

- Healthy: session-2/3 skip rises while error rate stays flat/down.
- Risky: skip rises with error/retry increases.
- Noisy: low-volume cohorts; annotate as provisional.
