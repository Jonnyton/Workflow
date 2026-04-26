# Conventions

## Files

- Keep `AGENTS.md`, `PLAN.md`, and `STATUS.md` short enough to scan quickly.
- Push durable reasoning into `docs/design-notes/`.
- Push formal accepted decisions into `docs/decisions/`.
- Use `INDEX.md` files to keep note graphs connected.
- Use `docs/exec-plans/` for larger multi-step delivery maps.
- Use `ideas/` for stray ideas that are not yet ready for the work board.

## Naming

- Design notes: `YYYY-MM-DD-topic.md`
- ADRs: `ADR-###-topic.md`
- Specs: `feature-or-change-name.md`
- Execution plans: `YYYY-MM-DD-topic.md` or `topic.md`

## Linking

- Every new durable note should be linked from at least one index page.
- Prefer explicit Markdown links.
- Add sideways links between related notes, not just parent links.

## Verification Language

- `current:` means verified in the current environment.
- `historical:` means true when last checked, not revalidated now.
- `contradicted:` means current evidence says the older claim is no longer true.
- `unknown:` means not yet checked or not confidently reconstructable.

## Large Documents

- Use `python scripts/docview.py` before any raw whole-file read of large
  Markdown, text, or JSON artifacts.
- If `docview.py` says a result is too large, narrow the query again.

## MCP Actions Reference

- New MCP actions and field additions are catalogued in `docs/mcp-actions/`.
- When a chatbot encounters an unexpected response field or a new action verb,
  check `docs/mcp-actions/` before assuming a schema error.
- Index: `docs/mcp-actions/2026-04-25-session-additions.md`

## Gate-branch shape

- Standalone gate branches (`gate_investigation_v1`, `gate_review_v1`, etc.)
  emit a uniform verdict shape so conditional-edge routing works generically
  and chatbots converge on one consumer contract.
- Verdict enum: `pass` / `send_back` / `reject` / `hold` / `rollback`.
- See `docs/conventions/gate-branch-shape.md` for the full contract,
  per-verdict required fields, worked example, and forward-compat plan
  with the unified Evaluator type.
