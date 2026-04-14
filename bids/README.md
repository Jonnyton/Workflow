# Node Bids (Phase G)

This directory holds **NodeBid posts** — cross-universe, bid-priced
execution requests for individual nodes.

## YAML shape

```yaml
node_bid_id: nb_1712345678901_abcd1234
node_def_id: extract_entities   # must exist in an accessible branches/*.yaml
required_llm_type: ""           # empty = any daemon; otherwise e.g. "claude-opus"
inputs:                         # FLAT dict of primitives only
  text: "some input"
  max_tokens: 500
bid: 1.5                        # float; 0 = no paid priority
submitted_by: alice
status: open                    # open | claimed:<daemon_id> | succeeded | failed | expired
evidence_url: ""                # populated by the executor on completion
submitted_at: "2026-04-14T12:00:00+00:00"
```

## Lifecycle

1. A user posts via MCP: `universe action=submit_node_bid node_def_id=... inputs_json=... bid=...`
   (requires `WORKFLOW_PAID_MARKET=on` on the posting host). A YAML
   lands in `bids/<node_bid_id>.yaml`.
2. Commit + push so cross-host daemons can see it:
   `git add bids/<id>.yaml && git commit && git push`.
3. Any daemon with `WORKFLOW_PAID_MARKET=on` whose NodeBidProducer
   runs during its dispatcher cycle will emit a BranchTask for the
   bid. The dispatcher picks it alongside Branch-based work per the
   scoring function.
4. When a daemon's dispatcher claims the BranchTask, the runner
   routes to the NodeBid executor (not the Branch wrapper stream),
   executes the referenced node with **stripped inputs** (no
   universe state), writes `bid_outputs/<id>/output.json` under the
   universe output dir, and updates the bid's `status` +
   `evidence_url`.
5. A settlement record lands at
   `<repo_root>/settlements/<bid_id>__<daemon_id>.yaml` (fields:
   `bid_id`, `daemon_id`, `bid_amount`, `evidence_url`,
   `completed_at`, `success`, `settled: false`).

## LLM-type filter

Dispatcher-side: if a bid declares `required_llm_type` and the
daemon sets `served_llm_type` in its dispatcher_config.yaml, only
matching tasks are eligible. Empty on either side = no filter.

## Node approval requirement

The NodeBid executor refuses to run any node with `approved=False`.
Code nodes are scanned against an **expanded** dangerous-pattern
list (`os.system`, `subprocess`, `eval(`, `exec(`, `__import__`,
`compile`, `open(`, `importlib`, `pickle`, `marshal`) — stricter
than the compile-time check because NodeBid execution has no
universe-state guardrail.

## Race note (v1 limitation)

Two daemons running concurrently on the same `repo_root` may both
claim the same bid via distinct BranchTask claims. v1 accepts this
double-execution; first-push-wins on settlement. Bid atomicity is a
Phase H concern.

## evidence_url

Always a `file://` URL pointing at the output artifact on the
executing host. The settlement layer (future) is responsible for
translating this into an archive URL for cross-host verification.
