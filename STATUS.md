# Status

Live steering only.

### Budget

**Hard ceiling: 4 KB / 60 lines.**

### Standing Principles

**24/7 uptime is the forever rule.** Every surface must work with zero hosts online: tier-1 chatbot, tier-2 host install, tier-3 OSS clone, node discovery/remix/converge, paid-market, moderation. Target architecture: `docs/design-notes/2026-04-18-full-platform-architecture.md`.

**Main is always downloadable.** Broken install is a production bug. See PLAN.md Â§Distribution.

### Lifecycle Rules

- **Concerns** â€” one line, â‰¤150 chars. Delete when resolved.
- **Work** â€” claimable board. Delete when landed.
- **Next** â€” replace each session.

---

## Concerns

- [2026-04-14] Sporemarch fix (b): verify multi-scene overshoot + dispatch-guard retention in next user-sim.
- [2026-04-17] Echoes drift-drafted Scene 1/2/3 still in `output/echoes_of_the_cosmos/story.db`; retest fresh universe vs resume.
- [2026-04-17] 589e1fb REST changes need tests: `/votes/{id}/resolve` forced; `/votes/{id}/ballots` now `{"vote": ...}`.
- [2026-04-17] Privacy mode note landed: `docs/design-notes/2026-04-18-privacy-modes-for-sensitive-workflows.md`; 3 host Qs remain.
- [2026-04-18] `add_canon_from_path` sensitivity note landed: `docs/design-notes/2026-04-18-add-canon-from-path-sensitivity.md`; 3 host asks remain.
- [2026-04-18] Claude.ai injection note landed: `docs/design-notes/2026-04-18-claude-ai-injection-hallucination.md`; task #15 still blocked.
- [2026-04-18] `fantasy_daemon/author_server.py` alias risk: snapshot export, not sys.modules rebind; fix there if cross-alias drift appears.
- [2026-04-18] Full-platform architecture supersedes phased plan: `docs/design-notes/2026-04-18-full-platform-architecture.md`.
- [2026-04-19] Navigator follow-up: `docs/design-notes/2026-04-19-modularity-audit.md` flags `universe_server`, discovery, and `daemon_server` seams.

---

## Work

Claim by setting Status to `claimed:yourname`. Files is the collision boundary.

| Task | Files | Depends | Status | Notes |
|------|-------|---------|--------|-------|
| **Rename A1-C2** | Phase 2-4 rename commits | â€” | pending | Dispatch §5 `docs/exec-plans/active/2026-04-19-author-to-daemon-rename-status.md`. A2-A4 parallel; B1 serial; C1-C2 parallel. |
| **Mission 10 retest** | user-sim; new universe or resume echoes | host scope call | claimed:user | Exercises Fix A barrier + Fix E cleanup end-to-end. |
| **#11 Engine/domain API separation** | `docs/design-notes/2026-04-17-engine-domain-api-separation.md` | rename lands first | host-review | 4 host asks in Â§6. |
| **#19 Memory-scope Stage 2c flag flip** | â€” | 30d clean + zero Stage-1 firings | monitoring | Clock started 2026-04-16. |
| **#25 File rename universe_*â†’workflow_*** | remaining canonical python renames + packaging mirror + shortcut label | â€” | pending | bat name already shipped at 1b29d92; module renames pending. |

---

## Next

1. Rename Phase 2 A1 is the next dispatchable dev commit (unblocks A2-A5 parallel work, then B1, then C1-C2 parallel). ~3-4 dev-days to D2 with 2-dev parallelism.
2. §11 full-platform host Qs (~16 active): Q1 Postgres-canonical, Q7 Fly, Q10 load-test, Q17 co-maintainer, Q29-31 autoresearch DSL, Q32-34 evaluator load-bearing — answer unblocks tracks A-P dispatch.
3. Once §11 answered, break tracks A-P into Work rows. Track O = autoresearch (§32), Track P = evaluation-layers (§33).
4. Layer-3 rename design note (`docs/design-notes/2026-04-19-universe-to-workflow-server-rename.md`) sequences AFTER Phase 1 Part 2 lands — host §5 answers still pending.
5. Subordinated: Mission 10/11 retests, #11 API asks, modularity-audit legacy cleanup (deferred per #73), STEERING.md removal (#27 in flight).
