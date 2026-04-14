# Phase G Pre-Flight — NodeBid Executor + Paid Market Priority Weights

Planner draft, 2026-04-14. For dev handoff on Phase G rollout row.

Phase G is where the priority function stops being a stub. Phases E–F proved the dispatcher can tier-sort BranchTasks from multiple sources (host queue, goal pool) and actually invoke them. Phase G adds the second execution shape from memo §3.2: the **NodeBid**. A NodeBid is a single-node, cross-universe, bid-priced work unit posted to a repo-root `bids/` directory. Any daemon can pull one, run the specified node in a sandboxed single-node executor, and record an `evidence_url`. The bid price feeds the dispatcher scorer's `bid_term` coefficient — which has existed as a stub since Phase E — making high-value work sort ahead of low-value work within a tier.

This phase ships the structural slot so the market can grow into it. No wallet integration, no crypto. Bids are token-denominated and accounted; the market mechanics work in isolation from any real payment settlement.

## 1. Source material

- `docs/exec-plans/daemon_task_economy_rollout.md` §Phase G (lines 181–207).
- `docs/planning/daemon_task_economy.md` §3.2 NodeBid shape, §4.2 tiered selection, §4.3 priority function.
- `docs/specs/phase_f_preflight.md` §4.1 #2–3 — BranchTaskProducer protocol (landed), GoalPoolProducer (landed). Phase G's NodeBidProducer follows the same pattern.
- Live Phase F code: `workflow/producers/branch_task.py` (BranchTaskProducer protocol + registry), `workflow/producers/goal_pool.py` (concrete producer + pool YAML write), `workflow/subscriptions.py` (subscription durability).
- Reserved stubs already in code:
  - `workflow/branch_tasks.py`: `bid: float = 0.0`, `required_llm_type: str = ""`, `evidence_url: str = ""`, `"paid_bid"` in `VALID_TRIGGER_SOURCES`.
  - `workflow/dispatcher.py`: `accept_paid_bids: bool = False` in `DispatcherConfig`, `"paid_bid": 50.0` in `_DEFAULT_TIER_WEIGHTS`, `bid_coefficient: float = 0.0`, `bid_term = config.bid_coefficient * float(task.bid)` already in `score_task`, `"stubbed (Phase G)"` in `tier_status_map()`.
- PLAN.md "Private chats, public actions" + §Multiplayer Daemon Platform — security model context.
- STATUS.md Phase F R13 note: double-execution accepted for goal pool v1; Phase G bid atomicity is the resolution target.
- STATUS.md Phase E follow-up #1: `queue_cancel` on running tasks returns rejection with no graph-level interrupt — real cancel semantics land in Phase H. NodeBid executor respects this.
- `docs/specs/outcome_gates_phase6.md` — evidence_url shape; NodeBid completion is a gate claim candidate.

## 2. What exists vs. what Phase G adds

**Already live (after Phase F):**
- `bid: float = 0.0`, `required_llm_type: str = ""`, `evidence_url: str = ""` reserved in `BranchTask` dataclass (`workflow/branch_tasks.py:72-89`). Phase G is the first consumer of all three fields.
- `accept_paid_bids: bool = False` in `DispatcherConfig` (`workflow/dispatcher.py:52`). Phase G activates it.
- `"paid_bid": 50.0` in `_DEFAULT_TIER_WEIGHTS` — tier weight constant already set.
- `bid_coefficient: float = 0.0` in `DispatcherConfig` — Phase G sets a non-zero default when paid market is on.
- `bid_term = config.bid_coefficient * float(task.bid)` already in `score_task` (`workflow/dispatcher.py:137`) — wired but always 0 because `bid_coefficient = 0.0`. Phase G activates by setting a non-zero default when flag on.
- `"paid_bid"` in `VALID_TRIGGER_SOURCES` (`workflow/branch_tasks.py:49`).
- `"stubbed (Phase G)"` label in `tier_status_map()` (`workflow/dispatcher.py:86-87`). Phase G replaces this with `"live"`.
- `BranchTaskProducer` protocol + registry (`workflow/producers/branch_task.py`). Phase G's `NodeBidProducer` is another concrete implementation.
- `_try_dispatcher_pick` + `_finalize_claimed_task` in `fantasy_author/__main__.py` — executor wire-up already exists for BranchTasks. Phase G adds a second execution path in the `_finalize_claimed_task` / `_try_dispatcher_pick` code for NodeBid-originated tasks.

