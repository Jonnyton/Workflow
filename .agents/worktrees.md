# Worktree Inventory

Cross-provider append-only log of worktree create/remove events. Run
`python scripts/worktree_status.py` to see current local state.

GitHub alignment:

- A worktree is the local checkout for one Git branch.
- A branch folds back through a GitHub PR, normally draft while blocked or
  under review and ready only when verification gates pass.
- `STATUS.md` owns claims and file collision boundaries; GitHub owns branch,
  commit, PR, and merge history.
- A branch is not memory. `_PURPOSE.md`, this inventory, `STATUS.md`,
  idea files, and draft PR bodies are the durable memory layer.
- Lane state is one of: Active lane, Parked draft lane, Idea/reference only,
  Abandoned/swept.

Format for future entries:

```text
## YYYY-MM-DD HH:MM - <create|remove|sweep> <slug>

- Provider: <provider/session>
- Branch: <branch>
- Lane state: <Active lane | Parked draft lane | Idea/reference only | Abandoned/swept>
- Worktree: <path>
- STATUS/Issue/PR: <row, issue, or PR URL>
- PLAN refs: <relevant PLAN.md modules reviewed>
- Purpose: <one-line>
- _PURPOSE.md: <path or "missing - retrofit before pickup">
- Memory refs: <prior provider memory/artifact paths>
- Related implications: <STATUS rows, pipeline rows, reports, design notes>
- Idea feed refs: <bottom-of-lane ideas/INBOX.md captures to remember, not build authority>
- Ship/abandon: <PR URL, merge SHA, or abandon reason>
```

---

## Initial Seed - 2026-05-02

Generated from `git worktree list --porcelain` during the worktree discipline
handoff. Existing worktrees do not all have `_PURPOSE.md` yet; retrofit on
next touch. Do not bulk edit another provider's active worktree metadata.

### Current Checkout

```text
Workflow                              cursor/claim-check-session-d
```

### Claude-Team / Convention Worktrees

```text
wf-bug045                            fix/bug-045-invoke-branch-spec-plumbing
wf-cohit-prevention                  chore/check-primitive-exists-script
wf-conventions                       chore/agent-memory-ownership-convention
wf-daemon-registry-doc               chore/daemon-registry-design-note
wf-graph-compiler-fix                fix/graph-compiler-event-sink
wf-slice1-sweep                      verify/slice1-sweep
wf-validate-branch-s1                fix/bug-044-validate-branch-stage-1
wf-worktree-discipline               chore/worktree-discipline-convention
wf-worktree-status-script            chore/worktree-status-script
```

### Codex-Owned Worktrees

Codex writes or confirms `_PURPOSE.md` for these on next touch.

```text
wf-arc-b-phase3                      codex/arc-b-phase3
wf-codex-runtime-proof               codex/codex-runtime-proof
wf-connect-copy                      codex/mcp-rollout-acceptance
wf-daemon-souls                      codex/daemon-soul-summon-live
wf-daemon-souls-main                 codex/daemon-soul-summon-live-main
wf-directory-rollout                 codex/librechat-no-login-pack-v2
wf-directory-submissions             codex/directory-submission-boundaries
wf-directory-write-fix               codex/openai-write-proof-docs
wf-f2-spec-retire                    codex/status-loop-ownership
wf-host-discovery-live               codex/host-discoverability-live
wf-hostless-byok-impl                codex/daemon-memory-governor
wf-old-session-consolidation         codex/old-session-consolidation
wf-openai-app-draft-boundary         codex/openai-app-draft-boundary
wf-openai-form-state                 codex/openai-form-state
wf-openai-proof-assets               codex/openai-proof-assets
wf-openai-submission-prep            codex/openai-submission-prep
wf-provider-compliance-conventions   codex/provider-compliance-conventions
wf-reversible-approval-conventions   codex/reversible-approval-conventions
```

### Anomalies For Host / Owner Review

