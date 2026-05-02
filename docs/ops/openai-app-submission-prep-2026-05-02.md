# OpenAI App Submission Prep - 2026-05-02

## Current Decision Boundary

OpenAI app draft: `Workflow`.

Submission target: ChatGPT Apps Directory public/global review using
`https://tinyassets.io/mcp-directory`, not the full custom connector surface at
`https://tinyassets.io/mcp`.

Final submit remains blocked on action-time host approval. Do not check
legal/compliance boxes, assert business/individual verification, or click
`Submit for Review` without that approval.

## Official OpenAI Docs Checked

Checked on 2026-05-02:

- `https://developers.openai.com/apps-sdk/deploy/submission`
- `https://developers.openai.com/apps-sdk/app-submission-guidelines`
- `https://developers.openai.com/apps-sdk/guides/security-privacy`
- `https://developers.openai.com/apps-sdk/plan/tools`
- `https://developers.openai.com/apps-sdk/guides/optimize-metadata`
- `https://developers.openai.com/apps-sdk/deploy/testing`
- `https://developers.openai.com/apps-sdk/deploy`

Review implications captured in
`docs/ops/openai-app-submission-readiness-2026-05-02.md`.
Historical ChatGPT Developer Mode proof is preserved in
`docs/ops/openai-app-submission-chatgpt-proof-2026-05-02.md`.

## App Info

- App name: `Workflow`
- Subtitle: `Build durable workflows` (23 chars; under OpenAI's 30-char
  guidance from the submission skill)
- Category: `PRODUCTIVITY`
- Developer/publisher: `TinyAssets`
- Website URL: `https://tinyassets.io`
- Support: `https://tinyassets.io/legal#contact` or `ops@tinyassets.io`
- Privacy Policy URL: `https://tinyassets.io/legal#privacy`
- Terms of Service URL: `https://tinyassets.io/legal#terms`
- Logo candidate: `assets/brand/workflow-logo-icon.png` (1024x1024 PNG)

Description:

`Workflow connects ChatGPT to a durable open-source work graph. Users can check daemon status, browse shared goals and project wiki knowledge, and submit bounded requests that continue through the Workflow loop beyond a single chat.`

## Tool Surface

`chatgpt-app-submission.json` covers the directory-safe source in
`workflow/directory_server.py`:

- `get_workflow_status`
- `list_workflow_universes`
- `inspect_workflow_universe`
- `list_workflow_goals`
- `search_workflow_goals`
- `get_workflow_goal`
- `search_workflow_wiki`
- `read_workflow_wiki_page`
- `list_workflow_runs`
- `propose_workflow_goal`
- `submit_workflow_request`

The full custom connector at `/mcp` exposes broader legacy tools (`universe`,
`community_change_context`, `extensions`, `goals`, `gates`, `wiki`,
`get_status`). Do not switch the OpenAI app to `/mcp` without regenerating and
re-auditing the packet for that full surface.

## Source Hardening Landed

PR #183 / merge `69b93ae` makes the packet safer for review:

- `get_workflow_status` now redacts raw activity logs, local paths, host
  account identifiers, and internal hashes from the directory-safe response.
- Directory tool docstrings now start with `Use this when...` phrasing to
  improve discovery precision.
- `tests/test_directory_server.py` now asserts that
  `chatgpt-app-submission.json` exactly matches the directory tool set and
  source annotations.
- Positive tests now cover all read/write tool families, including goal
  list/get and run listing.

Deploy prod run `25260452881` passed on 2026-05-02 and deployed image tag
`69b93ae89027`. Live `https://tinyassets.io/mcp-directory` has been re-probed
and now returns redacted status with `directory_privacy_note`, without raw
log/call arrays, host identifiers, local paths, session-boundary account data,
or internal hashes.

PR #184 / merge `30363c7` removed the remaining review-noisy diagnostic
count/caveat labels (`activity_log_tail_count`, `last_n_calls_count`, and
`evidence_caveats.last_n_calls`) before final OpenAI submit proof. Deploy prod
run `25260784025` passed and deployed image tag `30363c709a28`.

