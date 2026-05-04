---
title: Auto-fix runbook
date: 2026-04-21
status: active
---

# Auto-fix runbook

`.github/workflows/auto-fix-bug.yml`

The second half of the auto-detect-and-fix loop. When `wiki-bug-sync` creates
an `auto-bug`-labeled GH Issue, this workflow fires, attempts a Claude-powered
fix, and either opens a PR or falls back to `needs-human`.

## Full loop

```
wiki file_bug          (chatbot or daemon)
    ↓
wiki-bug-sync          (every 15 min, GHA)
    ↓ creates GH Issue with `auto-bug` label
auto-fix-bug           (on issues.labeled = auto-bug)
    ↓ auth path A/B/C
    ↓ opens PR  OR  adds `needs-human` + comment
```

## Auth paths

### Path A — OAuth token (preferred)

Add secret `CLAUDE_CODE_OAUTH_TOKEN`:
1. claude.ai → Settings → Claude Code OAuth
2. GitHub → repo Settings → Secrets and variables → Actions → New repository secret
3. Name: `CLAUDE_CODE_OAUTH_TOKEN`, value: paste token

OAuth tokens do not expire on a fixed schedule but will need rotation if
revoked. The workflow uses the official `anthropics/claude-code-action@v1`.

### Path B — API key (fallback)

Add secret `ANTHROPIC_API_KEY`:
1. console.anthropic.com → API Keys → Create key
2. GitHub → repo Settings → Secrets and variables → Actions → New repository secret
3. Name: `ANTHROPIC_API_KEY`, value: `sk-ant-...`

Path B is the fallback when `CLAUDE_CODE_OAUTH_TOKEN` is absent or empty.

### Path C — No auth (graceful-skip)

When neither secret is set, the workflow:
- Adds `needs-human` label to the issue
- Posts a comment explaining how to add auth
- Exits 0 (pipeline stays green)

This is the current state until host seeds one of the secrets. The full loop
is valid; fix attempts will begin automatically the moment auth is added.

## Disable toggle

Set repo **variable** (not secret) `AUTO_FIX_DISABLED=true`:
- Settings → Secrets and variables → Actions → Variables tab
- New repository variable: `AUTO_FIX_DISABLED`, value `true`

When disabled, the workflow adds `needs-human` + a comment and exits 0.

To re-enable: set `AUTO_FIX_DISABLED=false` (or delete the variable).

Variable-based toggle preserves secrets — no data loss from toggling.

## Branch and PR naming

- Branch: `auto-bug/issue-<N>` where N = GH issue number
- PR title: `[auto-fix] BUG-NNN: <short title>`
- PR body: `Fixes #N` + auto-fix note

PRs require review before merge — no auto-merge. Host reviews the diff.

## What Claude is asked to do

1. Read AGENTS.md + STATUS.md for project context
2. Reason about the bug from the issue description
3. Find root cause; implement a minimal targeted fix
4. Add/update tests
5. Run ruff on touched files
6. If not confident, add a code comment explaining the uncertainty — never guess

## Manual trigger

Re-label the issue: remove `auto-bug` then re-add it. Or use workflow_dispatch
via the Actions UI (select "Auto-fix bug" workflow → Run workflow).

To retry a specific issue from the CLI:

```bash
gh issue edit <N> --remove-label auto-bug
gh issue edit <N> --add-label auto-bug
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `needs-human` added, comment says "no auth" | Neither secret set | Add `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` (see auth paths) |
| `needs-human` added, comment says "disabled" | `AUTO_FIX_DISABLED=true` | Set variable to `false` |
| PR opened but tests fail | Claude wrote imperfect fix | Review, push additional commits to the branch |
| Workflow not triggering | Issue labeled before workflow existed | Re-label the issue |
| Concurrent fix attempts racing | Multiple labels applied at once | Concurrency group `auto-fix-<N>` serializes per-issue |
