# No-Op Daemon Loop Investigation (#6)

**Author:** planner
**Date:** 2026-04-13
**Status:** scoping for dev

## TL;DR

STATUS.md #6 names the gap "bounded reflection doesn't catch no-op loops."
CLAUDE.md's Name-Collision Awareness section already flagged the root
cause of the *naming*: `_MAX_REFLECTION_PASSES` (now renamed
`_MAX_RETRIEVAL_REFLECTION_PASSES`) is a retrieval re-query bound, not
a loop-level guardrail. There is no "bounded reflection" implementation
that would catch the universe-level worldbuild no-op cycle. The
`orient` node in which that name lives is a scene-loop node and never
runs during worldbuild cycles.

**A universe-level guardrail DID land in c85efa1 this session**
(`_MAX_WORLDBUILD_NOOP_STREAK = 3` in worldbuild.py). It post-dates
the 2026-04-08/09 stall (which is why the 3-day log never showed it
firing). It is **untested against live daemon behavior** and — after
reading the code — covers only the worldbuild path. Three other
classes of no-op loop on the universe graph still have no guardrail.

**Recommendation:** don't re-invent; generalize. Keep the existing
worldbuild guardrail, promote "no-op streak" from a worldbuild-local
counter to a universe-cycle health signal, and give the universe
graph (not individual phase nodes) the authority to self-pause. Two
small dev tasks, one design-light, one test-heavy.

---

## 1. Code map — what "reflection" actually means here

### 1a. "Reflection" in `orient.py` (scene-loop, retrieval only)

**File:** `domains/fantasy_author/phases/orient.py:43-44`, `:501-512`.

```python
_MAX_RETRIEVAL_REFLECTION_PASSES = 2
_MAX_REFLECTION_PASSES = _MAX_RETRIEVAL_REFLECTION_PASSES  # legacy alias
# …
reflection_passes = 0
while reflection_passes < _MAX_RETRIEVAL_REFLECTION_PASSES:
    …
    reflection_passes += 1
```

This bounds how many times the scene-loop `orient` node can re-query
retrieval when it decides the first pass didn't pull enough context.
It is a retrieval-budget cap. It has nothing to do with daemon-loop
no-op detection.

`orient` runs inside the scene subgraph (Book → Chapter → Scene). It
is never invoked during a universe-level worldbuild cycle. Even if
the retrieval reflection bound were more aggressive, it could not see
the worldbuild → "No changes" → worldbuild pattern.

### 1b. "Stuck" at the book level (`diagnose.py`, scene-loop only)

**File:** `domains/fantasy_author/phases/diagnose.py`.

There is a book-level stuck detector that triggers on consecutive
scene reverts inside the scene subgraph. `select_task.py:82`
dispatches to `diagnose` when `health.stuck_level > 3`. This is
scene/book scope — it cannot observe universe-cycle patterns and does
not fire when the universe graph dispatches `worldbuild` as the task.

### 1c. Worldbuild no-op streak guardrail (landed c85efa1)

**File:** `domains/fantasy_author/phases/worldbuild.py:44-50, 180-202`.

```python
_MAX_WORLDBUILD_NOOP_STREAK = 3
# …
noop_this_cycle = signals_acted == 0 and not generated_files
if noop_this_cycle:
    streak = int(health.get("worldbuild_noop_streak", 0)) + 1
else:
    streak = 0
health["worldbuild_noop_streak"] = streak

stuck = noop_this_cycle and streak >= _MAX_WORLDBUILD_NOOP_STREAK
if stuck:
    health["stopped"] = True
    health["idle_reason"] = "worldbuild_stuck"
```