## OpenAI Dashboard State

Recorded prior dashboard state from 2026-05-02:

- App draft exists and reached the Submit page.
- MCP Server URL was configured as `https://tinyassets.io/mcp-directory`.
- Authentication was set to `No Auth`.
- Tool scan was green at that time.
- Tool justifications and test cases were entered from
  `chatgpt-app-submission.json`.
- Final submit page was not completed.

Not yet complete:

- Logo upload.
- Screenshots and/or demo recording URL if we choose to provide them.
- Release notes.
- Individual/business publisher selector and verification assertion.
- Compliance/legal checkboxes.
- Mature/adult-content radio.
- Final `Submit for Review`.

## Required Before Submit

1. Run public canaries and tool canaries against both `/mcp` and
   `/mcp-directory`.
2. Verify live `/mcp-directory` `get_workflow_status` no longer returns raw
   logs, local paths, host account identifiers, or internal hashes.
3. Run the ChatGPT mobile golden prompt set. OpenAI testing docs explicitly
   call out testing iOS or Android.
4. For `propose_workflow_goal` and `submit_workflow_request`, confirm at
   action-time before approving public/state-changing writes.
5. Confirm privacy policy coverage for the categories listed in the readiness
   doc.
6. Host approves release notes, compliance answers, mature-content answer,
   publisher selector, and final submit.

Suggested release notes:

`Initial public alpha of Workflow. This app connects ChatGPT to the directory-safe Workflow MCP surface for daemon status, shared goals, project wiki lookup, run browsing, and bounded request submission.`

## Current Verification Snapshot

2026-05-02T12:34-07:00 from `../wf-openai-submission-hardening`:

- `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp-directory --timeout 15 --verbose` passed.
- `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --timeout 15 --verbose` passed.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp-directory --timeout 20 --verbose` passed.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp --timeout 20 --verbose` passed.
- `python -m pytest tests/test_directory_server.py -q` passed locally for this branch.

2026-05-02T12:56-07:00 from deployed `main` merge `69b93ae`:

- PR #183 merged and deploy prod run `25260452881` passed for image tag
  `69b93ae89027`.
- `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --timeout 15 --verbose` passed.
- `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp-directory --timeout 15 --verbose` passed.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp --timeout 20 --verbose` passed.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp-directory --timeout 20 --verbose` passed from the updated worktree and invoked `get_workflow_status`.
- `python scripts/mcp_probe.py --url https://tinyassets.io/mcp-directory --tool get_workflow_status --args "{}" --raw` returned `directory_privacy_note`, with raw `activity_log_tail`, raw `last_n_calls`, `policy_hash`, `session_boundary`, `host_id`, and storage subsystem `path` fields absent.
2026-05-02T13:13-07:00 from deployed `main` merge `30363c7`:

- PR #184 merged and deploy prod run `25260784025` passed for image tag
  `30363c709a28`.
- `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --timeout 15 --verbose` passed.
- `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp-directory --timeout 15 --verbose` passed.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp --timeout 20 --verbose` passed.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp-directory --timeout 20 --verbose` passed and invoked `get_workflow_status`.
- Strict live redaction probe passed: `evidence` only contains
  `activity_log_line_count` and `last_completed_request_llm_used`;
  `evidence_caveats` only contains `last_completed_request_llm_used`; and
  `activity_log_tail`, `last_n_calls`, `activity_log_tail_count`,
  `last_n_calls_count`, `policy_hash`, `session_boundary`, `host_id`, and
  storage subsystem `path` fields are absent.

2026-05-02T13:23-07:00 from ChatGPT web Developer Mode:

- Read-only Workflow status prompt completed with no `Unknown action`, hang, or
  5xx.
- Approved public write prompt completed after the `Propose a public workflow
  goal?` card.
- ChatGPT returned goal id `20e2339c82e3` and stated
  `Called tool was propose_workflow_goal: yes`.
- Direct `/mcp-directory` `search_workflow_goals` and `get_workflow_goal`
  probes confirmed goal `20e2339c82e3` exists, is public, and has tags
  `submission, smoke`.
