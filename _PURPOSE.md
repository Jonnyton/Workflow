# Site Wiki Live Lens

- Created: 2026-05-02 by codex-gpt5-desktop-website.
- Branch: `codex/site-wiki-live-lens`.
- Base ref: `origin/main` at `f82e189`.
- Worktree: `../wf-site-wiki-live-lens`.
- STATUS row: `Site wiki live-lens refactor`.
- Purpose: refine the public website after retiring `/goals` into `/wiki`; keep visitor-facing copy and actions wiki-first while preserving raw MCP `goals` protocol evidence where truthful.
- Files: `STATUS.md`, `_PURPOSE.md`, `WebSite/site/**`.
- Depends: no runtime blocker; `.agents/worktrees.md` append deferred because it overlaps the in-flight worktree-discipline lane.
- PR expectation: push branch and open a draft PR for review; do not direct-push `main`.
- Prior-provider memory refs: chat handoff for `bbee77f Retire goals page into wiki surface`; `WebSite/DEPLOY.md`; `.agents/skills/website-editing/SKILL.md`.
- Related implication refs: `STATUS.md` BUG-034 legacy Goals-router concern; `STATUS.md` Directory submissions; `STATUS.md` Site cert flip.
- Ship condition: `npm run check`, `npm run build`, local desktop/mobile browser verification of `/wiki`, `/goals`, `/catalog`, plus click checks for the changed controls.
- Abandon condition: another provider claims overlapping `WebSite/site/**` or live MCP/wiki direction changes.
- Pickup hints: preserve transparent chat-capture text verbatim; use “work target” for public records, not product-surface “goals.”
