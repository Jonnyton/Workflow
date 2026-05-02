# Worktree inventory

Cross-provider append-only log of worktree create/remove events. Run
`python scripts/worktree_status.py` to see current state.

Format per entry:

```
## YYYY-MM-DD HH:MM — <event> <slug>

- Provider: <claude-code | codex-gpt5-desktop | cursor-gpt55 | ...>
- Branch: <branch-name>
- Purpose: <one-line>
- _PURPOSE.md: <path or "missing — retrofit on next-touch">
- Ship/abandon: <PR URL | abandon reason | "active">
```

---

## Initial seed — 2026-05-02

This is the inventory at the moment the convention landed. 41 worktrees
present; 5 are claude-team-active, 17 are Codex's, 18 are anomalies
flagged for host review, plus 1 main mirror.

Existing worktrees do NOT have `_PURPOSE.md` yet — convention is
**retrofit-on-next-touch**, not bulk sweep. Each entry below is a
seed for the per-worktree `_PURPOSE.md` to be written when that
worktree is next visited.

### A. Claude-team-active (write `_PURPOSE.md` on next-touch)

```
wf-bug045              fix/bug-045-invoke-branch-spec-plumbing            BUG-045 plumbing fix; awaits _PURPOSE.md retrofit
wf-conventions         chore/agent-memory-ownership-convention            agent-memory ownership boundary AGENTS.md change
wf-daemon-registry-doc chore/daemon-registry-design-note                  PR #150 (daemon_registry substrate doc) — REMOVE post-merge
wf-graph-compiler-fix  fix/graph-compiler-event-sink                      PR (BUG-038/041 secondary) — REMOVE post-merge
wf-slice1-sweep        verify/slice1-sweep                                Slice 1 verifier broadened-test sweep
wf-validate-branch-s1  fix/bug-044-validate-branch-stage-1                BUG-044 validate_branch Stage 1
wf-cohit-prevention    chore/check-primitive-exists-script                check_primitive_exists.py auto-iterate (dev-2 in-flight)
wf-worktree-discipline chore/worktree-discipline-convention               THIS PR (worktree convention)
```

### B. Codex-owned (lead messages Codex with the convention; Codex writes its own `_PURPOSE.md`)

```
wf-arc-b-phase3                          codex/arc-b-phase3
wf-codex-runtime-proof                   codex/codex-runtime-proof
wf-connect-copy                          codex/mcp-rollout-acceptance
wf-daemon-souls                          codex/daemon-soul-summon-live
wf-daemon-souls-main                     codex/daemon-soul-summon-live-main
wf-directory-rollout                     codex/librechat-no-login-pack-v2
wf-directory-submissions                 codex/directory-submission-boundaries
wf-directory-write-fix                   codex/directory-write-fix
wf-f2-spec-retire                        codex/status-loop-ownership
wf-host-discovery-live                   codex/host-discoverability-live
wf-hostless-byok-impl                    codex/daemon-memory-governor
wf-old-session-consolidation             codex/old-session-consolidation
wf-openai-app-draft-boundary             codex/openai-app-draft-boundary
wf-openai-form-state                     codex/openai-form-state
wf-openai-proof-assets                   codex/openai-proof-assets
wf-openai-submission-prep                codex/openai-submission-prep
wf-provider-compliance-conventions       codex/provider-compliance-conventions
wf-reversible-approval-conventions       codex/reversible-approval-conventions
```

### C. Anomalies flagged for host review

These do NOT match the `wf-<purpose-slug>` naming convention OR have
unclear ownership. Host should sweep or retain-with-purpose-marker.

```
wf-review-96   wf-review-100  wf-review-104  wf-review-105  wf-review-106  wf-review-107  wf-review-108
```
**7 detached-HEAD `wf-review-NNN` worktrees.** Provider unknown; likely
PR-review state from past sessions. Per convention, each should get
`_PURPOSE.md` with `purpose: "PR-NNN review"` + `ship: "review comment
posted"` + `abandon: "PR closed"`. If the PRs are merged/closed, sweep.

```
wf-ci-smoke-8e9de0c
```
**Hash-named, not purpose-named.** Detached HEAD at commit `8e9de0c`.
Violates naming convention. Likely a one-off CI smoke test left behind.
Recommend: sweep unless owner identifies it.

```
Workflow-bug037-live2          codex/browser-only-scorched-tanks-pwa
Workflow-scorched-pwa-live     codex/scorched-tanks-browser-pwa-live-main
```
**Sibling-of-repo prefix variants** — break the convention's `wf-*`
sibling-naming. Should be renamed (`git worktree move`) to `wf-bug037-live2`
and `wf-scorched-pwa-live`, OR absorbed into existing Codex worktrees.

```
Workflow/origin/main           codex/bug037-publish-version-topology
```
**HOST-ACTION CALL-OUT.** Worktree path is *nested inside the main
checkout* at `Workflow/origin/main`. Pairs with the untracked `origin/`
directory at the repo root flagged in the gap-period summary memo.
This is genuinely confusing — a worktree should never live inside its
parent repo. Recommend: host removes this worktree (`git worktree
remove Workflow/origin/main`) and the corresponding untracked `origin/`
dir gets cleaned up.

```
Workflow/.claude/worktrees/agent-a54683e4  worktree-agent-a54683e4
```
**Agent-spawned worktree** under `.claude/worktrees/`. Different
ownership convention (Claude Code agent SDK creates these). Out of
scope for the `wf-*` convention; mentioned for completeness.

```
wf-main-live                   main
```
**Main mirror.** Probably intentional (provides a clean main checkout
for diff/audit purposes without disturbing the cursor session's
HEAD). Should get `_PURPOSE.md` with `purpose: "clean main mirror for
audits"` + `ship: "permanent — never remove"`.

---

## Cross-refs

- AGENTS.md §"Parallel Dispatch" → "Worktree discipline" subsection.
- Design memo: `.claude/agent-memory/navigator/2026-05-02-worktree-discipline-design.md`.
- Scan tool spec (queued for dev-2 after `check_primitive_exists.py` ships): `scripts/worktree_status.py`.
- Sibling tool: `scripts/claim_check.py` (covers STATUS.md Files-collision; orthogonal to this).
