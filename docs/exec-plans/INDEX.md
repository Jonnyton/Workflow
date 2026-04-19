# Execution Plans Index

Execution plans are for ideas that are too large or risky for a single board
row but should still be driven to a shipped outcome.

## Active

- [active/README.md](active/README.md)
- [active/2026-04-09-runtime-fiction-memory-graph.md](active/2026-04-09-runtime-fiction-memory-graph.md)
- [active/2026-04-15-author-to-daemon-rename.md](active/2026-04-15-author-to-daemon-rename.md) — Phased mass-rename of `author`→`daemon` across ~1,200 Python files, 3 DB tables, user-visible strings. 6-7 dev days across 5 phases with shim-based back-compat.
- [active/2026-04-16-memory-scope-stage-2b.md](active/2026-04-16-memory-scope-stage-2b.md) — `MemoryScope` redesign + write-site threading (5-tier orthogonal composition). ~3 dev sessions, flag-gated behind `WORKFLOW_TIERED_SCOPE`.
- [active/2026-04-18-uptime-phase-1a-static-landing.md](active/2026-04-18-uptime-phase-1a-static-landing.md) — Static landing + read-only catalog browser at tinyassets.io. Deploy locked to GoDaddy shared ($89.99/yr, sunk cost). 8 tasks (~1.75 dev-days + ~0.25 host-day CF config). 3 host Qs before dev dispatch: `/mcp` routing during cut-over, catalog visibility filter, SFTP credentials.

## Completed

- [completed/README.md](completed/README.md)

## Legacy Planning References

- [ARCHITECTURE_PLAN.md](../../ARCHITECTURE_PLAN.md)
- [RESTRUCTURE_PLAN.md](../../RESTRUCTURE_PLAN.md)
- [BUILD_PREP.md](../../BUILD_PREP.md)
- [IMPLEMENTATION_SUMMARY_PHASE_3.md](../../IMPLEMENTATION_SUMMARY_PHASE_3.md)
- [PHASE_3_5_6_IMPLEMENTATION.md](../../PHASE_3_5_6_IMPLEMENTATION.md)
- [IMPORT_COMPATIBILITY.md](../../IMPORT_COMPATIBILITY.md)
