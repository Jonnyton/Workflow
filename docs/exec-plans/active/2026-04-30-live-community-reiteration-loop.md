# Live Community Reiteration Loop

Status: active scoping, claimed by `codex-gpt5-desktop` on 2026-04-30.

## Goal

Make the community-driven change loop real and observable:

```text
community change request
  (bug, patch, feature, docs/ops, branch refinement, project-design change)
  -> community-authored triage / investigation / planning branch
  -> change packet (patch packet, feature spec, migration plan, etc.)
  -> implementation branch or PR
  -> CI + review gates
  -> merge + deploy
  -> live user-surface observation
  -> wiki/GitHub status update or re-entry into the loop
```

Acceptance is uptime-shaped once the loop is built: users must be able to
check the public website from a phone while this local computer is off and see
whether the loop is running, blocked, or recovering from real community
interactions. Website rendering is a separate preview-approved UI slice; this
plan owns the cloud-visible loop status contract and alarm path.

This is wiring and proof work, not a branch redesign. Branches remain
community-authored and remixable. Platform code should only provide the
smallest primitives that let those branches run, hand off, and be observed.
BUG-044 is the first live item because it is available and concrete; it is not
the boundary of the loop.

## Current Evidence

Freshness stamp: 2026-04-30, `wf-main-live`, local code + live MCP + public
GitHub API.

- PLAN.md already makes this the intended shape: minimal primitives,
  community-build over platform-build, commons-first architecture, GitHub as
  public shared state, Goals above Branches, and user/provider parity.
- Host reframe on 2026-04-30: the loop is for all project evolution, not just
  bugs. Bugs, patch requests, feature requests, docs/ops changes, branch
  refinements, and project-design changes use the same community-driven path.
- Host reframe on 2026-04-30: public loop requests are daemon requests, not
  one workflow's private queue. Paid or free daemons may claim them if they
  meet the declared gate and bounty requirements. Code-change writers are
  restricted to Claude/Codex, with an opposite-family checker.
- Live MCP has Goal `f10caea2e437` ("Turn a Workflow bug into a patch packet")
  with user-made Branch `0731a3122bd4` (`bug_to_patch_packet_v1`) bound.