These do not conform to the new `../wf-<purpose-slug>` convention or have
unclear ownership. Keep, rename, or sweep only after owner/host review.

```text
Workflow/.claude/worktrees/agent-a54683e4  worktree-agent-a54683e4
Workflow/origin/main                       codex/bug037-publish-version-topology
Workflow-bug037-live2                      codex/browser-only-scorched-tanks-pwa
Workflow-scorched-pwa-live                 codex/scorched-tanks-browser-pwa-live-main
wf-ci-smoke-8e9de0c                        detached
wf-main-live                               main
wf-review-96                               detached
wf-review-100                              detached
wf-review-104                              detached
wf-review-105                              detached
wf-review-106                              detached
wf-review-107                              detached
wf-review-108                              detached
```

Notes:

- `Workflow/origin/main` is nested inside the main checkout and should not be a
  pattern for future worktrees.
- `Workflow-bug037-live2` and `Workflow-scorched-pwa-live` are sibling-prefix
  variants; new work uses `wf-*`.
- Detached `wf-review-NNN` worktrees need `_PURPOSE.md` with PR number and
  close/merge cleanup condition if retained.

## Sweep - 2026-05-02 Respawn Readiness

- Provider: codex-gpt5-desktop
- Branch: cursor/claim-check-session-d
- Worktree: C:\Users\Jonathan\Projects\Workflow
- STATUS/Issue/PR: Provider-context feed lifecycle scanner row.
- PLAN refs: Harness And Coordination; State And Artifacts; Providers.
- Purpose: Make new sessions see active worktree implications before claiming.
- _PURPOSE.md: retrofitted for `wf-worktree-discipline` and
  `wf-worktree-status-script`.
- Memory refs:
  `.claude/agent-memory/navigator/2026-05-02-worktree-discipline-design.md`.
- Related implications:
  `docs/audits/2026-05-02-provider-context-feed-frontier-research.md`.
- Idea feed refs: `ideas/PIPELINE.md`; `ideas/INBOX.md` bottom-of-lane ideas.
- Ship/abandon: Needs opposite-provider review before provider-context feed land.

## Cross-Refs

- `AGENTS.md` -> "GitHub-Aligned Worktree Discipline".
- `scripts/worktree_status.py` -> current-state scanner.
- `scripts/claim_check.py` -> STATUS.md file-collision scanner.
- `scripts/provider_context_feed.py` -> lifecycle feed for provider memories,
  loose ideas, research artifacts, automation notes, and worktree handoffs at
  claim/plan/build/review/foldback/memory-write checkpoints.
- Claude design memory:
  `.claude/agent-memory/navigator/2026-05-02-worktree-discipline-design.md`.

## Existing Main Entry - 2026-05-02

- 2026-05-02 create `../wf-provider-identity-bridge` on
  `codex/provider-identity-bridge` by codex-gpt5-desktop-identity-rollout;
  STATUS row: Provider identity bridge; PR expected ready after docs checks.

## OpenAI Submission Hardening - 2026-05-02

- 2026-05-02 create `../wf-openai-submission-hardening` on
  `codex/openai-submission-hardening` by
  codex-gpt5-desktop-openai-submission.
- STATUS row: OpenAI app submission hardening.
- Purpose: refresh official OpenAI requirements, audit `/mcp-directory`
  source/tool hints, and refactor packet/docs before final submit approval.
- Ship condition: submission packet is truthful and focused checks pass;
  final OpenAI submit remains action-time host approval.

## OpenAI Live Proof - 2026-05-02

- 2026-05-02 reuse `../wf-openai-submission-hardening` on
  `codex/openai-live-proof` by codex-gpt5-desktop-openai-submission after
  PR #183 merged.
- STATUS row: Directory submissions + first-use evidence.
- Purpose: record live deploy/redaction proof and narrow remaining OpenAI
  submission blockers.
- Ship condition: STATUS/docs show PR #183 deploy proof; ChatGPT web/mobile
  proof and final submit approval remain open.
