# STATUS.md Concerns — Post-Session Re-Triage

**Date:** 2026-04-19
**Author:** navigator
**Purpose:** Cross-reference each STATUS.md concern against the last 30 commits (this session's landings). Verdict per concern: **CURRENT** (still live), **RESOLVED** (a commit fixed it), **SUPERSEDED** (a newer concern or design note replaces it). Recommended STATUS.md trim included for host approval.
**Source:** STATUS.md as of commit `fd0f981` + commit log inspection.

---

## Triage table

| # | Concern (STATUS.md verbatim) | Verdict | Rationale + commit refs |
|---|---|---|---|
| 1 | **[2026-04-14] Sporemarch fix (b): verify multi-scene overshoot + dispatch-guard retention in next user-sim.** | **CURRENT** | No live-mission session this round exercised Sporemarch directly. Devin Session 2 was tier-2 install path, not Sporemarch. The Mission 10 retest concern (#2) and this one fold into "next non-Devin user-sim mission" — `docs/audits/2026-04-19-concern-triage.md` already routed it to user-sim with a fold-into-next-mission recommendation. **No action needed; concern stays current.** |
| 2 | **[2026-04-17] Echoes drift-drafted Scene 1/2/3 still in `output/echoes_of_the_cosmos/story.db`; retest fresh universe vs resume.** | **CURRENT** | Same routing as #1 — user-sim mission required, and no Echoes-targeted live mission ran this session. The dirty-state in `output/echoes_of_the_cosmos/` persists. **No action needed.** |
| 3 | **[2026-04-17] 589e1fb REST changes need tests: `/votes/{id}/resolve` forced; `/votes/{id}/ballots` now `{"vote": ...}`.** | **RESOLVED** | Commit `084586f` ("tests: cover 589e1fb vote resolve/ballots REST changes") landed this session. Tests now cover both REST changes. **Recommend: delete this concern from STATUS.md.** |
| 4 | **[2026-04-17] Privacy mode note landed: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`; 3 host Qs remain.** | **CURRENT** (unchanged) | No host answers this session on the 3 Qs. Design note unchanged. The host-Q digest v2 doesn't yet include these Qs (digest covers full-platform §11 + self-auditing + layer-3 rename). **No action needed; consider folding into next host-Q digest update if host wants more on the slate.** |
| 5 | **[2026-04-18] `add_canon_from_path` sensitivity note landed: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`; 3 host asks remain.** | **CURRENT** (unchanged) | Same shape as #4. No host answers this session. **No action needed.** |
| 6 | **[2026-04-18] Claude.ai injection note landed: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`; task #15 still blocked.** | **SUPERSEDED** | Devin Session 2 STRONG PASS on LIVE-F1/F6/F7/F8 (per `docs/audits/user-chat-intelligence/2026-04-19-devin-session-2.md`) validates that the chain of fixes (#15 + #88 + #89 + #95) successfully addressed the underlying chatbot-injection / fabrication bug class. Task #15's "still blocked" status is stale — the live evidence shows the system-layer mitigation is working at the surface that mattered. **Recommend: delete this concern from STATUS.md OR rewrite to "[RESOLVED] Devin Session 2 validates #15+#88+#89+#95 chain end-to-end (3/3 STRONG PASS)".** |
| 7 | **[2026-04-18] `fantasy_daemon/author_server.py` alias risk: snapshot export, not sys.modules rebind; fix there if cross-alias drift appears.** | **CURRENT** (latent — verified safe so far) | This is a fix-on-detection latent concern. The Phase 1 Part 2.5 landing (`7dde417`) did not surface cross-alias drift in the verifier's gate; the snapshot-export pattern hasn't bitten. Concern stays as a watch-item. **Recommend: rewrite to compress: "[2026-04-18] WATCH: `fantasy_daemon/author_server.py` snapshot-export alias may drift; fix on detection."** |
| 8 | **[2026-04-18] Full-platform architecture supersedes phased plan: `docs/design-notes/2026-04-18-full-platform-architecture.md`.** | **CURRENT** (host-decision queue) | No host answers this session on the §11 Qs. The host-Q digest v2 has Q1-Q3 from this note as top-leverage. **No action needed; concern is the meta-pointer to the host-decision queue.** |
| 9 | **[2026-04-19] Navigator follow-up: `docs/design-notes/2026-04-19-modularity-audit.md` flags `universe_server`, discovery, and `daemon_server` seams.** | **SUPERSEDED** | This session's Part B spaghetti audit (`docs/audits/2026-04-19-project-folder-spaghetti.md`) absorbed all 3 codex hotspots from the modularity-audit (cross-ref verified at lines 6, 31, 51, 139). The dispatch sequencing doc (`docs/exec-plans/active/2026-04-19-refactor-dispatch-sequence.md`) names them as R5, R6, R10. The discovery seam now has its own exec-plan (`docs/exec-plans/active/2026-04-19-entry-point-discovery.md`). **Recommend: delete this concern from STATUS.md — fully superseded by the spaghetti audit + dispatch sequence + entry-point exec-plan trio.** |

---

## Summary by verdict

- **CURRENT (5):** #1 (Sporemarch retest), #2 (Echoes retest), #4 (privacy 3 Qs), #5 (add_canon 3 asks), #8 (full-platform 16 Qs). Plus #7 (latent watch-item).
- **RESOLVED (1):** #3 (votes REST tests landed in `084586f`).
- **SUPERSEDED (2):** #6 (Devin Session 2 STRONG PASS validates the fix chain), #9 (spaghetti audit + dispatch sequence + entry-point exec-plan supersede the modularity-audit follow-up).

---

## Recommended STATUS.md trim

This trim is for host approval per `feedback_status_md_host_managed.md` (host curates Concerns; navigator proposes only). If approved, STATUS.md Concerns drops from 9 lines to 6.

**Delete:**
- Concern 3 (votes REST tests — landed `084586f`).
- Concern 6 (Claude.ai injection — Devin Session 2 STRONG PASS supersedes; can also be rewritten as a [RESOLVED] entry if host prefers preserving the trail).
- Concern 9 (modularity-audit follow-up — superseded by Part B + dispatch sequence + entry-point exec-plan).

**Rewrite:**
- Concern 7: tighter wording — "[2026-04-18] WATCH: `fantasy_daemon/author_server.py` snapshot-export alias may drift; fix on detection."

**Keep as-is:**
- Concerns 1, 2, 4, 5, 8.

**Net delta:** 9 lines → 6 lines (3 deletions, 1 rewrite). Concerns block stays well under the STATUS.md 60-line ceiling.

---

## Cross-cutting observations

**Three of nine concerns (33%) reach resolution this session.** That's a healthy throughput — concerns aren't piling up, they're moving through. The session shipped both: code that resolves a code concern (#3 → `084586f`), and validation that resolves a system-trust concern (#6 → Devin Session 2). The third (#9) resolves through documentation — the modularity-audit's followups are now structured execution-ready work.

**Two patterns surface as "still current":**
1. **User-sim concerns (#1, #2)** wait for the next non-Devin live mission — both are routed to fold into that mission's stop conditions per `docs/audits/2026-04-19-concern-triage.md`.
2. **Host-decision concerns (#4, #5, #8)** wait for host async answers — all three should fold into the next host-Q digest update if host wants a broader slate. Currently digest v2 doesn't carry them; recommend digest v3 absorb them once host has cleared current queue (Q4 + Q1-3 minimum).

**One latent concern (#7)** is correctly framed as "watch + fix on detection." No proactive action needed.

---

## What this audit does NOT do

- Does not modify STATUS.md directly. Per `feedback_status_md_host_managed.md`, host curates Concerns; navigator proposes only. Lead surfaces the trim recommendation; host decides.
- Does not promote resolved concerns to a "wins log" or "session summary." Those are activity.log territory.
- Does not re-scope the user-sim missions for #1 + #2 — that's user-sim's call (or lead's dispatch decision when next non-Devin mission lands).
