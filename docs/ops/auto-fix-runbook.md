---
title: Auto-fix runbook
date: 2026-04-21
status: active
---

# Auto-fix runbook

`.github/workflows/auto-fix-bug.yml`

Reference free-claimant for the community daemon-request loop. When
`wiki-bug-sync` creates a `daemon-request` GitHub Issue, this workflow attempts
an automated writer change and either opens a PR or falls back to
`needs-human`. BUG pages still also receive `auto-bug` for compatibility.

This workflow is not the whole loop. It is one callable daemon path on the
public request bus. Other paid or volunteer daemons can claim the same class of
request if they satisfy the declared gate, bounty, writer, and checker
requirements.

## Full loop

```text
wiki request artifact  (BUG page, feature/patch plan, docs/ops request)
    ->
wiki-bug-sync          (every 15 min, GHA)
    -> creates GH Issue with `daemon-request` label
Auto-fix change        (on issues.labeled = daemon-request/auto-change/auto-bug)
    -> auth path A/B/C/D
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

### Path B - Codex CLI fallback

Add secret `OPENAI_API_KEY`:
1. platform.openai.com -> API Keys -> Create key
2. GitHub -> repo Settings -> Secrets and variables -> Actions -> New repository secret
3. Name: `OPENAI_API_KEY`, value: `sk-...`

The workflow installs `@openai/codex`, runs `codex login --with-api-key`, then
runs `codex exec` in the GitHub runner workspace. This is the preferred
cross-family fallback when Claude OAuth is rate-limited or unavailable.

### Path C - Claude API key fallback

Add secret `ANTHROPIC_API_KEY`:
1. console.anthropic.com -> API Keys -> Create key
2. GitHub -> repo Settings -> Secrets and variables -> Actions -> New repository secret
3. Name: `ANTHROPIC_API_KEY`, value: `sk-ant-...`

Path C is the same Claude-family fallback when neither Claude OAuth nor Codex
is available.

### Path D - No auth (graceful-skip)

When no approved Claude/Codex writer secret is visible to GitHub Actions, the
workflow:
- Adds `needs-human` and `auto-fix-auth-missing` labels to the issue
- Posts a comment explaining which non-secret auth presence check failed
- Exits 0 so the pipeline stays green

Change attempts begin automatically the moment one approved writer secret is
added. The scheduled backfill retries `needs-human` requests that have not had
a real writer attempt yet once writer auth is visible, and clears the
auth-missing labels before attempting the fix.

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
- PR labels: `writer:claude` requires `checker:codex`; `writer:codex`
  requires `checker:claude`. The `Daemon request policy` PR check enforces
  that same-family machine review is not accepted.

## Gate and bounty requirements

Issues filed by the sync lane include the public daemon-request contract:

- `daemon-request` marks the issue as a public work order.
- `payment:free-ok` means a volunteer daemon may claim it without a paid
  bounty.
- `writer-pool:claude-codex` and `checker:cross-family` describe the machine
  code-change policy.
- `gate-required` means Branch and bounty eligibility come from the relevant
  gate ladder's `branch_requirements` and `bounty_requirements`.

If a paid bounty is attached later, settlement must reference a gate rung and
its evidence requirements. The PR producer should not invent a separate payout
rule in the PR body.

PRs require review before merge. Host reviews the diff.

## What the writer is asked to do

1. Read `AGENTS.md` and `STATUS.md` for project context.
2. Classify the request as bug, patch, feature, docs/ops, branch refinement, or project design.
3. For bugs, find root cause; for non-bugs, identify the smallest useful project change.
4. Add or update tests, docs, or checks appropriate to the risk.
5. Run `ruff` on touched Python files.
6. If not confident, leave a clear comment and exit gracefully. Never guess.

## Manual trigger

Re-label the issue: remove `daemon-request` then re-add it. `auto-change` and
legacy BUG-only `auto-bug` issues are still discovered for compatibility. Or
use workflow_dispatch via the Actions UI:
select "Auto-fix change" -> Run workflow. Explicit re-labels and
`workflow_dispatch` runs retry issues that already carry `auto-fix-attempted`;
scheduled backfill does not, so normal unattended polling cannot churn the same
writer failure forever.

To retry a specific issue from the CLI:

```bash
gh issue edit <N> --remove-label daemon-request
gh issue edit <N> --add-label daemon-request
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `needs-human` added, comment says "no auth" | No approved writer secret visible to GitHub Actions | Add `CLAUDE_CODE_OAUTH_TOKEN`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` |
| `needs-human` + `auto-fix-auth-missing` persists after adding auth | Backfill has not run yet, or the issue already has `auto-fix-attempted` from a real writer failure | Wait for the 15-minute schedule or manually dispatch the workflow for that issue |
| Claude path rate-limited | Claude action failed and `OPENAI_API_KEY` is present | Workflow falls through to Codex CLI |
| `needs-human` added, comment says "disabled" | `AUTO_FIX_DISABLED=true` | Set variable to `false` |
| PR opened but tests fail | Writer produced an imperfect change | Review, push additional commits to the branch |
| Workflow not triggering | Issue labeled before workflow existed | Re-label with `auto-change` |
| Concurrent fix attempts racing | Multiple labels applied at once | Concurrency group `auto-fix-<N>` serializes per issue |
