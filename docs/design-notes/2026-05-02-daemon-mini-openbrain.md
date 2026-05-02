# Daemon Mini OpenBrain

## Status

Draft. Captures a design direction from the 2026-05-02 Nate B. Jones/Open Brain
research pass. No OB1 code is copied; this is a Workflow-native adaptation of
the architecture pattern.

## Research Basis

Nate B. Jones surfaces Open Brain through:

- YouTube: https://www.youtube.com/@NateBJones
- Substack: https://natesnewsletter.substack.com/
- GitHub user: https://github.com/NateBJones
- Open Brain repo: https://github.com/NateBJones-Projects/OB1

Open Brain's relevant pattern is:

- one durable memory backend with vector search and an open protocol;
- small MCP tool surface: capture, search, browse recent, stats;
- atomic entries with metadata and embeddings, not giant documents;
- import/migration prompts that turn existing notes into standalone thoughts;
- periodic review prompts that synthesize patterns and open loops;
- wiki/note apps are frontends or import sources, not the memory backend.

The key FAQ distinction is directly relevant to daemon wikis: Open Brain is not
an Obsidian/wiki replacement. The database is where AI memory lives; a visual
wiki can sit on top or alongside it. Long content should be chunked into
retrievable units with metadata linking chunks back to parent documents.

## Workflow Adaptation

Each soul-bearing daemon should get a private "mini OpenBrain" under its daemon
wiki contract. The wiki remains the readable, curated self-model. The mini
brain is the daemon-controlled atomic memory backend.

Recommended shape:

- `daemon_brain_entries` in the canonical Workflow SQLite database, keyed by
  `daemon_id`.
- `daemon_brain_chunks` in the existing LanceDB singleton, also keyed by
  `daemon_id`, `entry_id`, and memory scope.
- `daemon_wikis/<daemon>/pages/...` remains the protected, human-readable wiki.
- `daemon_wikis/<daemon>/raw/signals/...` remains immutable source evidence.
- `daemon_wikis/<daemon>/status/...` records compaction/review/index status.

Do not create a separate Supabase/OpenRouter stack per daemon. Workflow already
has host-local state, LanceDB, and provider routing. The Open Brain idea should
be imported as architecture, not dependency surface.

## Minimal Tools

Expose the smallest daemon-owned tool set:

1. `capture_daemon_thought`
   - appends one atomic thought, decision, failure, preference, or observation;
   - computes a content fingerprint to dedupe;
   - stores metadata: `daemon_id`, `role`, `fixed_llm`, `source_type`,
     `source_id`, `reliability`, `temporal_bounds`, `topic_tags`, `visibility`,
     and `promotion_state`.
2. `search_daemon_brain`
   - semantic search within one daemon by default;
   - cross-daemon search only with explicit borrowed-role or host authority.
3. `list_daemon_thoughts`
   - recent entries, filters, and stats for review/debugging.
4. `promote_daemon_brain_to_wiki`
   - writes durable synthesis into protected wiki pages when repeated atomic
     thoughts become stable policy, self-model changes, claim evidence, or soul
     evolution proposals.

The normal runtime prompt must not include all mini-brain rows. It should
include only:

- the soul;
- the bounded daemon wiki packet;
- a small number of role/query-relevant brain hits;
- memory status/pressure metadata.

## Review Loop

Each daemon should own a regular review ritual, analogous to Open Brain's
weekly review:

1. Cluster recent brain entries by theme.
2. Detect unresolved action items, contradictions, and repeated failure modes.
3. Promote stable lessons into `pages/self-model/current-self.md`,
   `pages/decisions/decision-policy.md`, `claim_proofs/`, or
   `drafts/soul-evolution/`.
4. Mark superseded noisy entries as summarized, not deleted.
5. Run the daemon memory governor after promotion.

This gives the daemon agency over its own memory without letting raw capture
become prompt bloat.

## Fit With Existing Daemon Work

This design extends, rather than replaces, the current slice:

- `workflow/daemon_wiki.py` remains responsible for wiki scaffolding and raw
  signals.
- `workflow/daemon_memory.py` remains responsible for byte caps, compaction,
  and prompt packet bounds.
- future `workflow/daemon_brain.py` would own atomic entries, fingerprints,
  retrieval, and promotion state.
- runtime selection must respect soul identity and fixed LLM pins before using
  any daemon brain.

## Guardrails

- No one flat memory pool. Every entry is daemon-scoped.
- No soul copying. Borrowed role context may retrieve from the role daemon's
  brain only under explicit contract and must credit the executor separately.
- No default public exposure. Daemon brains are host-local unless a future
  explicit sharing policy says otherwise.
- No unbounded tool surface. Prefer four tools; avoid per-table MCP expansion.
- No direct dependency on OB1 code or schema without license review.

## MVP

After #18 clears:

1. Add `workflow/daemon_brain.py` with SQLite entry CRUD, fingerprint dedupe,
   and JSON metadata.
2. Add LanceDB indexing/search through the existing singleton.
3. Extend daemon wiki scaffold with `pages/brain/review.md` and status files.
4. Add focused tests outside current locks.
5. Wire runtime packet builder to include top-k mini-brain hits under the
   existing 8k soul/wiki overhead cap.
