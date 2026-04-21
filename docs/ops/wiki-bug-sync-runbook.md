---
title: Wiki bug sync runbook
date: 2026-04-21
status: active
---

# Wiki bug sync runbook

`scripts/wiki_bug_sync.py` + `.github/workflows/wiki-bug-sync.yml`

Polls the wiki every 15 min for new BUG-NNN entries and opens a GitHub Issue
for each. The "detect" half of the auto-detect-and-fix loop.

## How it works

1. GHA runs `wiki_bug_sync.py` every 15 min (cron `*/15 * * * *`).
2. Script calls `wiki action=list` on `https://tinyassets.io/mcp`.
3. Filters promoted entries with `type=bug` and `bug_number > cursor`.
4. For each new bug, calls `wiki action=read` to pull frontmatter (title,
   severity, component), then POSTs a GH Issue via `GITHUB_TOKEN`.
5. Issue title: `[BUG-NNN] <title>`. Labels: `auto-bug` + `severity:<level>`.
6. Commits updated cursor to `.agents/.wiki_bug_sync_cursor` with `[skip ci]`.

## Cursor file

Path: `.agents/.wiki_bug_sync_cursor`  
Contents: a single integer — the last BUG number successfully synced.

The file is committed to the repo. GHA reads HEAD's cursor, runs sync, then
commits the incremented cursor back. This makes the pipeline idempotent:
re-running on the same commit produces no duplicate issues.

**Reset cursor** (re-sync all bugs):

```bash
echo 0 > .agents/.wiki_bug_sync_cursor
git add .agents/.wiki_bug_sync_cursor
git commit -m "chore: reset wiki-bug-sync cursor"
git push
```

**Skip a range** (mark bugs 1–5 as already seen without creating issues):

```bash
echo 5 > .agents/.wiki_bug_sync_cursor
git add .agents/.wiki_bug_sync_cursor
git commit -m "chore: advance wiki-bug-sync cursor to BUG-005"
git push
```

## Manual trigger

Via GitHub Actions UI: Actions → "Wiki bug sync" → Run workflow.

Or via CLI:

```bash
GITHUB_TOKEN=$(gh auth token) python scripts/wiki_bug_sync.py \
    --url https://tinyassets.io/mcp \
    --repo Jonnyton/Workflow
```

## Dry run (preview without creating issues)

```bash
python scripts/wiki_bug_sync.py --dry-run
```

Prints what would be created; does not touch GH or update the cursor.

## Opt-out convention

To prevent a specific BUG-NNN entry from becoming a GH Issue, advance the
cursor past it manually (see "Skip a range" above). There is no per-bug
suppression flag — if you want finer control, close the issue immediately
after it's created.

## Labels

| Wiki severity | GH label |
|---|---|
| `low` | `severity:low` |
| `medium` | `severity:medium` |
| `high` | `severity:high` |
| `blocker` | `severity:blocker` |
| (always) | `auto-bug` |

Labels are created automatically if they don't exist. Color: `d93f0b`
(orange-red) for severity labels, `0075ca` (blue) for `auto-bug`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Workflow runs but no issues created | Cursor already past all bugs | Check cursor value; reset if needed |
| `GITHUB_TOKEN is not set` error | Token not passed | Use `--dry-run` locally; GHA provides token automatically |
| `MCP network error` | Daemon/canary unreachable | Check uptime-canary workflow for P0 status |
| Duplicate issues | Cursor not committed back | Check GHA job logs for "Cursor unchanged" message; re-run |
| Labels not applied | Label create race | Re-run; `_gh_ensure_label` is idempotent on 422 |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All new bugs synced (or none found) |
| 1 | MCP protocol / response-shape error |
| 2 | MCP network error |
| 3 | GitHub API error |