**Phase G adds:**
- `workflow/node_bid.py` — `NodeBid` dataclass (separate from `BranchTask`). Repo-root storage shape (`bids/<id>.yaml`). `write_node_bid_post()` + `read_node_bids()` I/O helpers. `validate_node_bid_inputs()` mirrors the pool flat-dict invariant.
- `workflow/executors/node_bid.py` — `execute_node_bid(bid: NodeBid, *, universe_path: Path | None, config: dict | None) -> NodeBidResult`. Sandboxed single-node executor: compile the named node, run it with `bid.inputs`, record output to `evidence_url`. Narrower sandbox than `compile_branch` (one node, one LLM call, no graph state).
- `workflow/producers/node_bid.py` — `NodeBidProducer(BranchTaskProducer)`. Reads `<repo_root>/bids/*.yaml`, filters to bids matching daemon's `required_llm_type`, converts to BranchTask with `trigger_source="paid_bid"`, `bid=bid.bid`. Registered when `WORKFLOW_PAID_MARKET=on`.
- Dispatcher scorer activation: when `WORKFLOW_PAID_MARKET=on`, set `bid_coefficient` default to `1.0` (configurable); replace `"stubbed (Phase G)"` with `"live"` in `tier_status_map()`.
- MCP action `submit_node_bid(node_def_id, required_llm_type, inputs_json, bid)` on the `universe` tool.
- `bids/` repo-root directory + `bids/README.md` conventions.
- Feature flag `WORKFLOW_PAID_MARKET=off` (default). All Phase G behavior behind this flag.
- `dispatcher_config.yaml` addition: `bid_coefficient` field (Phase E already has the Python default; Phase G sets it non-zero in configs when market is on and documents it).

**Explicitly NOT in Phase G:**
- Real wallet/crypto settlement. Bids are numbers; accounting is advisory only.
- Multi-daemon bid atomicity beyond "first claim wins." Phase F R13 accepted this for pool tasks; Phase G narrows it via the `claimed_by` field write on first executor pick, but true atomic exclusion (no double-execution) is not guaranteed without a distributed lock. The claim write reduces double-execution probability to a small race window.
- Bid moderation / flood prevention. v1 has no rate limit on `submit_node_bid`. Revisit when abuse appears.
- Sybil-proof evidence verification. `evidence_url` is self-reported in v1. Coupling to #56 outcome gates is noted (memo §4.3) but the verification design is Phase 6.x scope.
- Cross-host NodeBid discovery. Phase G is local-first (same git repo). Push/pull for cross-host visibility follows the same `git push` hint pattern as `goal_pool/`.
- Per-node sandbox policy beyond the existing `compile_branch` security model. Phase G borrows that model and narrows it; a new node-specific policy layer is future work.

## 3. Risk map

| # | Risk | Blast radius | Reversible? | Mitigation |
|---|------|-------------|-------------|------------|
| R1 | NodeBid executor crashes mid-run, leaves `evidence_url` empty | single node bid, one LLM call | Yes — task marked `failed`, bid YAML stays on disk for retry | `execute_node_bid` wraps in try/except; `_finalize_claimed_task` marks status; no universe state written on crash |
| R2 | `bid_coefficient` non-zero causes BranchTask ordering to diverge from Phase F behavior | per-daemon queue ordering | Yes — set `bid_coefficient=0.0` in config or `WORKFLOW_PAID_MARKET=off` | Default `bid_coefficient=0.0` when flag OFF; activation only when flag ON; all BranchTasks from Phase E/F have `bid=0.0` so `bid_term=0` unless a real bid was submitted |
| R3 | Double-execution on a NodeBid (two daemons both pick the same bid YAML) | wasted LLM call, duplicate `evidence_url` | Mostly — second write to `evidence_url` is idempotent if same node; non-idempotent side effects are node-author's responsibility | `claimed_by` field stamped before execution starts (narrow but non-zero race window); Phase H adds advisory claim atomicity |
| R4 | NodeBid inputs contain universe-path references that contaminate cross-universe state | cross-universe contamination | Yes — same flat-dict invariant as pool inputs | `validate_node_bid_inputs()` rejects `_`-prefixed keys, nested dicts, reserved universe-path keys; identical to `validate_pool_task_inputs()` guard |
| R5 | `required_llm_type` mismatch causes daemon to skip valid bids | zero pool bids surfaced | Yes — bids stay on disk | `NodeBidProducer._accessible_bids()` filters on `required_llm_type`; unmatched bids silently skipped (INFO log); no queue pollution |
| R6 | `bids/` grows unbounded (no TTL, no cleanup) | disk usage | Yes — `git rm bids/<id>.yaml` | v1 ships with no auto-cleanup; host manages via git; document TTL convention in `bids/README.md` |
| R7 | `node_def_id` doesn't resolve on this daemon (node not in registry) | single bid, one skip | Yes — mark `failed` with `error="node_not_available"` | `execute_node_bid` resolves node from registry; raises `CompilerError` (same pattern as Phase D branch not found); `_finalize_claimed_task` marks failed |
| R8 | `WORKFLOW_PAID_MARKET=on` activates `bid_coefficient=1.0`, silently reorders existing queue | queue ordering change on upgrade | Yes — set `bid_coefficient=0.0` explicitly | Document in release notes; default is OFF; coach operators to audit config before flip |

