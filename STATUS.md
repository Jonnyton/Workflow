# Status

Live project state. This file only holds what is currently steering work.

### Size Budget

**Hard ceiling: 4 KB / 60 lines.** If this file exceeds either limit, trim before adding. Commits and `activity.log` are the history — this file is not.

### Lifecycle Rules

- **Concerns** — one line each, ≤150 chars. If detail is needed, put it in the commit message, spec, or `docs/concerns/` and link from here. Delete when resolved — don't mark DONE, just delete. Landing records go in `activity.log`, not here. Accepted design decisions go in PLAN.md, not here. If a concern becomes a Work row, delete the concern.
- **Work** — claimable task board. Position is priority. Each row has **Files** (collision boundary) and **Depends**. Delete rows when landed — commits are the record.
- **Next** — what the next session should do. Replace each session, don't append.

---

## Concerns

- [2026-04-14] Daemon restart needed for #6 guardrails to take effect. Host-gated, tray "Restart All".
- [2026-04-14] Sporemarch fix (b): verify multi-scene overshoot + dispatch-guard retention in Mission 8.
- [2026-04-14] Packaging mirror (`packaging/`) stale vs live `workflow/`. Host: auto-built or hand-maintained?
- [2026-04-14] Phase E: `queue_cancel` lacks graph interrupt (deferred to Phase H); producer-registry test gap.
- [2026-04-14] YAML-staged + SQLite-committed + no git commit on `git_bridge.commit` failure. Platform invariant, deferred.
- [2026-04-14] Phase D: 3 cosmetic doc items fold into docs-pass before `WORKFLOW_UNIFIED_EXECUTION` flag flip.
- [2026-04-14] MCP always-allow toggle: validate selectors in next user-sim mission.
- [2026-04-14] Phase F: flag-flip requires restart (document); `repo_root` walk can find wrong `.git` (set `WORKFLOW_REPO_ROOT`).
- [2026-04-14] Phase G: `exec()` security posture needs `bids/README.md` doc; unapproved-node bid wastes one pick.
- [2026-04-14] Phase G: `_revert_claim` does `git reset --hard`; document before `WORKFLOW_PAID_MARKET` default flip.
- [2026-04-14] Import-time flag discipline (`WORKFLOW_UNIFIED_EXECUTION`, `WORKFLOW_GOAL_POOL`, `WORKFLOW_PAID_MARKET`): document all three in release notes.
- [2026-04-14] Host questions pending on 3 specs — see `docs/planning/daemon_task_economy.md` §6, `docs/specs/outcome_gates_phase6.md` §9, `docs/specs/taskproducer_phase_c.md` §9.
- [2026-04-15] Ruff baseline debt: 60 errors across 16 untouched files (48 auto-fixable); sweep before next flag-flip.

---

## Work

Claim by setting Status to `claimed:yourname`. Files column is the collision boundary. Position is priority.

| Task | Files | Depends | Status | Notes |
|------|-------|---------|--------|-------|
| **#56 Phase 6.2.2** — private-Branch visibility filter | `workflow/author_server.py`, `workflow/universe_server.py` | host direction | blocked:host | Three design paths — pick one before claiming. |
| **Memory-scope defense-in-depth** | `workflow/memory/scoping.py`, `workflow/retrieval/agentic_search.py`, `workflow/retrieval/phase_context.py` | design pass | pending | Tag KG/vector rows with `universe_id`; filter at read-time. |
| **Author → Daemon mass-rename** | `fantasy_author/` module + `author_server.py` | after Phase C-H settles | pending | Drive-by fixes ongoing. Full rename after rollout. |

---

## Next

1. **User-sim Mission 8** — Sporemarch queue drainage (fix a+b) + dispatch routing fix. Validate overshoot concern. Gate `WORKFLOW_UNIFIED_EXECUTION=1` flip (Phase D docs-pass first).
2. **User-sim Mission 9** — end-to-end pool + NodeBid with all flags on (D+E+F+G). Gates `WORKFLOW_GOAL_POOL` + `WORKFLOW_PAID_MARKET` default flips.
