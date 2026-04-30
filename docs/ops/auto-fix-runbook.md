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
    -> subscription auth path
    -> opens PR  OR  adds `needs-human` + comment
```

## Auth paths

### Path A - Claude Code OAuth token (primary subscription lane)

Add secret `CLAUDE_CODE_OAUTH_TOKEN`:
1. claude.ai -> Settings -> Claude Code OAuth
2. GitHub -> repo Settings -> Secrets and variables -> Actions -> New repository secret
3. Name: `CLAUDE_CODE_OAUTH_TOKEN`, value: paste token

OAuth tokens do not expire on a fixed schedule but need rotation if revoked.
This is the intended steady-state Claude daemon path because it runs through
the host's Claude subscription. The workflow uses the official
`anthropics/claude-code-action@v1`.

### Path B - Codex subscription lane

Add secret `WORKFLOW_CODEX_AUTH_JSON_B64`:
1. On a host already logged into Codex subscription auth, base64 encode
   `~/.codex/auth.json`.
2. GitHub -> repo Settings -> Secrets and variables -> Actions -> New repository secret
3. Name: `WORKFLOW_CODEX_AUTH_JSON_B64`, value: paste the base64 output

The workflow installs the bundle into `~/.codex/auth.json`, runs
`@openai/codex`, commits any working-tree changes to a branch, and opens a PR
with `Writer family: Codex` / `Required checker family: Claude`.

`OPENAI_API_KEY` is not an approved default daemon writer lane for this project.

### Path C - No subscription auth (graceful-skip)

When no approved subscription-backed writer secret is visible to GitHub
Actions, the workflow:
- Adds `needs-human`, `auto-fix-auth-missing`, and
  `auto-fix-claude-subscription-missing` labels to the issue
- Posts a comment explaining that API-key secrets are intentionally ignored for
  default daemon writers
- Exits 0 so the pipeline stays green

Change attempts begin automatically the moment an approved subscription writer
secret is added and `Deploy prod` completes. That deploy-completion wakeup plus
the scheduled backfill retries `needs-human` requests that have not had a real
writer attempt yet once subscription writer auth is visible, and clears the
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
| `needs-human` added, comment says "no auth" | No approved subscription-backed writer secret visible to GitHub Actions | Add or repair `CLAUDE_CODE_OAUTH_TOKEN` or `WORKFLOW_CODEX_AUTH_JSON_B64` |
| `needs-human` + `auto-fix-auth-missing` persists after adding auth | Deploy-completion wakeup/backfill has not run yet, or the issue already has `auto-fix-attempted` from a real writer failure | Wait for `Deploy prod`/15-minute schedule or manually dispatch the workflow for that issue |
| `auto-fix-claude-subscription-missing` appears | The intended Claude subscription daemon lane is offline/not visible to Actions | Add or repair `CLAUDE_CODE_OAUTH_TOKEN` |
| `auto-fix-provider-exhausted` appears | Selected subscription-backed provider returned quota/rate/capacity exhaustion | Restore subscription capacity or bring another subscription-backed approved writer lane online |
| Claude path rate-limited | Claude action failed and no subscription-backed Codex lane is wired | Issue is marked `needs-human`; do not fall through to API-key billing |
| `needs-human` added, comment says "disabled" | `AUTO_FIX_DISABLED=true` | Set variable to `false` |
| PR opened but tests fail | Writer produced an imperfect change | Review, push additional commits to the branch |
| Workflow not triggering | Issue labeled before workflow existed | Re-label with `auto-change` |
| Concurrent fix attempts racing | Multiple labels applied at once | Concurrency group `auto-fix-<N>` serializes per issue |
