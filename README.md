# Workflow

Workflow is the primary identity of this project: a general agent-workflow
engine, host-run multiplayer daemon platform, and long-horizon agent lab.
`fantasy_author/` is the first benchmark branch, not the whole product.

This repo already contains substantial architecture and implementation work.
These starter surfaces exist to make that work easier to navigate, extend, and
connect in Obsidian.

## Start Here

1. Read [STATUS.md](STATUS.md) for live state.
2. Read [PLAN.md](PLAN.md) for architecture and design intent.
3. Read [AGENTS.md](AGENTS.md) for process rules.
4. Use [INDEX.md](INDEX.md) as the repo map.
5. Use `python scripts/docview.py` for large Markdown, text, and JSON files
   before any raw whole-file read.
6. Capture loose user ideas in [ideas/INBOX.md](ideas/INBOX.md) or with
   `python scripts/capture_idea.py "Idea summary"`.

## Core Hubs

- [INDEX.md](INDEX.md): top-level repo map and graph hub.
- [VAULT_GUIDE.md](VAULT_GUIDE.md): Obsidian-friendly orientation note.
- [AGENTS.md](AGENTS.md): process truth.
- [PLAN.md](PLAN.md): design truth.
- [STATUS.md](STATUS.md): live-state truth.
- [ideas/INDEX.md](ideas/INDEX.md): idea capture, triage, and shipped ledger.
- [knowledge/INDEX.md](knowledge/INDEX.md): human-readable knowledge map.

## Notes

- The new `knowledge/` docs complement `knowledge.db`; they do not replace it.
- The new `docs/exec-plans/` surface complements existing planning docs like
  `BUILD_PREP.md` and `RESTRUCTURE_PLAN.md`; it does not invalidate them.
- The user may steer multiple live sessions across different providers at once.
  Durable coordination belongs in files, not only in chat.
