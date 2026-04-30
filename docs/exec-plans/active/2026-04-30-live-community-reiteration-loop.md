# Live Community Reiteration Loop

Status: active scoping, claimed by `codex-gpt5-desktop` on 2026-04-30.

## Goal

Make the community-driven change loop real and observable:

```text
wiki bug / patch request
  -> community-authored investigation branch
  -> patch packet
  -> coding/fix branch or PR
  -> CI + review gates
  -> merge + deploy
  -> live user-surface observation
  -> wiki/GitHub status update or re-entry into the loop
```

This is wiring and proof work, not a branch redesign. Branches remain
community-authored and remixable. Platform code should only provide the
smallest primitives that let those branches run, hand off, and be observed.

## Current Evidence

Freshness stamp: 2026-04-30, `wf-main-live`, local code + live MCP + public
GitHub API.

- PLAN.md already makes this the intended shape: minimal primitives,
  community-build over platform-build, commons-first architecture, GitHub as
  public shared state, Goals above Branches, and user/provider parity.
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
- Public GitHub API shows `wiki-bug-sync` exists and the latest visible run
  succeeded; `auto-fix-bug` has zero runs; no open public `auto-bug` issues or
  open PRs exist from this loop.
- Local `gh` is not authenticated, so live GitHub checks used the public REST
  API. Authenticated issue/PR mutation still needs GitHub app or a configured
  token.

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

1. **Forward trigger is not wired.** Filing a wiki bug does not enqueue
   `bug_investigation`.
2. **Backfill and safety-net are not wired.** Old/unprocessed bugs stay idle if
   the forward trigger was missing or misconfigured.
3. **Patch packet completion is not observed end-to-end.** The helper can
   attach a packet, but the loop has no proven run-completion hook that appends
   it to the bug page.
4. **Patch-loop branch is bound but unrunnable.** `change_loop_v1` is attached
   to Goal `4ff5862cc26d`, but live run `020a76ae0530478e` failed with a
   node-id/state-key collision; tracked as BUG-044.
5. **PR automation is issue-driven, not patch-packet-driven.** The existing
   GitHub Action starts from `auto-bug` issues and depends on Claude auth; it
   does not yet consume patch packets or Codex/Codex CLI as a writer path.
6. **Observation closure is manual.** No single status object says "BUG-NNN
   was filed, investigated, PR opened, merged, deployed, live-tested, and
   clean-use observed."
7. **Docs are contradictory.** `docs/ops/post-redeploy-validation-runbook.md`
   claims `file_bug` emits a dispatcher request; current code and active exec
   plan show it does not.

## Domain Invariants

- Do not redesign `bug_to_patch_packet_v1` or `change_loop_v1`; community
  branches compete/evolve through Goal binding, forks, versions, judgments,
  and observation results.
- Do not add new platform tools for convenience if existing primitives compose
  the behavior.
- A bug filing must never fail because the investigation pipeline is
  misconfigured. Investigation is best-effort around the durable bug record.
- Public bug lifecycle state must be reconstructable from durable artifacts:
  wiki page, GitHub issue/PR, git log, run record, and observation evidence.
- Final acceptance for MCP/chatbot-visible behavior requires rendered user
  surface proof. Claude.ai is preferred; ChatGPT rendered UI is the fallback
  while Claude is rate-limited.

## Implementation Slices

### Slice 1: Make `file_bug` enqueue investigation

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

- A patch packet or auto-bug issue creates a branch and PR, or a structured
  `needs-human` artifact if no writer provider is configured.
- PR body links BUG-NNN, wiki page, patch packet, tests, and observation plan.
- Writer path is provider-pluggable: Claude action if configured, Codex CLI
  path when available, manual fallback otherwise.

### Slice 6: Observation and closure

Files likely touched:

- new live-loop probe script or runbook
- wiki/GitHub status update path
- acceptance probe catalog if this becomes a named probe

Acceptance:

- One command/report reconstructs BUG-NNN state across wiki, queue/run, issue,
  PR, CI, deploy, canaries, rendered chatbot proof, and post-fix clean-use
  evidence.
- If observation fails, the item re-enters the loop instead of being marked
  done.

## First Bug To Clear

Use a real existing wiki bug once Slice 1 is in place. Good candidates:

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
