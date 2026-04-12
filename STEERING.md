# STEERING.md — Live Directives

Read this at session start. All tasks and unresolved items live in STATUS.md.

---

## Standing Directives

### Built ≠ Done
Every session: sweep for components that are built but not wired. Check that data flows end-to-end. Never report "done" while the pipeline is disconnected. The full task board is in STATUS.md — work from it, update it in real time.

### Build Toward Future
Don't patch — build the real system. Quick hacks that bypass the architecture create debt. The ingestion + retrieval pipeline is the priority until it works end-to-end: upload → synthesize → index → retrieve → prompt.

### Universal Ingestion
Any file type the user throws at the daemon should be accepted, synthesized into structured worldbuilding docs, and indexed. Raw sources preserved in canon/sources/. Text works today. Image/video/audio plumbing in place.

### Living Documents
PLAN.md and ARCHITECTURE_PLAN.md must reflect reality. When something ships, update the doc. When something is broken, say so. No stale "built, not yet populated" footnotes sitting for sessions.