- Live MCP has Goal `4ff5862cc26d` ("Route a patch request through
  investigation, PR, release, and live observation") bound to user-made Branch
  `fd5c66b1d87d` (`change_loop_v1`) after host approval on 2026-04-30.
- Rendered ChatGPT UI proof on 2026-04-30 confirmed read-only through the
  Workflow connector: Goal `4ff5862cc26d` exists, includes branch
  `fd5c66b1d87d`, branch name is `change_loop_v1`, wiki `BUG-044` exists, and
  no changes were made. Screenshot artifact:
  `output/chatgpt-loop-proof-main.png`.
- Live run `020a76ae0530478e` of `change_loop_v1` failed at compile time:
  `ValueError: 'investigation_gate' is already being used as a state key`.
  This produced wiki `BUG-044`.
- `scripts/wiki_bug_sync.py --dry-run --url https://tinyassets.io/mcp --repo
  Jonnyton/Workflow` detected `BUG-044` as the next sync item and would create
  issue `[BUG-044] ...` with labels `auto-bug` and `severity:major`.
  The first local Windows run exposed a console encoding bug in the script's
  Unicode arrow output; fixed in this slice by using ASCII `->`.
- Live MCP queue is empty; no `bug_investigation` request is pending.
- Local code confirms `_wiki_file_bug` still returns immediately after
  `_append_wiki_log`; it does not call `_maybe_enqueue_investigation`.
- `tests/test_bug_investigation_wiring.py` still has the integration test
  skipped for the unwired call site.
- `python -m pytest tests/test_bug_investigation_wiring.py
  tests/test_bug_investigation_dispatcher.py
  tests/test_bug_investigation_flow.py -q` passes: 55 passed, 1 skipped.
- Public GitHub API shows `wiki-bug-sync` exists. Run 159 synced BUG-038
  through BUG-043 into `auto-bug` issues, but did not trigger
  `auto-fix-bug`; GitHub intentionally suppresses most follow-on workflows
  caused by `GITHUB_TOKEN` events. BUG-044 was not yet synced by schedule at
  2026-04-30T02:53Z.
- `.github/workflows/auto-fix-bug.yml` is being patched to backfill pending
  `auto-bug` issues on `workflow_run`, schedule, manual dispatch, and workflow
  file pushes instead of relying only on `issues:labeled`. The same patch
  updates stale Claude action inputs to the supported v1 input surface.
- Live GitHub Actions run 1 of `Auto-fix bug` on commit `1251c8e` succeeded
  at 2026-04-30T03:05Z. It processed issues #88, #87, and #86 and marked each
  `needs-human` with a bot comment because `CLAUDE_CODE_OAUTH_TOKEN` was not
  visible to GitHub Actions. API-key billing lanes are not approved cloud
  daemon writer auth; cloud daemons run through host subscriptions only.
- CI `actionlint` on commit `1251c8e` failed because push-to-main linted every
  workflow and surfaced pre-existing shellcheck findings in unrelated workflow
  files. The follow-up patch narrows push linting to changed workflow files;
  manual dispatch remains the all-workflows audit.
- `wiki-bug-sync` still did not fire through 2026-04-30T03:20Z, so BUG-044
  was manually bridged to GitHub issue #89 through the GitHub connector and
  labeled in two steps (`severity:major`, then `auto-bug`). That real
  `issues:labeled` event triggered `Auto-fix bug` run 3, which marked #89
  `needs-human` with the same no-Claude-auth comment. `.agents/.wiki_bug_sync_cursor`
  is advanced to 44 in the follow-up commit to prevent a later duplicate issue.
- Slice 5b started on 2026-04-30 without touching #18-owned runtime/test
  files. `scripts/wiki_bug_sync.py` now has an opt-in
  `--include-community-requests` lane: BUG pages keep the numeric
  `.wiki_bug_sync_cursor`, while promoted non-bug wiki artifacts use
  `.agents/.wiki_change_sync_seen.json`. Future promoted feature, patch,
  docs/ops, branch-refinement, and project-design pages get GitHub Issues
  labeled `auto-change` plus `request:<kind>`. BUG pages also carry
  `auto-change` for the shared downstream queue while retaining `auto-bug`.
- Local proof for Slice 5b: `python -m py_compile scripts/wiki_bug_sync.py`,
  `python -m ruff check scripts/wiki_bug_sync.py`, `python
  scripts/wiki_bug_sync.py --dry-run --url https://tinyassets.io/mcp --repo
  Jonnyton/Workflow --include-community-requests`, and local `actionlint`
  against `.github/workflows/wiki-bug-sync.yml` +
  `.github/workflows/auto-fix-bug.yml` pass. The dry-run reports no new
  current requests with `bug_cursor=44` and `change_seen=12`; new promoted
  non-bug request pages are the live trigger.
- Local `gh` is not authenticated, so live GitHub checks used the public REST
  API. Authenticated issue/PR mutation still needs GitHub app or a configured
  token.
- Slice 6 loop watch started on 2026-04-30 without website UI edits. Local
  `scripts/community_loop_watch.py` reads public GitHub state and currently
  reports RED: intake and deploy workflows are green, but 9 open loop issues
  are `needs-human`, 32 pending loop issues are older than 45 minutes,
  `uptime-canary.yml` latest run is failed/stale, and open P0 issue #79 is
  still live. This is the first cloud-visible status contract for the website
  to render after preview approval.
- Slice 6 shipped to `main` on 2026-04-30 at commit `dd7bed4`. Live proof:
  `Community loop watch` run `25147557573` failed intentionally on RED state,
  issue #90 (`community-loop-red`) opened with the status JSON, `actionlint`
  run `25147557593` passed after shellcheck fixes, `build-image` run
  `25147557592` passed, `Deploy prod` run `25147567091` passed, and
  `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp
  --verbose` was green locally. The loop is now visible as down rather than
  falsely green.

## Existing Pieces

- `workflow/api/wiki.py`: `wiki action=file_bug`, dedup, kind routing, wiki
  write path.
- `workflow/bug_investigation.py`: payload mapping, dispatcher enqueue helper,
  Investigation/Patch Packet formatting, patch packet attachment helper.
- `workflow/dispatcher.py` and branch task queue: request-type claim surface.
- `scripts/wiki_bug_sync.py` + `.github/workflows/wiki-bug-sync.yml`: wiki
  BUG -> GitHub Issue sync.
- `.github/workflows/auto-fix-bug.yml`: GitHub Issue label -> Claude action
  fix attempt -> PR or `needs-human`.
- `workflow/git_bridge.py`: local git primitives including `open_pr`.
- Live user surfaces: Claude.ai `ui-test` when quota is available; ChatGPT
  rendered UI fallback is confirmed usable with the Workflow connector.

## Gaps To Close

1. **Forward trigger is not wired for the wiki bug lane.** Filing a wiki bug
   does not enqueue `bug_investigation`.
2. **Backfill and safety-net are not wired.** Old/unprocessed requests stay
   idle if the forward trigger was missing or misconfigured.
3. **Patch packet completion is not observed end-to-end.** The helper can
   attach a packet, but the loop has no proven run-completion hook that appends
   it to the bug page.
4. **Patch-loop branch is bound but unrunnable.** `change_loop_v1` is attached
   to Goal `4ff5862cc26d`, but live run `020a76ae0530478e` failed with a
   node-id/state-key collision; tracked as BUG-044.
5. **PR automation is one claimant, not the request bus.** The existing GitHub
   Action starts from labeled GitHub issues. It must consume `daemon-request`
   issues as a reference free daemon, fall through between Claude and Codex
   writer paths, and label PRs with writer/checker policy. Other paid/free
   daemons should be able to claim the same public request if they satisfy the
   gate and bounty contract.
6. **Gate requirements are not enforced at claim time yet.** Gate ladders can
   carry `branch_requirements` and `bounty_requirements`, but runtime
   enforcement in `gates claim` waits for the #18-owned `market.py` sweep to
   clear.
7. **Observation closure is manual.** No single status object says "BUG-NNN
   or request N was filed, investigated/planned, PR opened, merged, deployed,
   live-tested, and clean-use observed."
8. **Docs are contradictory.** `docs/ops/post-redeploy-validation-runbook.md`
   claims `file_bug` emits a dispatcher request; current code and active exec
   plan show it does not.
9. **Loop uptime is not independently watched.** The existing uptime ladder
   proves MCP/tool/wiki surfaces, but no cloud-scheduled probe says whether
   intake, queue, writer, release, and observation are operating as one loop.

## Domain Invariants

- Do not redesign `bug_to_patch_packet_v1` or `change_loop_v1`; community
  branches compete/evolve through Goal binding, forks, versions, judgments,
  and observation results.
- Do not add new platform tools for convenience if existing primitives compose
  the behavior.
- A request filing must never fail because a downstream branch or automation
  path is misconfigured. Follow-on work is best-effort around the durable
  request record.
- Public request lifecycle state must be reconstructable from durable
  artifacts: wiki page, GitHub issue/PR, git log, run record, and observation
  evidence.
- Final acceptance for MCP/chatbot-visible behavior requires rendered user
  surface proof. Claude.ai is preferred; ChatGPT rendered UI is the fallback
  while Claude is rate-limited.

## Implementation Slices

### Slice 1: Make the wiki bug lane enqueue investigation

Files likely touched:

- `workflow/api/wiki.py`
- `tests/test_bug_investigation_wiring.py`
- `docs/exec-plans/active/2026-04-25-file-bug-wiring.md`

Acceptance:

- Unskip `test_wiki_file_bug_invokes_maybe_enqueue_investigation`.
- `_wiki_file_bug` calls `_maybe_enqueue_investigation` after the wiki write
  and log append.
- Helper failure never changes the `file_bug` response.
- Focused tests pass.

Coordination:

- This touches `tests/`, currently claimed by #18. Claim only after #18 clears
  or after STATUS explicitly narrows the collision.

### Slice 2: Add backfill and safety-net producer

Files likely touched:

- `workflow/bug_investigation.py`
- daemon startup/scheduler module after local map confirms the right home
- new focused tests

Acceptance:

- A scan finds bug pages without `## Investigation` or `## Patch Packet`.
- Startup and periodic safety-net enqueue the missing `bug_investigation`
  requests idempotently.
- Duplicate queue entries are prevented or harmlessly coalesced.

### Slice 3: Attach run output back to the wiki bug

Files likely touched:

- run-completion/dispatcher integration point
- `workflow/bug_investigation.py`
- focused tests around `patch_packet` output shapes

Acceptance:

- Completed investigation runs with `patch_packet` append or replace the
  `## Patch Packet` section on the correct BUG page.
- Failed runs append an Investigation status note with actionable failure
  class, not a false patch packet.

### Slice 4: Bind live Goal/Branch state

Live operation, not code:

- Bind `fd5c66b1d87d` (`change_loop_v1`) to Goal `4ff5862cc26d`. Done on
  2026-04-30 after host approval.
- Publish/record versions if the versioning surface is required before
  canonical selection.
- Set canonical only through the supported version primitive once live versions
  exist.

Acceptance:

- `goals action=get goal_id=4ff5862cc26d` shows `change_loop_v1` bound.
- `extensions action=get_branch branch_def_id=fd5c66b1d87d` still shows the
  original community branch shape.
- Follow-up run should pass compile after BUG-044 is resolved.

### Slice 5: PR producer bridge

Files likely touched:

- existing `auto-fix-bug` workflow or a new provider-neutral auto-fix runner
- `workflow/git_bridge.py` only if the current primitive is insufficient
- docs/runbook updates

Acceptance:

- A patch packet or daemon-request issue creates a branch and PR, or a structured
  `needs-human` artifact if no writer provider is configured.
- PR body links the request artifact, wiki page, change packet, tests, and
  observation plan.
- Writer path is one claimant on the daemon request bus: subscription-backed
  Claude Code OAuth if configured, future subscription-backed Codex lane when
  available, manual fallback otherwise. Claude failures do not fall through to
  API-key billing lanes.
- No-auth blocks self-heal: issues marked `needs-human` before writer auth was
  visible are rediscovered by scheduled backfill once approved Claude/Codex
  writer auth appears, unless a real writer attempt already marked the issue
  `auto-fix-attempted`.
- PRs record `writer:*` and `checker:*` labels; `writer:claude` requires
  `checker:codex`, and `writer:codex` requires `checker:claude`.

### Slice 5c: Gate, Branch, and bounty requirement contract

Files likely touched:

- `docs/conventions/gate-branch-shape.md`
- `.github/workflows/daemon-request-policy.yml`
- runbooks and request-labeling scripts

Acceptance:

- Gate ladder rungs can declare `branch_requirements` and
  `bounty_requirements`.
- Request issues carry labels that make the daemon request contract visible:
  `daemon-request`, `payment:free-ok`, `writer-pool:claude-codex`,
  `checker:cross-family`, and `gate-required`; the allowed writer lane is still
  subscription-backed Claude/Codex only.
- Machine-authored PRs cannot pass policy with same-family writer/checker
  labels.
- Runtime `gates claim` validation is explicitly queued behind #18 rather than
  silently pretending the locked `market.py`/plugin-mirror files are already
  wired.

### Slice 5b: Generalize request classes beyond bugs

Files likely touched:

- wiki request intake and sync scripts
- GitHub labels/workflows
- community Goal/Branch docs and examples

Acceptance:

- Feature requests, patch requests, docs/ops changes, and project-design
  proposals can enter the same loop without being mislabeled as bugs.
- GitHub labels distinguish request kind while sharing the same downstream
  change-loop primitives.
- Existing BUG pages remain valid first-class request artifacts.

Implementation note:

- This slice uses promoted wiki artifacts as the non-bug entrypoint until a
  dedicated chatbot `file_change_request` / `file_feature_request` verb can be
  added after #18 clears the runtime/test write lock.

### Slice 6: Observation and closure

Files likely touched:

- new live-loop probe script or runbook
- wiki/GitHub status update path
- acceptance probe catalog if this becomes a named probe

Acceptance:

- One command/report reconstructs request state across wiki, queue/run, issue,
  PR, CI, deploy, canaries, rendered chatbot proof, and post-change clean-use
  evidence.
- A GitHub-hosted scheduled watch runs without the local machine and opens or
  updates a `community-loop-red` issue when the loop is red. It reports known
  blocked states, including missing writer auth, instead of treating
  successful no-op automation as a healthy loop.
- If observation fails, the item re-enters the loop instead of being marked
  done.

## First Live Request To Clear

Use a real existing request once the first lane is in place. BUG-044 is now the
current live request because it came from the first `change_loop_v1` run and
has a concrete public transition path. Other good bug-lane candidates:

- BUG-038: provider exhaustion blocked a live branch-run proof.
- BUG-041: failed branch run snapshot can leave failed node displayed as
  running.
- BUG-034: ChatGPT approval bug is P1 but likely partly outside repo control;
  use only after internal mitigations are clearly scoped.

For the first full proof, prefer a repo-fixable bug with a small code surface
and a rendered ChatGPT/Claude observation path. Do not start with a provider
secret/configuration-only failure unless the goal is explicitly ops wiring.

## Verification Ladder

1. Local focused tests for each slice.
2. Push to GitHub/main and watch relevant Actions green.
3. Public canaries: `python scripts/mcp_public_canary.py --url
   https://tinyassets.io/mcp` and the live uptime ladder.
4. Rendered chatbot proof: Claude.ai when quota returns; ChatGPT UI fallback
   while Claude is blocked.
5. Post-fix clean-use evidence: logs, live user history, issue/PR status,
   canary recurrence window, or explicit "no post-fix real-user use yet" watch
   item in STATUS.
