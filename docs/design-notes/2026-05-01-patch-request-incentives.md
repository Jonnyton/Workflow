# Patch Request Incentives And Requester-Directed Daemons

Date: 2026-05-01
Status: accepted direction; implementation blocked by #18 and BUG-045/P1a

## Summary

Patch requests may carry optional pickup incentives, and requesters may direct
their own daemons to work on a specific request. Both mechanisms accelerate who
looks at the work. Neither changes whether the patch is accepted, released, or
merged.

## Design Contract

- Incentives are daemon pickup signals only.
- Owner-directed daemon work is an iteration accelerator only.
- Acceptance remains controlled by tests, review, moderation, outcome gates,
  release gates, live observation, and rollback evidence.
- Paid or requester-directed work must keep a clear audit trail naming the
  requester, attached incentive terms, directed daemon, produced branch/run, and
  evidence handle.
- The system must not rank a patch as more correct, safer, or more mergeable
  because an incentive exists.
- If no daemon accepts the incentive, the request remains in the normal queue.
- If a requester daemon produces a proposal, it enters the same review and gate
  path as every other proposal.

## Interface Sketch

Future API surfaces should be additive fields/actions on existing request,
market, daemon, and work-target concepts rather than a new top-level tool.

```json
{
  "patch_request_id": "req_...",
  "pickup_incentive": {
    "enabled": true,
    "amount": "opaque",
    "terms": "paid on accepted claim / completed review packet / other gate",
    "visibility": "public"
  },
  "requester_directed_daemon": {
    "daemon_id": "daemon_...",
    "instruction": "work on this patch request",
    "scope": "proposal_only"
  },
  "authority_boundary": {
    "affects_pickup_priority": true,
    "affects_acceptance": false,
    "affects_release": false,
    "affects_merge": false
  }
}
```

Expected implementation homes:

- `workflow/api/market.py` for incentive/claim/bid semantics.
- `workflow/work_targets.py` for queue ordering and request assignment.
- `workflow/daemon_registry.py` for requester-directed daemon targeting.
- `workflow/api/runs.py` / `workflow/universe_server.py` only where run/attach
  evidence is needed after BUG-045/P1a.

## Evidence

- Public lab smoke `b2a2ca326a174898` completed on 2026-05-01 after storage
  recovery.
- Parent loop run `00e5e52661c240d2` completed on 2026-05-01 for this exact
  request. It selected child branch `e019229850f9`, returned
  `automation_claim_status=no_execution_claim`, `parent_loop_status=
  blocked_before_child_attach`, `release_gate_result=HOLD`, and preserved the
  BUG-045/P1a blocker behind #18.

## Implementation Tests

- Incentivized request can be claimed earlier by eligible daemons.
- Incentive does not alter acceptance, release, merge, or moderation gates.
- Requester-directed daemon can produce a proposal/run for the specified patch.
- Requester-directed daemon output still requires normal review/gate evidence.
- Audit log records incentive terms and directed daemon provenance.
- Same request with no incentive still remains claimable through the normal
  queue.
- Conflicting incentive/directed-daemon updates are rejected or versioned.