### Reversibility summary

Everything is reversible by `WORKFLOW_PAID_MARKET=off`. Flag default is off. With flag off: `NodeBidProducer` is not registered, `submit_node_bid` returns `{"status": "not_available"}`, `bid_coefficient` defaults to `0.0` (no change to queue ordering), `tier_status_map()["paid_bid"]` stays `"stubbed (Phase G)"`. A merged-but-flag-off Phase G is inert.

Secondary safety: `bids/` directory is in the repo but Phase G ships it empty. A host who receives a bad bid can `git rm` the file locally.

## 4. Implementation contract

### 4.1 Deliverables

1. **`workflow/node_bid.py` — NodeBid dataclass + I/O helpers.**

   ```python
   @dataclass
   class NodeBid:
       node_bid_id: str           # filename stem; e.g. nb_<timestamp>_<random>
       node_def_id: str           # which node to run; slug form
       required_llm_type: str     # hard filter; "" = any
       inputs: dict               # flat dict of primitives; same invariant as pool
       bid: float                 # token price; no floor
       submitted_by: str          # attribution; set from UNIVERSE_SERVER_USER or "host"
       status: str                # open | claimed:<daemon_id> | succeeded | failed | expired
       evidence_url: str          # populated on completion; "" until then
       submitted_at: str          # ISO timestamp
   ```

   - `write_node_bid_post(repo_root, bid_dict) -> Path` — write `<repo_root>/bids/<node_bid_id>.yaml`.
   - `read_node_bids(repo_root) -> list[NodeBid]` — read all `.yaml` files in `<repo_root>/bids/`, skip malformed (log WARN + continue; don't crash producer cycle).
   - `validate_node_bid_inputs(inputs: dict) -> None` — identical invariant to `validate_pool_task_inputs`: reject nested dicts, `_`-prefixed keys, reserved keys. Raises `ValueError` on violation.
   - `claim_node_bid(repo_root, node_bid_id, daemon_id) -> bool` — stamp `status="claimed:<daemon_id>"` in YAML in place. Returns `True` if claim succeeds (previous status was `"open"`), `False` if already claimed. Uses a file-level lock sidecar (`bids/<id>.yaml.lock`) — separate from any universe lock. This is the advisory claim mechanism that reduces (but does not eliminate) R3 double-execution.

2. **`workflow/executors/node_bid.py` — sandboxed single-node executor.**

   ```python
   @dataclass
   class NodeBidResult:
       node_bid_id: str
       status: str           # "succeeded" | "failed"
       output: dict          # node output dict; empty on failure
       evidence_url: str     # artifact path or URL; "" if not produced
       error: str            # "" on success; exception text on failure
   ```

   - `execute_node_bid(bid: NodeBid, *, node_registry, llm_provider) -> NodeBidResult`
     - Resolve `bid.node_def_id` from `node_registry`. Raise `CompilerError` if not found.
     - Compile and invoke the node with `bid.inputs` in a throwaway context (no universe state; no `_run_graph` machinery; no SqliteSaver checkpoint).
     - Write output artifact to a temp path under `<repo_root>/bid_outputs/<node_bid_id>/`. Populate `evidence_url` with the file path.
     - Catch all exceptions; return `NodeBidResult(status="failed", error=str(e))`.
     - Does NOT write any universe-scoped artifact. Cross-universe by construction — no `universe_id` field touched.
   - Security model: inherits `compile_branch`'s trusted-node constraint. Node must be in the registry and must not access universe state via side-channel. Enforcement is honor-system in v1 (same as Phase D opaque-node wrapper). Formal sandbox isolation is future work.

3. **`workflow/producers/node_bid.py` — `NodeBidProducer(BranchTaskProducer)`.**

   - `produce(universe_path, *, subscribed_goals, config) -> list[BranchTask]`
     - Calls `read_node_bids(repo_root)`.
     - Filters: skip `status != "open"`, skip `required_llm_type` mismatch (INFO log), skip on `validate_node_bid_inputs` failure (WARN log).
     - For each accepted bid: emit a `BranchTask` with `trigger_source="paid_bid"`, `bid=bid.bid`, `branch_def_id="<node_bid>" + bid.node_def_id` (special synthetic slug), `goal_id=""`. The dispatcher picks these like any other BranchTask; `_try_dispatcher_pick` routes synthetic `"<node_bid>"` prefix to the NodeBid executor.
   - `name = "node_bid"`. `origin = "paid_bid"`.
   - Registered at module-import time via `register_branch_task_producer(NodeBidProducer())` when `WORKFLOW_PAID_MARKET=on`.
   - Mtime-based cache on `bids/*.yaml` (mirrors GoalPoolProducer's R3 perf guard).

4. **Dispatcher scorer activation (in `workflow/dispatcher.py`).**

   - Replace `"stubbed (Phase G)"` in `tier_status_map()` with `"live" if self.accept_paid_bids else "disabled"`.
   - `bid_coefficient` default in `DispatcherConfig` stays `0.0`. When `WORKFLOW_PAID_MARKET=on`, `_load_dispatcher_config` sets `bid_coefficient=1.0` if the YAML field is absent. This means flipping the flag alone activates bid-weighted sorting.
   - No changes to `score_task` itself — `bid_term = config.bid_coefficient * float(task.bid)` already correct.

5. **`fantasy_author/__main__.py` — NodeBid executor routing in `_try_dispatcher_pick`.**

   - If `claimed.branch_def_id.startswith("<node_bid>")`: extract `node_def_id = claimed.branch_def_id[len("<node_bid>"):]`, look up the original `NodeBid` from `bids/`, call `execute_node_bid`, update `evidence_url` in the YAML.
   - If NOT a NodeBid: existing BranchTask execution path unchanged.
   - `claim_node_bid()` call happens before executor dispatch (advisory claim, reduces double-execution window).
   - `_finalize_claimed_task` unchanged — marks BranchTask queue entry succeeded/failed as before.

6. **MCP action `submit_node_bid` on `universe` tool.**

   - Params: `node_def_id: str`, `required_llm_type: str = ""`, `inputs_json: str`, `bid: float = 0.0`.
   - Validates `inputs_json` parses to flat dict (calls `validate_node_bid_inputs`).
   - Writes bid YAML to `<repo_root>/bids/<node_bid_id>.yaml` via `write_node_bid_post`.
   - Returns `{"status": "ok", "node_bid_id": id, "next_step": "git add bids/<id>.yaml && git commit && git push"}`.
   - Returns `{"status": "not_available", "hint": "WORKFLOW_PAID_MARKET=on required"}` when flag off.
   - Non-host submitters have `bid` clamped to max of their user tier weight (inherits Phase E §4.3 invariant 9 principle across NodeBid path). In v1, anyone may post; `priority_weight` clamping from Phase F is the precedent.

7. **`bids/` repo-root directory.**

   - `bids/README.md` — post format, YAML shape, `required_llm_type` values, `bid` semantics (token-denominated, advisory), TTL convention (posts older than 30 days with `status=open` may be pruned by any subscriber), cross-host visibility (same git push pattern as `goal_pool/`), R3 double-execution note.
   - Commit an empty `.gitkeep` so the directory tracks in git.

8. **Tests** — see §4.4.

9. **Documentation:** `docs/planning/node_bid_conventions.md` — repo-root `bids/` layout, YAML shape, `node_def_id` slug format, `required_llm_type` values, `bid` semantics, TTL. Parallel to `docs/planning/goal_pool_conventions.md`.

### 4.2 Flags

Two flags active in Phase G (in addition to Phase D/E/F flags):

- `WORKFLOW_PAID_MARKET` (new, Phase G) — default `off`. When `on`:
  - `NodeBidProducer` registers at import time.
  - `bid_coefficient` defaults to `1.0` in `_load_dispatcher_config` if not explicitly set.
  - `accept_paid_bids=True` in DispatcherConfig (if not explicitly overridden in YAML).
  - `tier_status_map()["paid_bid"]` returns `"live"`.
  - `submit_node_bid` MCP action is active.
- `WORKFLOW_GOAL_POOL` (Phase F) — `NodeBidProducer` is independent of this flag. A daemon may have goal pool off and paid market on (runs NodeBids only from `bids/`, not from `goal_pool/`).

Flag combination table (Phase D × E × F × G):

| D | E | F | G | Behavior |
|---|---|---|---|----------|
| off | off | off | off | Legacy direct-graph path (existing behavior) |
| on | on | off | off | Dispatcher picks BranchTasks from host queue only; wrapper execution |
| on | on | on | off | + Goal pool subscription + GoalPoolProducer; bid_term=0 always |
| on | on | on | on | Full market: bid-weighted tier sorting + NodeBid execution path |
| on | on | off | on | NodeBid-only market (no goal pool); valid operational mode |

### 4.3 Invariants (must hold across all flag states)

1. **Universe isolation preserved.** `execute_node_bid` writes NO universe-scoped artifact. `NodeBid` has no `universe_id` field. If a node implementation attempts to read/write universe state via side-channel, that is a node-author bug, not a Phase G bug. Defense: node registry enforces trusted-node constraint (same as Phase D opaque-node); universe-scoped I/O in a NodeBid context raises an error at the executor boundary (v1: honor-system; v2: formal sandbox).

2. **Bid-term activation is flag-gated.** `bid_coefficient = 0.0` when `WORKFLOW_PAID_MARKET=off`. Score function unchanged for all existing tests. Verified by running the full Phase E/F test suite with flag off.

3. **Flat-dict inputs invariant.** NodeBid inputs reject nested dicts, `_`-prefixed keys, reserved keys. Identical to `validate_pool_task_inputs`. Enforced at BOTH `submit_node_bid` (post side) and `NodeBidProducer._accessible_bids()` (producer side).

4. **`branch_tasks.json` queue unchanged for non-NodeBid tasks.** NodeBid-originated BranchTask entries use synthetic `branch_def_id` prefix `"<node_bid>"`. Dispatcher routing keyed on this prefix. Existing BranchTasks with real `branch_def_id` values are never mistaken for NodeBids.

5. **`claim_node_bid` is advisory, not exclusive.** Two daemons may claim the same bid in the narrow window between read and write. This is R3 (accepted). The `status` field after claim is `"claimed:<daemon_id>"` — the second claimer overwrites. Phase H claim atomicity resolves this. No data corruption; worst case is wasted execution.

6. **Status transitions are monotonic.** `open → claimed → succeeded | failed | expired`. A bid in `succeeded` or `failed` state is never re-queued. Producer filters on `status == "open"` strictly.

7. **No bid floor.** Zero-bid NodeBids are valid. A daemon with `bid_coefficient=0.0` treats all bids as equal (tier weight only). A daemon with `bid_coefficient=1.0` still picks zero-bid NodeBids if no higher-value work is available (score = tier_weight + 0 + recency + ...). Preserves "leave daemon on → works forever" default.

8. **`required_llm_type = ""` means any LLM accepted.** Blank value is not a rejection filter. `NodeBidProducer` skips only when `bid.required_llm_type != ""` AND doesn't match the daemon's configured LLM type.

9. **Feature flag is import-time, not hot-reloadable.** `register_if_enabled()` runs at `workflow/producers/node_bid.py` module load. Mid-run flag flips are silently ignored (same as Phase D `WORKFLOW_UNIFIED_EXECUTION` and Phase F `WORKFLOW_GOAL_POOL` discipline). Document in release notes.

### 4.4 Test strategy

Target: `tests/test_phase_g_node_bid.py`. Minimum 35 tests.

**NodeBid dataclass + I/O (8 tests):**
- `test_write_and_read_round_trip` — write a bid YAML, read back, fields match.
- `test_filename_stem_matches_id` — `write_node_bid_post` uses `node_bid_id` as filename stem.
- `test_validate_rejects_nested_dict` — `validate_node_bid_inputs` raises on `{"a": {"b": 1}}`.
- `test_validate_rejects_underscore_key` — rejects `{"_private": "x"}`.
- `test_validate_accepts_flat_primitives` — str/int/float/bool/null all accepted.
- `test_claim_node_bid_first_wins` — two sequential claims; first sets `claimed:<id1>`, second returns False.
- `test_read_skips_malformed_yaml` — malformed `.yaml` in `bids/` is skipped with WARN, remaining bids returned.
- `test_read_empty_bids_dir` — empty `bids/` returns `[]`.

**NodeBidProducer (7 tests):**
- `test_producer_emits_open_bids` — `bids/<id>.yaml` with `status=open` → BranchTask emitted with `trigger_source="paid_bid"`.
- `test_producer_skips_claimed_bid` — `status=claimed:other` → not emitted.
- `test_producer_skips_succeeded_bid` — `status=succeeded` → not emitted.
- `test_producer_filters_llm_type_mismatch` — `required_llm_type="claude-opus"` and daemon configured for `"claude-haiku"` → skipped.
- `test_producer_accepts_blank_llm_type` — `required_llm_type=""` accepted by any daemon.
- `test_producer_skips_invalid_inputs` — malformed flat-dict inputs → skipped (WARN log), other bids still returned.
- `test_producer_not_registered_flag_off` — with `WORKFLOW_PAID_MARKET=off`, `NodeBidProducer` absent from registry.

**Executor (6 tests):**
- `test_execute_success` — node resolves, runs with inputs, result has `status="succeeded"`, `evidence_url` populated.
- `test_execute_unknown_node_fails` — unregistered `node_def_id` → `NodeBidResult(status="failed", error=...)`.
- `test_execute_node_raises_marks_failed` — node body raises → result has `status="failed"`.
- `test_execute_no_universe_state_written` — universe dir untouched after executor runs.
- `test_execute_output_written_to_bid_outputs` — output artifact lands in `<repo_root>/bid_outputs/<id>/`.
- `test_execute_result_evidence_url_empty_on_failure` — failed result has `evidence_url=""`.

**Dispatcher scorer (5 tests):**
- `test_bid_term_zero_when_coefficient_zero` — `bid_coefficient=0.0`, `bid=100.0` → `bid_term=0` in score.
- `test_bid_term_scales_with_coefficient` — `bid_coefficient=1.0`, `bid=10.0` → `bid_term=10.0`.
- `test_paid_bid_tier_weight_above_goal_pool` — `paid_bid` tier weight (50.0) > `goal_pool` tier weight (40.0) in `_DEFAULT_TIER_WEIGHTS`.
- `test_tier_status_map_live_flag_on` — `WORKFLOW_PAID_MARKET=on` → `tier_status_map()["paid_bid"] == "live"`.
- `test_tier_status_map_stubbed_flag_off` — `WORKFLOW_PAID_MARKET=off` → `"stubbed"` or `"disabled"` in status.

**MCP submit_node_bid (5 tests):**
- `test_submit_node_bid_flag_off_returns_not_available` — `WORKFLOW_PAID_MARKET=off` → `status=not_available`.
- `test_submit_node_bid_writes_yaml` — flag on, valid inputs → `bids/<id>.yaml` created.
- `test_submit_node_bid_rejects_nested_inputs` — `inputs_json='{"a": {"b": 1}}'` → rejected.
- `test_submit_node_bid_includes_next_step_hint` — response contains `"git add"` hint string.
- `test_submit_node_bid_records_submitted_by` — `posted_by` field in YAML matches `UNIVERSE_SERVER_USER` or `"host"`.

**Flag matrix + invariants (6 tests):**
- `test_flag_g_off_no_bid_producer_in_registry` — `WORKFLOW_PAID_MARKET=off` → `registered_branch_task_producers()` has no `"node_bid"` name.
- `test_flag_g_on_bid_producer_in_registry` — `WORKFLOW_PAID_MARKET=on` → `"node_bid"` present.
- `test_flag_g_off_existing_tasks_score_unchanged` — scoring test with flag off: BranchTasks from Phase E/F have same relative order as before Phase G.
- `test_no_universe_id_in_node_bid` — `NodeBid` dataclass has no `universe_id` field.
- `test_synthetic_branch_def_id_prefix` — BranchTask emitted by NodeBidProducer has `branch_def_id` starting with `"<node_bid>"`.
- `test_double_execution_second_claim_returns_false` — invariant 5: second `claim_node_bid` on same bid returns False (advisory, not exclusive).

**R3 double-execution + R6 TTL convention (3 tests):**
- `test_double_execution_not_blocked` — two simultaneous producer calls both see same open bid (accepted race semantics).
- `test_expired_bid_skipped` — `status=expired` → not emitted by producer.
- `test_read_bids_ignores_gitkeep` — `.gitkeep` in `bids/` does not appear in `read_node_bids()` output.

### 4.5 Rollback plan

1. `WORKFLOW_PAID_MARKET=off` (already the default) — reverts all Phase G behavior with no code change.
2. `git rm bids/*.yaml` if any spam bids land in the pool before the host adds access controls.
3. If `bid_coefficient` non-zero reorders queue unexpectedly: set `bid_coefficient: 0.0` in `<universe>/dispatcher_config.yaml` — restores Phase F ordering without changing any code.
4. If `execute_node_bid` crashes mid-run: BranchTask marked `failed` by `_finalize_claimed_task`; bid YAML remains on disk; daemon continues with next task. No silent swallowing.

### 4.6 Non-goals (explicit)

- **No real payment.** Bids are floats. No crypto, no escrow, no wallet.
- **No anti-double-execution guarantee.** `claim_node_bid` is advisory. True atomicity in Phase H.
- **No evidence verification.** `evidence_url` is self-reported. Sybil-resistance via #56 outcome gates is a future coupling.
- **No cross-host discovery by default.** `bids/` is local. Cross-host requires `git push`.
- **No `queue_cancel` for running NodeBid tasks.** Same Phase E follow-up #1 note: in-flight NodeBids require daemon pause/stop.
- **No per-node sandbox policy.** Executor inherits `compile_branch` trusted-node model; formal sandbox isolation is future work.
- **No TTL enforcement.** `bids/README.md` documents the 30-day convention; host manages pruning manually.

### 4.7 Files touched

| File | Change |
|------|--------|
| `workflow/node_bid.py` | NEW — NodeBid dataclass + I/O + claim helper |
| `workflow/executors/__init__.py` | probably new dir or existing file — add NodeBidResult import if needed |
| `workflow/executors/node_bid.py` | NEW — sandboxed single-node executor |
| `workflow/producers/node_bid.py` | NEW — NodeBidProducer + register_if_enabled |
| `workflow/dispatcher.py` | Replace `"stubbed (Phase G)"` in `tier_status_map`; set `bid_coefficient` default when flag on |
| `fantasy_author/__main__.py` | `_try_dispatcher_pick`: add NodeBid routing branch on `"<node_bid>"` prefix |
| `workflow/universe_server.py` | Add `submit_node_bid` action + dispatch table entry + WRITE_ACTIONS ledger |
| `bids/README.md` | NEW — post format, YAML shape, TTL, R3 note |
| `bids/.gitkeep` | NEW — directory tracking |
| `docs/planning/node_bid_conventions.md` | NEW — public reference |
| `tests/test_phase_g_node_bid.py` | NEW — 35+ tests |
| `STATUS.md` | Phase G row → claimed; add Phase G concerns post-audit |

**Not touched by Phase G:**
- `workflow/branch_tasks.py` — reserved fields already present; no new fields needed.
- `workflow/subscriptions.py` — subscriptions are goal-pool specific; NodeBid path is subscription-free.
- `goal_pool/` — unchanged.

### 4.8 Success criteria (for reviewer)

Phase G passes if and only if:

1. All 35+ Phase G tests pass with `WORKFLOW_PAID_MARKET=off`.
2. All 35+ Phase G tests pass with `WORKFLOW_PAID_MARKET=on`.
3. Full suite passes (Phase E + F + G tests combined) with no regressions.
4. `tier_status_map()["paid_bid"]` returns `"live"` when flag on, `"stubbed (Phase G)"` or `"disabled"` when off.
5. `bid_term` is `0.0` for all Phase E/F BranchTasks (which have `bid=0.0`) regardless of `bid_coefficient`.
6. `execute_node_bid` on a valid node writes an artifact to `bid_outputs/` and populates `evidence_url`.
7. `execute_node_bid` on an unknown `node_def_id` returns `NodeBidResult(status="failed")` without crashing the daemon.
8. `submit_node_bid` with flag off returns `{"status": "not_available"}`.
9. No universe-scoped artifact written by the NodeBid executor path.
10. `workflow/node_bid.py`, `workflow/executors/node_bid.py`, `workflow/producers/node_bid.py` all have test coverage for the flat-dict inputs invariant.

### 4.9 Decision log

| # | Question | Decision | Rationale |
|---|---------|----------|-----------|
| D1 | Separate `NodeBid` dataclass vs reuse `BranchTask` with extra fields? | Separate `NodeBid` in `workflow/node_bid.py` | Memo §3.2 explicitly calls out the structural difference: NodeBid is cross-universe, bid-market, atomic-completion; BranchTask is universe-bound, graph-execution, multi-phase. Merging them hides a real security boundary. |
| D2 | Synthetic `branch_def_id` prefix vs a separate queue for NodeBids? | Synthetic prefix `"<node_bid>"` in BranchTask emitted from producer | Lets the same dispatcher + queue infrastructure handle both shapes with one routing branch in `_try_dispatcher_pick`. Avoids a second queue file and a second lock surface. The prefix is clearly non-slug (angle brackets never appear in real `branch_def_id` slugs). |
| D3 | Async NodeBidProducer? | Sync, v1 | NodeBid I/O is local file reads — milliseconds. Memo §1.1 "async variant for I/O-heavy cross-universe producers" was aimed at HTTP producers. Keep sync; revisit if a producer does HTTP. |
| D4 | `bid_coefficient` default when flag off? | `0.0` (unchanged from Phase E) | Avoids any change to Phase E/F queue ordering when Phase G lands flag-off. Only activates when host explicitly flips `WORKFLOW_PAID_MARKET=on`. |
| D5 | Synthetic prefix format? | `"<node_bid>"` (literal angle-bracket wrapper) | Cannot appear in a real YAML slug (`<` and `>` are not valid in slugs per our naming convention). Unambiguous at a glance. |
| D6 | TTL on `bids/` entries? | Convention only (30-day pruning documented in README) | v1 has no runtime enforcer. Host manages via git. Formal TTL enforcement adds complexity for a problem that won't appear until real market volume lands. |
| D7 | NodeBid executor output location? | `<repo_root>/bid_outputs/<node_bid_id>/` | Repo-root (not universe-scoped). NodeBids are cross-universe; universe scoping would be incorrect. `bid_outputs/` parallel to `goal_pool/` and `bids/` in the repo-root layout convention. |

### 4.10 Phase H atomicity note

Phase G's `claim_node_bid()` reduces the double-execution race window to the time between "read status=open" and "write status=claimed:<id>". This is not zero. The STATUS.md Phase F R13 concern notes Phase G bid atomicity as the resolution target. Phase G reduces but does not eliminate R13 for NodeBids. Phase H (host dashboard + advisory claim semantics for pools) is the committed resolution point. Update R13 concern text in STATUS.md to reflect this after Phase G audit clears.

### 4.11 Outcome gates coupling

NodeBid completion populates `evidence_url`. Memo §4.3 flags this as the outcome-gate sybil-resistance coupling: a paid claim should produce verifiable evidence that the node ran. In v1, `evidence_url` is self-reported and unverified. The coupling to #56 outcome gates is intentional architecture: a future phase where gate claims require evidence receipts will consume the `evidence_url` field already being populated here. No action required in Phase G; document the coupling in `node_bid_conventions.md`.

### 4.12 Open design questions (non-blocking, flag for host input)

These do not block Phase G implementation but sharpen future phases:

1. **Token denomination.** Bids are floats. What token? Project-native points? Project token from STATUS.md paid-requests memory `project_paid_requests_model.md`? In v1 it doesn't matter — any float works. Becomes a question when inter-host settlement lands.
2. **Who decides `required_llm_type` values?** In v1, any string is accepted. A shared vocabulary of type strings (`"claude-opus-4-6"`, `"claude-haiku-4-5"`, etc.) becomes important when cross-host matching is needed. Document recommended values in `node_bid_conventions.md`; defer enforcement.
3. **Bid expiry.** 30-day convention is in `bids/README.md`. Should `NodeBidProducer` auto-expire and write `status=expired`? v1 says no (host manages). Revisit at first reports of stale-bid confusion.
4. **`bid_outputs/` retention.** Output artifacts from executed NodeBids accumulate in `bid_outputs/`. Who cleans them? Same TTL question as `bids/`. Defer to a maintenance-pool task (ironic).

## 5. Handoff

Phase G is unblocked. Phase F landed at `1d02903` (2026-04-14). All Phase F tests passing; reserved stubs confirmed in dispatcher + branch_tasks.

**To claim:** Set Phase G row to `claimed:yourname` in STATUS.md Work table. Write `workflow/node_bid.py` first (dataclass + I/O), then `workflow/executors/node_bid.py` (executor), then `workflow/producers/node_bid.py` (producer + registration), then dispatcher activation in `workflow/dispatcher.py`, then MCP action in `workflow/universe_server.py`, then `_try_dispatcher_pick` routing in `fantasy_author/__main__.py`, then tests.

**Reviewer note:** Run the full Phase E + F + G suite before marking done. Check that `bid_term` is `0.0` for all Phase E/F BranchTasks (bid=0.0 reserved field). Check that `tier_status_map()["paid_bid"]` flips correctly.

**User-sim gate:** User-sim Mission 9 (end-to-end pool test, Phase F flag gate) should land before Phase G live validation. Phase G adds a third flag (`WORKFLOW_PAID_MARKET`) to the three-flag matrix; Mission 10 should test the full D+E+F+G stack with a real submitted NodeBid.
