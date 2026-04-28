---
status: historical
---

# Investigation Findings — 2026-04-10

Durable record of findings from this session so future sessions don't
re-investigate.

---

## Sporemarch Cross-Universe Contamination (Root Cause)

**Bug: CLI `--db` default is CWD-relative, not universe-relative.**

The daemon loaded the repo-root `knowledge.db` (449 Ashwater entities) for
all universes because of path resolution bugs in `fantasy_author/__main__.py`.

### 5 bugs to fix

| # | Bug | Location | Fix |
|---|-----|----------|-----|
| 1 | CLI `--db` default is `"story.db"` (CWD = repo root) | `__main__.py:1338` | Change default to `""` or `None` so DaemonController falls through to `Path(universe_path) / "story.db"` |
| 2 | KG path derived from `_db_path.parent`, not universe path | `__main__.py:243` `kg_path = str(Path(self._db_path).parent / "knowledge.db")` | Derive from `_universe_path` instead |
| 3 | Root-level DBs contain stale Ashwater data | `./story.db`, `./knowledge.db`, `./checkpoints.db`, `./lancedb/` | Archive to `archive/stale-ashwater-dbs/` |
| 4 | No universe-boundary assertion at startup | `__main__.py` init | Assert `_db_path` resolves inside `_universe_path` |
| 5 | `--serve` path (line 1242-1244) creates DaemonController WITHOUT `db_path` | `__main__.py:1242` | Verify this falls through correctly |

### Evidence

- `knowledge.db` at repo root is 1.38 MB with 449 entities / 617 edges
  from Ashwater/Aurelith universe.
- `output/default-universe/canon/` has 16 Ashwater canon files.
- Ch1 S1 of Sporemarch is correct (Caro, fungal underground). Ch1 S3
  onward is Ashwater content (Corin, Durnhollow, Ashwater river).
- 106 Ashwater-origin occurrences across 16 Sporemarch output files.

---

## Evaluator Blind Spots (Why 30 Wrong Scenes Accepted)

### 5 missing checks

| # | Missing check | Location | Fix |
|---|--------------|----------|-----|
| 1 | **No premise grounding** — PROGRAM.md never reaches evaluator | `_build_editorial_context` at `commit.py:258-290`, `_read_canon_context` at `orient.py:399-443` (only reads `canon/*.md`, not universe-root `PROGRAM.md`) | Inject PROGRAM.md into editorial context. Also add `premise_grounding` structural check in `structural.py`. |
| 2 | **No character roster validation** — alien characters pass freely | `_check_character_voice` at `structural.py:545-654` | Check characters against universe roster, not just POS distributions |
| 3 | **No setting/world validation** — alien locations pass freely | `canon_breach` at `structural.py:715-785` (Jaccard + negation only catches contradictions, not novel alien elements) | Check locations against universe registry |
| 4 | **Editorial reader sees contaminated context** — KG data flows into canon_facts | `_build_editorial_context` at `commit.py:258-290` | Fix root cause (universe isolation) first |
| 5 | **Foundation review detects but doesn't block** — hard-block only on unsynthesized uploads | `foundation_priority_review.py:24` | Add backpressure from review findings to scene verdicts |

### Why scores were 0.63-0.84

The Ashwater scenes are well-written prose. The structural evaluator grades
prose craft (coherence, readability, pacing), not story correctness. The
scores accurately reflect prose quality — the evaluator has no concept of
"this is the wrong story."

### Minimum viable fix

Add `premise_grounding` structural check:
1. Read PROGRAM.md at eval time
2. Extract key entities from premise
3. Check overlap with scene entities
4. Flag `clearly_wrong` if zero premise entities appear