This IS a real universe-level no-op guardrail and matches the
`"No changes"` activity-log signal exactly (`signals_acted == 0 and
not generated_files` is the same condition that triggers the "No
changes" log line in `fantasy_author_original/__main__.py:920-923`).

**But:** it was committed in c85efa1 (this session). It post-dates
the 2026-04-08/09 three-day stall on default-universe, so the absence
of the guardrail's firing in that log history is not evidence that
the guardrail is broken — it simply wasn't present.

**Untested in live:** no integration test covers the full cycle (N
consecutive no-op cycles → state["health"]["stopped"] = True → graph
routes to END). The unit test exists only to the degree that
worldbuild's return value can be asserted in isolation.

**Scope is narrow:** it only fires for worldbuild-specific no-ops. If
the daemon got stuck cycling through `authorial_priority_review →
dispatch_execution → idle → universe_cycle → foundation_priority_review`
(example: no authorial targets, no hard blockers, dispatch chooses
`idle`), the worldbuild guardrail never gets a chance to tick
because worldbuild is never dispatched.

---

## 2. Scheduler map — where the daemon decides the next work

Universe graph (`domains/fantasy_author/graphs/universe.py:432-495`):

```
foundation_priority_review
   ├─ hard blocker active   → dispatch_execution (task=worldbuild, target=upload)
   └─ no hard blocker       → authorial_priority_review
                               → dispatch_execution
                                   ├─ task=run_book
                                   ├─ task=worldbuild
                                   ├─ task=reflect
                                   └─ task=idle
                               → universe_cycle
                                   ├─ health.stopped=True → END
                                   └─ otherwise            → foundation_priority_review (loops)
```

### 2a. Foundation review
**File:** `foundation_priority_review.py`. Pure deterministic scan:
is there an unsynthesized upload? If yes → `stage="foundation"`,
`current_task="worldbuild"`, `intent="synthesize source upload"`. If
no → pass to authorial review. This path can pick `worldbuild`
forever if an upload-synthesis hard priority is stuck (e.g. synthesis
keeps "completing" without clearing the hard priority row).

### 2b. Authorial review
**File:** `authorial_priority_review.py`.
`choose_authorial_targets(universe_path, premise=premise)` ranks work
targets in `work_targets.json`. If `ranked` is empty, returns
`current_task="idle"`. Otherwise picks the first ranked target and
selects intent from `workflow_instructions["next_task"]` (free-form
worldbuild/reflect/write).

### 2c. Dispatch
**File:** `dispatch_execution.py:70-80`. Task is determined by
**intent-string pattern matching**:

```python
if "reflect" in lowered: return "reflect"
if any(token in lowered for token in ("synth", "worldbuild", "reconcile", "compare")):
    return "worldbuild"
if target is not None and target.role == ROLE_NOTES:
    return "worldbuild"
return "run_book"
```

This is the choke point where `worldbuild` gets picked repeatedly.
Once a target with role=ROLE_NOTES is chosen, this dispatcher always
routes to `worldbuild`, regardless of whether the prior N cycles
also routed there and produced nothing.

---

## 3. Why worldbuild → "No changes" → worldbuild cycles

Replay of the 2026-04-08/09 default-universe log against the code:

1. **PROGRAM.md is 84 bytes.** No meaningful premise.
2. `canon/` contains exactly `INDEX.md`, `location-the-gyre.md`,
   `universe.json`. One actual canon doc.
3. `foundation_priority_review`: no unsynthesized uploads active →
   pass to authorial review.
4. `authorial_priority_review`:
   - `ensure_seed_targets(universe_path, premise)` creates a seed
     ROLE_NOTES target if no targets exist.
   - `choose_authorial_targets` returns the seed.
   - `_choose_target` picks it.
   - `_choose_intent` returns `"continue authorial work"` (default
     branch) or `"worldbuild and reconcile notes"` if
     `workflow_instructions["next_task"] == "worldbuild"`.
5. `dispatch_execution._determine_task`: the intent string contains
   `"worldbuild"` OR the target has `role == ROLE_NOTES`. Either
   path → `task="worldbuild"`.
6. `worldbuild` executes. `signals` are empty (nothing upstream
   emitted them; `commit` never ran because no scenes were written).
   Falls to `_generate_canon_documents`:
   - reads `PROGRAM.md` — 84 bytes, mostly empty.
   - if `premise` is truthy it proceeds; if not it returns `[]`.
   - scans canon — one file present → `existing_topics` = one slug.
   - `_identify_gaps` returns the 9 missing topics.
   - Tries LLM for `characters` and `locations` (first two gaps).
   - If LLM returns empty for both (quota, local-LLM failure, empty
     premise → garbage output, etc.), `generated` stays `[]`.
7. `_rebuild_raptor`, version bump → `world_state_version` goes up
   (14 → 14 is actually *not* what the log shows; the log shows
   version incrementing 5→6→7→…→14, so the bump is happening even
   on no-op cycles because `new_version = state["world_state_version"] + 1`
   is unconditional — it's **always** run whether or not signals_acted
   and generated_files are both zero).
8. **Guardrail check (post-c85efa1 code only):** streak ticks to 3
   → `health["stopped"] = True` → universe_cycle → END. **In the
   2026-04-08 run this code did not exist, so stopped was never set.**

### Key behavioral fact

- `world_state_version` bumps unconditionally even on no-op cycles.
  That IS the version number climbing in the activity log (5…14)
  despite zero real work. Future dev work should fix this — version
  should bump when real changes land, not when worldbuild is merely
  invoked. Unconditional bumping makes the state deceptively look
  like progress.
- `activity.log` writes "No changes, version 14" accurately: the
  daemon main-runner correctly detects the no-op and logs it. The
  signal existed; the graph just didn't act on it.

### Why the inspect/get_status view said "phase unknown, accept rate 0.0%"

Inspect's "phase" comes from `status.json` / the activity log;
"accept rate" is derived from scene commits. Default-universe had
zero scene commits (no drafting ever happened), so accept_rate
is division-by-zero → 0.0% or "unknown". "Phase unknown" because
the activity log's latest phase marker is `worldbuild`, but the
daemon never advanced to any writing phase to re-stamp it.

---

## 4. No-op patterns that ARE NOT caught today

Even assuming the worldbuild guardrail now fires correctly, three
other universe-graph paths cycle without detection:

1. **Foundation-priority starvation.** If an upload-synthesis hard
   priority row refuses to clear (e.g. synthesis completes but the
   row's `status` is not transitioned to `ACTIVE_CLEARED`), foundation
   review picks `worldbuild` every cycle with intent "synthesize
   source upload". Worldbuild does synthesis work that does produce a
   `generated_files` entry, so `worldbuild_noop_streak` resets every
   cycle — yet the universe makes no forward progress because the
   hard priority never clears.

2. **Authorial idle loop.** If `authorial_priority_review` returns
   `current_task="idle"` (no ranked targets), dispatch routes to the
   `_idle_node`, which unconditionally sets `health["stopped"] = True`
   and exits. This IS caught. Good. But if a seed target is always
   re-created by `ensure_seed_targets` and always fails the same way,
   the graph cycles `authorial → dispatch → worldbuild → noop → cycle`
   which eventually trips the worldbuild guardrail. OK — covered.

3. **Reflect loop.** If intent matches `"reflect"`, dispatch routes
   to `reflect`. There's no "reflect produced nothing" guardrail.
   Reflect has no streak counter. If it runs forever without producing
   note changes, nothing stops it.

4. **Mixed-phase no-progress.** A subtler pattern: successive cycles
   alternate worldbuild and reflect, each producing token output but
   zero net progress (version bumps, no real facts/promises/notes
   change, accept_rate stays 0.0%). The worldbuild guardrail resets
   on any `generated_files` entry; reflect has no guardrail. A
   cross-phase "no outward progress in N cycles" signal would catch
   this.

---

## 5. Minimal design for a universe-level no-op detector

### Signal source

One observable primitive: **forward progress per cycle**. A cycle
made forward progress when AT LEAST ONE of these is true:

- `total_words` increased (a scene committed).
- `canon_facts_count` increased (new canon truth landed).
- `generated_files` from worldbuild is non-empty.
- `signals_acted` from worldbuild is > 0.
- `notes.json` added or mutated a user-visible note (observable via
  mtime or a cheap hash).
- A hard priority row transitioned state.
- `work_targets.json` had a target lifecycle transition.

### Where it lives

**`universe_cycle`** (`phases/universe_cycle.py:21`) is the correct
home. It already runs once per universe cycle, already reads the
health dict, already sets `health["stopped"]` externally. It has
the full post-cycle view: it sees `total_words`, `total_chapters`,
`world_state_version`, and the latest quality_trace entries.

Promote `worldbuild_noop_streak` into a more general
`cycle_noop_streak` maintained by `universe_cycle`:

```python
# pseudocode for universe_cycle
prev_totals = state.get("_prev_cycle_totals", {})
made_progress = (
    total_words > prev_totals.get("total_words", 0)
    or canon_facts_count > prev_totals.get("canon_facts_count", 0)
    or _last_trace_acted(state)   # generated_files / signals_acted / notes diff
)
streak = 0 if made_progress else int(health.get("cycle_noop_streak", 0)) + 1
health["cycle_noop_streak"] = streak
if streak >= _MAX_CYCLE_NOOP_STREAK:
    health["stopped"] = True
    health["idle_reason"] = f"no progress for {streak} cycles"
    # emit a universe-level note so host sees WHY on inspect
    _emit_host_note(state, f"Self-paused: {streak} no-op cycles.")
```

### Threshold

- `_MAX_CYCLE_NOOP_STREAK = 5` is a reasonable starting point. Three
  is the worldbuild-local bound; universe-cycle wants slightly more
  latitude because worldbuild's "no change" might be cheap to retry
  once or twice while other tasks attempt work.
- The worldbuild-local guardrail (`_MAX_WORLDBUILD_NOOP_STREAK = 3`)
  should remain — it's a fast-path signal specifically for the
  worldbuild hot loop. Redundant guards at two scopes is fine here.

### Action on trip

- **v1: pause.** Set `health["stopped"] = True` and
  `health["idle_reason"]`. Graph routes to END. Host sees the
  pause via `inspect` / `get_status`. This is the same action the
  worldbuild guardrail takes.
- **v1 also: emit an auditable note.** Write a timestamped entry to
  `notes.json` (category: system) so the host sees "daemon paused
  2026-04-13T14:22, reason=no-op streak=5, last task=worldbuild".
  Absence of this was a big reason the 3-day stall wasn't noticed
  earlier.
- **v1.5: ask for direction** (deferred). Instead of silent pause,
  write a note requesting premise / direction input. Out of scope
  for the first ship.

### What it does NOT do

- Does not switch phases or try alternate tasks. That's the daemon's
  core decision-making — adding heuristic "try reflect instead!"
  logic encodes the same kind of scaffolding PLAN.md wants to trend
  away from. Let the daemon self-pause and surface the problem.
- Does not retry with different parameters. Pause + surface.
- Does not interact with the scene-loop `orient` reflection budget
  or the book-level `diagnose` stuck detection. Those are different
  scopes.

### What about the name collision?

`_MAX_REFLECTION_PASSES` in `orient.py:44` is now a legacy alias
(`_MAX_REFLECTION_PASSES = _MAX_RETRIEVAL_REFLECTION_PASSES`). It
should be **deleted** once callers are audited, per CLAUDE.md's
"Qualified names beat bare ones" rule. Deleting it prevents a
future dev from confusing the retrieval bound with the universe
guardrail.

---

## 6. Concrete dev tasks

### Task A: generalize the no-op guardrail to universe scope

**Scope:** ~30-60 lines of code in `phases/universe_cycle.py`, plus
tests.

- Add `_MAX_CYCLE_NOOP_STREAK = 5` (module-level constant).
- In `universe_cycle`, detect forward progress between `state` and
  `state["_prev_cycle_totals"]` (new field, written by universe_cycle
  each tick). Check total_words, canon_facts_count, the latest
  quality_trace entry's `generated_files`/`signals_acted`, and notes
  mtime.
- If no progress, bump `health["cycle_noop_streak"]` and check the
  threshold. If tripped, set `health["stopped"] = True`,
  `health["idle_reason"]`, and append a system note.
- Preserve the existing worldbuild-local `_MAX_WORLDBUILD_NOOP_STREAK`
  — it's a faster trigger for the specific case.

**Tests:**

- 5 consecutive no-op cycles → `health["stopped"]` is True after the
  5th cycle, graph routes to END.
- Progress on cycle 3 resets streak; cycle 4 starts fresh.
- System note is written with reason + last task.
- Interaction with existing worldbuild guardrail: worldbuild's
  3-streak fires first if only worldbuild runs; universe-cycle
  5-streak fires when tasks vary but no progress happens.

**Files touched:**
- `domains/fantasy_author/phases/universe_cycle.py`
- `tests/test_universe_cycle_noop_guardrail.py` (new)

**Dependencies:** none. Can start immediately.

**Risk:** low. Additive to a well-bounded node; existing guardrail
stays in place as a backstop if the new one has bugs.

### Task B: verify the existing worldbuild guardrail with a live/
integration test

**Scope:** one integration test. Existing unit tests cover the
condition logic in isolation, but nothing asserts that the universe
graph actually routes to END after N no-op cycles.

- Compile the universe graph with a worldbuild node stubbed to
  return the "no changes" shape.
- Invoke the graph from `foundation_priority_review` entry.
- Assert: after `_MAX_WORLDBUILD_NOOP_STREAK` iterations,
  `should_continue_universe` returns `"end"` and the graph exits.
- Assert: `health["idle_reason"]` is set.

**Files touched:**
- `tests/test_universe_graph_worldbuild_guardrail.py` (new)

**Dependencies:** none. Can run in parallel with Task A.

**Risk:** low. Pure test; reveals any state-plumbing bug in the
existing guardrail before Task A layers on top.

### Task C (cleanup, low priority): kill the `_MAX_REFLECTION_PASSES` alias

**Scope:** ~5 lines in `phases/orient.py`.

- Delete `_MAX_REFLECTION_PASSES = _MAX_RETRIEVAL_REFLECTION_PASSES`.
- Grep callers; update any that still use the bare name.
- Update CLAUDE.md Name-Collision Awareness section's example once
  this lands.

**Files touched:**
- `domains/fantasy_author/phases/orient.py`
- any callers identified by grep (expected: zero, per CLAUDE.md it
  was renamed this session).
- `CLAUDE.md` (example update).

**Dependencies:** none. Can be bundled with Task A or sent to a
second dev for parallel.

**Risk:** very low. Pure rename-deletion.

### Task D (stretch, deferred): fix the unconditional
`world_state_version` bump in worldbuild

Out of scope for this investigation but surfaces here because it
shows up in the log: `world_state_version` climbs on no-op cycles,
which is misleading telemetry. Consider bumping only when
`signals_acted > 0 or generated_files` is true. File as a separate
concern; don't bundle with Tasks A-C.

---

## 7. Parallelization

| Task | Depends on | Parallel-safe with |
|------|-----------|--------------------|
| A: universe-cycle guardrail | — | B, C |
| B: worldbuild-guardrail integration test | — | A, C |
| C: kill alias | — | A, B |
| D: version-bump fix (deferred) | — | — |

All three near-term tasks are parallel-safe. Task A is the core
delivery for #6. Tasks B and C are hygiene that lowers cost of future
work.

---

## 8. Risks

- **Risk:** the worldbuild guardrail's `health` dict propagates
  through the state graph, but foundation/authorial review return
  node-updates that do NOT include `health`. LangGraph's default
  reducer for a non-Annotated dict field is full replacement — but
  only when the node includes the key in its return. Because those
  reviewers don't return `health`, the prior `health` value is
  preserved. This SHOULD be fine. Task B should confirm by asserting
  `health["worldbuild_noop_streak"]` value across two cycles is
  monotonic.
- **Risk:** `_prev_cycle_totals` introduces a new state field not in
  `UniverseState` TypedDict. Either add it to the TypedDict
  (preferred, documented) or store it inside `health`
  (less clean but avoids schema churn). Recommend adding to
  TypedDict as an internal field — matches the `_universe_path` /
  `_db_path` / `_kg_path` underscore convention already there.
- **Risk:** progress signal false positives (a tiny worldbuild LLM
  call returns a 1-byte file, marking "progress" despite effectively
  no work). Accept this. The worldbuild guardrail's narrower trigger
  catches it. Universe-cycle is a slower backstop.
- **Risk:** integration test flakiness. Avoid by stubbing worldbuild
  with a deterministic no-op return shape in Task B.
- **Risk:** surprises in live runs. Once Task A ships, watch a live
  sporemarch or fresh universe for one full cycle to confirm the
  guardrail fires correctly on induced no-op. Not part of the tests;
  part of the ship-verification ritual.

---

## 9. Relation to STATUS.md claims

STATUS.md header line about #6: *"default-universe cycling worldbuild
→ 'No changes' for 3 days. Bounded reflection in orient should have
caught this — it did not."*

Correction for STATUS.md once Task A lands: "Bounded reflection in
orient was a retrieval-budget cap in the scene loop — it could not
have caught this. A real universe-level no-op guardrail landed
worldbuild-local in c85efa1 and was promoted to universe_cycle scope
in $(commit-hash)." Planner recommends updating the Concern to
reflect that the original framing (bounded reflection = loop
guardrail) was a name collision, not a broken component.
