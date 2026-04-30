---
title: Auto-fix runbook
date: 2026-04-21
status: active
---

# Auto-fix runbook

`.github/workflows/auto-fix-bug.yml`

The second half of the community change loop. When `wiki-bug-sync` creates an
`auto-change`-labeled GH Issue, this workflow attempts an automated writer
change and either opens a PR or falls back to `needs-human`. BUG pages still
also receive `auto-bug` for compatibility.

## Full loop

```text
wiki request artifact  (BUG page, feature/patch plan, docs/ops request)
    ->
wiki-bug-sync          (every 15 min, GHA)
    -> creates GH Issue with `auto-change` label
Auto-fix change        (on issues.labeled = auto-change or auto-bug)
    -> auth path A/B/C
    -> opens PR  OR  adds `needs-human` + comment
```

## Auth paths

### Path A - OAuth token (preferred)

Add secret `CLAUDE_CODE_OAUTH_TOKEN`:
1. claude.ai -> Settings -> Claude Code OAuth
2. GitHub -> repo Settings -> Secrets and variables -> Actions -> New repository secret
3. Name: `CLAUDE_CODE_OAUTH_TOKEN`, value: paste token

OAuth tokens do not expire on a fixed schedule but need rotation if revoked.
The workflow uses the official `anthropics/claude-code-action@v1`.

### Path B - API key (fallback)

Add secret `ANTHROPIC_API_KEY`:
1. console.anthropic.com -> API Keys -> Create key
2. GitHub -> repo Settings -> Secrets and variables -> Actions -> New repository secret
3. Name: `ANTHROPIC_API_KEY`, value: `sk-ant-...`

Path B is the fallback when `CLAUDE_CODE_OAUTH_TOKEN` is absent or empty.

### Path C - No auth (graceful-skip)

When neither secret is set, the workflow:
- Adds `needs-human` label to the issue
- Posts a comment explaining how to add writer auth
- Exits 0 so the pipeline stays green

This is the current state until host seeds one of the secrets. The loop stays
valid; change attempts begin automatically the moment auth is added.

## Disable toggle

Set repo variable `AUTO_FIX_DISABLED=true`:
- Settings -> Secrets and variables -> Actions -> Variables tab
- New repository variable: `AUTO_FIX_DISABLED`, value `true`

When disabled, the workflow adds `needs-human` plus a comment and exits 0.

To re-enable: set `AUTO_FIX_DISABLED=false` or delete the variable.

Variable-based toggle preserves secrets; no data loss from toggling.

## Branch and PR naming

- Branch: `auto-change/issue-<N>` where N = GH issue number
- PR title: `[auto-change] <request-id>: <short title>`
- PR body: `Fixes #N` plus change summary

PRs require review before merge. Host reviews the diff.

## What the writer is asked to do

1. Read `AGENTS.md` and `STATUS.md` for project context.
2. Classify the request as bug, patch, feature, docs/ops, branch refinement, or project design.
3. For bugs, find root cause; for non-bugs, identify the smallest useful project change.
4. Add or update tests, docs, or checks appropriate to the risk.
5. Run `ruff` on touched Python files.
6. If not confident, leave a clear comment and exit gracefully. Never guess.

## Manual trigger

Re-label the issue: remove `auto-change` then re-add it. Legacy BUG-only
issues can still use `auto-bug`. Or use workflow_dispatch via the Actions UI:
select "Auto-fix change" -> Run workflow.

To retry a specific issue from the CLI:

```bash
gh issue edit <N> --remove-label auto-change
gh issue edit <N> --add-label auto-change
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `needs-human` added, comment says "no auth" | Neither writer secret set | Add `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` |
| `needs-human` added, comment says "disabled" | `AUTO_FIX_DISABLED=true` | Set variable to `false` |
| PR opened but tests fail | Writer produced an imperfect change | Review, push additional commits to the branch |
| Workflow not triggering | Issue labeled before workflow existed | Re-label with `auto-change` |
| Concurrent fix attempts racing | Multiple labels applied at once | Concurrency group `auto-fix-<N>` serializes per issue |
