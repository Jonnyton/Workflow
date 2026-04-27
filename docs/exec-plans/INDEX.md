# Execution Plans Index

Execution plans are for ideas that are too large or risky for a single board
row but should still be driven to a shipped outcome.

## Active

- [active/README.md](active/README.md)
- [active/2026-04-09-runtime-fiction-memory-graph.md](active/2026-04-09-runtime-fiction-memory-graph.md)
- [active/2026-04-15-author-to-daemon-rename.md](active/2026-04-15-author-to-daemon-rename.md) — Phased mass-rename of `author`→`daemon` across ~1,200 Python files, 3 DB tables, user-visible strings. 6-7 dev days across 5 phases with shim-based back-compat.
- [active/2026-04-16-memory-scope-stage-2b.md](active/2026-04-16-memory-scope-stage-2b.md) — `MemoryScope` redesign + write-site threading (5-tier orthogonal composition). ~3 dev sessions, flag-gated behind `WORKFLOW_TIERED_SCOPE`.

## Completed

- [completed/README.md](completed/README.md)
- [completed/2026-04-18-uptime-phase-1a-static-landing.md](completed/2026-04-18-uptime-phase-1a-static-landing.md) — Superseded by `docs/design-notes/2026-04-18-full-platform-architecture.md` (host rejected phased rollout for single-build).
- [completed/2026-04-19-bid-package-promotion.md](completed/2026-04-19-bid-package-promotion.md) — R2 dispatch sequence; bid surface promoted to `workflow/bid/` package (commit 3b83798).
- [completed/2026-04-19-compat-naming-cleanup.md](completed/2026-04-19-compat-naming-cleanup.md) — R3 dispatch sequence; `workflow/compat.py` deleted (commit d7a455e).
- [completed/2026-04-19-track-a-schema-auth-rls.md](completed/2026-04-19-track-a-schema-auth-rls.md) — Track A daemon-economy schema + auth + RLS (commits 98055aa + 029a5ec).
- [completed/2026-04-21-plan-md-migration-diff.md](completed/2026-04-21-plan-md-migration-diff.md) — APPLIED 2026-04-21; all 5 changes written to PLAN.md.
- [completed/2026-04-26-decomp-step-1-prep.md](completed/2026-04-26-decomp-step-1-prep.md) — universe_server.py decomp Step 1 prep (Steps 1-11 LANDED per STATUS).
- [completed/2026-04-26-decomp-step-2-prep.md](completed/2026-04-26-decomp-step-2-prep.md) — Step 2 prep.
- [completed/2026-04-26-decomp-step-3-prep.md](completed/2026-04-26-decomp-step-3-prep.md) — Step 3 prep.
- [completed/2026-04-26-decomp-step-4-prep.md](completed/2026-04-26-decomp-step-4-prep.md) — Step 4 prep.
- [completed/2026-04-26-decomp-step-5-prep.md](completed/2026-04-26-decomp-step-5-prep.md) — Step 5 prep.
- [completed/2026-04-26-decomp-step-6-prep.md](completed/2026-04-26-decomp-step-6-prep.md) — Step 6 prep.
- [completed/2026-04-26-decomp-step-7-prep.md](completed/2026-04-26-decomp-step-7-prep.md) — Step 7 prep.
- [completed/2026-04-26-decomp-step-8-prep.md](completed/2026-04-26-decomp-step-8-prep.md) — Step 8 prep.
- [completed/2026-04-26-decomp-step-9-prep.md](completed/2026-04-26-decomp-step-9-prep.md) — Step 9 prep.
- [completed/2026-04-26-decomp-step-10-prep.md](completed/2026-04-26-decomp-step-10-prep.md) — Step 10 prep.
- [completed/2026-04-26-decomp-step-11-prep.md](completed/2026-04-26-decomp-step-11-prep.md) — Step 11 prep (universe_server.py 14012 → 1771 LOC).

## Legacy Planning References

- [ARCHITECTURE_PLAN.md](../../ARCHITECTURE_PLAN.md)
- [RESTRUCTURE_PLAN.md](../../RESTRUCTURE_PLAN.md)
- [BUILD_PREP.md](../../BUILD_PREP.md)
- [IMPLEMENTATION_SUMMARY_PHASE_3.md](../../IMPLEMENTATION_SUMMARY_PHASE_3.md)
- [PHASE_3_5_6_IMPLEMENTATION.md](../../PHASE_3_5_6_IMPLEMENTATION.md)
- [IMPORT_COMPATIBILITY.md](../../IMPORT_COMPATIBILITY.md)
