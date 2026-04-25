# Sporemarch C16-S3 Revise-Loop Plateau — Diagnostic

**Date:** 2026-04-19
**Author:** dev (task #52)
**Input:** User-sim Mission 26 Probe A — Sporemarch B1-C16-S3 observed stuck in 30+ revise loop at 0.69-0.71 plateau.
**Method:** activity.log replay + commit.py + graph-topology code walk.
**Scope:** DIAGNOSTIC ONLY. No code changes in this pass. Proposed fix shape at §5; implementation is a separate task.

---

## 1. Evidence from activity.log

`output/sporemarch/activity.log` contains **38 Commit events** for scene_id `sporemarch-B1-C16-S3` between `2026-04-17 03:44:04` and `05:10:10`. That's ~1h 26m of repeated drafting.

Every single event's verdict is `SECOND_DRAFT`. Zero `accept`. Zero `revert`. Score distribution:

| score | count |
|------:|------:|
| 0.69  | 17    |
| 0.70  | 13    |
| 0.71  | 6     |
| 0.72  | 1     |
| 0.73  | 1     |

```
min=0.69  max=0.73  mean=0.698  stdev=0.010
```

Textbook plateau: scores live in a 4-point window over 38 iterations with no trajectory toward either `accept` (score ≥ 0.75 or clean editorial) or `revert` (hard structural failure).

`story.db` is currently empty on sporemarch because task #49's drift-cleanup migration purged all scene_history rows keyed to drift scene_ids (everything in sporemarch was drift-keyed — canon never caught up). All post-hoc analysis here relies on the activity log rather than scene_history.

---

## 2. Verdict-engine shape (walked via `commit.py:_compute_editorial_verdict`)

```
Rule 1 — structural.hard_failure                   → revert
Rule 2 — clearly_wrong concerns AND not            → second_draft
         second_draft_used
Rule 3 — fallthrough                               → accept (never block)
```

`second_draft_used` is read from state at commit-node entry: `is_revision OR state["second_draft_used"]`. The scene graph's `route_after_commit` (scene.py:20) enforces a one-revise cap inside a SINGLE scene graph run:

```python
if state["verdict"] == "accept":          return END
if state["verdict"] == "second_draft"
   and not state["second_draft_used"]:    return "draft"
return END   # revert or second_draft already used
```

That invariant holds — inside one scene graph run, at most two `commit` events can fire (original + one revise). After that, the scene ends regardless of verdict.

---

## 3. Why the loop still runs 38 times

The scene-level cap works. The CHAPTER-level cap does not exist.

Chapter graph walks scenes one at a time via `run_scene` (chapter.py:66). On each call:

- `chapter.py:53` builds a **fresh** scene_state with `"second_draft_used": False`.
- `chapter.py:98` compiles a **new** scene graph and invokes it.
- `chapter.py:153-175` calls `advance_work_target_on_accept` ONLY when `verdict == "accept"`.

So the sequence that produces a 38-iteration plateau is:

1. Universe loop picks C16-S3 via the dispatcher.
2. Chapter's `run_scene` runs the scene graph.
3. Scene graph: commit → SECOND_DRAFT → draft → commit → SECOND_DRAFT → END (scene cap fires).
4. Return to chapter. Verdict is `second_draft`, NOT `accept`, so `advance_work_target_on_accept` is **not called**.
5. `scenes_completed` still increments (chapter.py:139), but the work_target's positional metadata is unchanged.
6. Next dispatcher cycle: same work_target, same scene_id → step 2 again.
7. Fresh `second_draft_used=False` on every re-entry → same terminal SECOND_DRAFT.
8. Infinite loop bounded only by external signals (host pause, tray stop, session end).

Activity-log cadence (~2-4 minutes between scores) is consistent with scene→commit→scene cycles that each go through full draft + eval.

---

## 4. Why the scores plateau instead of diverging

Two hypotheses, not resolvable from log alone:

**H1 — LLM temperature stability.** The draft provider is deterministic enough that re-drafting the same beat sheet from the same state produces prose with nearly identical structural-score and editorial-score signals. Editorial concerns surface the same `clearly_wrong` pattern every time → same `second_draft` verdict. 38 runs × low variance = the plateau.

**H2 — Editorial critic anchoring.** The editorial critic may be keying off a specific structural feature that the draft node cannot fix without external signal (e.g. a missing character appearance, a plot constraint from notes.json). Every revise attempt tries the same shape → same critique.

Both converge on the same operational consequence: **the daemon cannot self-rescue from this state.** No amount of additional iteration is going to escape 0.69-0.71.

---

## 5. Proposed fix shape

Three concentric layers, smallest-to-largest. Recommend implementing all three but they're independently valuable.

### 5.1 Scene-level attempt counter (minimum viable — ~0.5 dev-day)

Add `scene_attempt_count` to work_target metadata. The dispatcher increments it every time a given scene_id is re-dispatched without an `accept` verdict. When count ≥ threshold (suggest **3**, matching `FLAGGING_MAX_CONSECUTIVE_FAILURES`), the dispatcher force-accepts the scene and advances regardless of verdict.

**Signal:** emits `[dispatch_guard] force_accept scene=<id> attempts=<N> final_score=<S>` via the tagged activity_log path (now available per task #50).

**Tradeoff:** force-accepted scenes land in scene_history with `verdict='accept'` but `force_accepted=True` column so retrospective analysis can find them. Daemon continues.

### 5.2 Score-ceiling escape hatch (medium — ~1 dev-day)

Extend `_compute_editorial_verdict` to detect plateau:

```python
if attempt_count >= 3 and structural.aggregate_score >= 0.65:
    # Plateau escape: good enough, stop thrashing
    return "accept", [{"type": "plateau_escape", "score": ..., "attempts": ...}]
```

Threshold 0.65 chosen as "comfortably above the 0.6 low-structural-score floor, below the 0.75 normal-accept implicit bar." C16-S3's mean 0.698 would hit this; true failures below 0.65 still don't.

**Better than force-accept** because the daemon evaluates whether the score itself is acceptable rather than just giving up. Force-accept at 0.30 and plateau-escape at 0.71 shouldn't look identical.

### 5.3 Editorial-concern rotation (larger — ~2 dev-days, scope)

If H2 is correct and the editorial critic keeps surfacing the same `clearly_wrong` concern across 38 iterations, the critic is the anchor. Options: (a) attempt-count-aware prompt that tells the critic "this scene has been revised N times with similar scores, lower your bar", (b) swap the critic provider after N attempts, (c) add a "deadlocked concern" detection that silences a concern once it's been fired >3 times on the same scene_id.

This is a design call with tradeoffs — defer until 5.1 + 5.2 telemetry show whether this is the real issue.

---

## 6. Recommended follow-up tasks

- **(dev, high-priority)** Implement 5.1 scene-attempt-counter dispatch guard. Unblocks Sporemarch resume without masking the root cause. Emits tagged log events so user-sim can verify via `get_recent_events(tag="dispatch_guard")`.
- **(dev, medium-priority)** Implement 5.2 plateau escape. Smart-accept at score ≥ 0.65 after 3+ attempts.
- **(navigator, optional)** Walk 5.3 design tradeoffs. Skip if 5.1+5.2 telemetry shows plateaus are rare and don't need a third fix.
- **(verifier, proactive)** After 5.1 lands, retest Mission 26 Probe A on a re-seeded sporemarch universe. Expected: C16-S3 either accepts or force-accepts within 3 attempts; daemon advances to C16-S4.

---

## 7. Observability shape (dependency on #50 get_recent_events)

Task #50 shipped `get_recent_events(tag=...)` MCP verb but did NOT add tagged call sites. The fix implementations in §5 should emit tagged events at the three key moments:

- **[dispatch_guard]** — scene re-dispatched for the Nth time (N≥3).
- **[overshoot_detected]** — scene count exceeded chapter target (orthogonal to this diagnostic but same log family).
- **[plateau_escape]** — verdict force-accepted due to attempt-count + score threshold.

User-sim can then close the concern-1 loop via:
```
universe(action="get_recent_events", tag="dispatch_guard")
```
and see the structured trail without grepping raw activity.log.

---

## 8. Non-findings

- **Not a #49 drift-cleanup regression.** C16-S3 plateau predates cleanup (log timestamps 2026-04-17 03:44 onward; cleanup ran post-migration). Would have shown the same behavior pre-cleanup.
- **Not a dispatch_execution bug in the narrow sense.** Dispatcher is correctly selecting the work_target each cycle — the work_target itself doesn't get advanced, so the dispatcher keeps doing its job.
- **Not a #B3 NER garbage interaction.** NER filter (task #51) operates on extracted_facts post-draft; doesn't affect verdict.
- **Not cross-universe.** Only observed in sporemarch; echoes_of_the_cosmos showed a different failure mode (scene_count overshoot, concern 1 proper).
