# Workflow

**A goal-agnostic engine that runs real multi-step work and patches itself.** Bind it to any domain — a novel, a research program, an invoice queue, a legal filing — and a daemon runs the actual work, notices where it fell short, files that gap back as a patch request, and ships its own fix through evidence gates. Humanity declares shared Goals; a legion of diverse AI-augmented workflows pursues each one in parallel, branches evolve and cross-pollinate, and outputs are ranked by how far they climb each Goal's real-world outcome-gate ladder. `fantasy_daemon/` is the first benchmark branch; the engine is built for everything people collectively care about next. Live at **[tinyassets.io](https://tinyassets.io)** · MCP endpoint **[tinyassets.io/mcp](https://tinyassets.io/mcp)**.

**Built by Jonathan Farnsworth** (jonathan.m.farnsworth@gmail.com, GitHub [@Jonnyton](https://github.com/Jonnyton)) — sole human author; the only co-authors are the project's own AI agents.

## Proof of life

Not a slide deck — the system runs on its own infrastructure and patches itself in public:

- **It ships its own fixes.** The patch loop turns filed gaps into machine-authored PRs through a cross-family writer/checker gate. Self-patches merged to `main` the week of 2026-06-10 (e.g. #1306–#1308). Implemented in [`.github/workflows/auto-fix-bug.yml`](.github/workflows/auto-fix-bug.yml) (~1,900 lines) + [`workflow/bug_investigation.py`](workflow/bug_investigation.py).
- **Canary-gated deploys with receipts.** Live deploy SHA `7d80057` (image `ghcr.io/jonnyton/workflow-daemon:7d80057`), canary bundle **passed**, deployed 2026-06-10 — verifiable in the [deploy run](https://github.com/Jonnyton/Workflow/actions/runs/27296624961) and live via the `get_status` MCP tool.
- **Real throughput.** The supervisor queue has carried 1,500+ tasks to completion (lifetime) across the live universe.
- **~7,800 tests, all offline.** 7,800+ tests across 400+ files run with providers mocked (`_FORCE_MOCK=True`) — no API keys needed (`pip install -e .[dev] && pytest -q`).

Honest caveat (the site says this too): the *user-facing* outcome loop hasn't shipped a real external artifact yet — draft mode is on, OAuth is unwired, `run_count` is 0. What's proven today is the engine, the architecture, and the self-patching loop; the first shipped real-world outcome is the next milestone.

## The flagship: the patch loop

A user's chatbot hits a capability gap → files it as a patch request → a daemon picks it up, drafts a fix, routes it through evidence gates, and ships when the gates are satisfied → the next summon starts smarter. No design committee drew this loop; it was pulled out of `user-sim` sessions where chatbot-personas filed the first patches against the system. Walk it on the site at [/patch-loop](https://tinyassets.io/patch-loop); read the implementation in [`auto-fix-bug.yml`](.github/workflows/auto-fix-bug.yml) + [`workflow/bug_investigation.py`](workflow/bug_investigation.py).

## See the code (one click from here)

The entry path should reach functions, not just docs. Representative core:

- **The MCP surface** every chatbot connects to — [`workflow/universe_server.py`](workflow/universe_server.py) (the `universe` / `extensions` / `goals` / `gates` / `wiki` / `get_status` tools).
- **The daemon run loop** — [`fantasy_daemon/__main__.py`](fantasy_daemon/__main__.py) (LangGraph universe graph, SQLite checkpointer, pause/resume).
- **Branch spec → executable graph** — [`workflow/graph_compiler.py`](workflow/graph_compiler.py) (compiles a declarative branch into a runnable `StateGraph`; approval-gated node execution).
- **The evaluation/gate primitive** — [`workflow/node_eval.py`](workflow/node_eval.py).

## What's strongest here

A coherent, dependency-verified stack (LangGraph / FastMCP / LanceDB / igraph / clingo) wired into a single self-patching engine; design philosophy with teeth (minimal primitives, fork-over-build, commons-first privacy); operational seriousness (canary-gated deploys, deploy receipts tied to source SHA, ~7,800 offline tests); and a system honest enough to file bugs against itself and state in public what it hasn't shipped yet.

## Quick Start (for contributors)

Clone-to-green-tests in ~5 minutes on a clean machine:

```bash
git clone https://github.com/Jonnyton/Workflow.git
cd Workflow
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]
pytest -q                 # 7,800+ tests, offline — no API keys (providers mocked)
ruff check                # lints clean on a fresh clone
```

All tests run offline with `_FORCE_MOCK=True` set in `tests/conftest.py`. No `ANTHROPIC_API_KEY` or similar required for CI or local dev. If any test fails on a clean clone, file an issue — that's a TEST-1 regression.

Cross-platform notes:
- Tested on Windows, macOS, Linux. Paths use `pathlib.Path` — backslashes don't leak into tests.
- Python 3.11+ required (see `pyproject.toml`).
- The tray (`workflow/workflow_tray.py`) is Windows-first; macOS/Linux support is work-in-progress. Platform code is cross-platform.

## Start Here (deeper)

1. Read [STATUS.md](STATUS.md) for live state.
2. Read [PLAN.md](PLAN.md) for architecture and design intent (reads staff-level).
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
