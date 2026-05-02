# OpenAI App Submission Readiness - 2026-05-02

Purpose: one checklist for deciding whether Workflow is ready to click
`Submit for Review` in the OpenAI Apps dashboard.

## Acceptance Inputs From Official Docs

Official OpenAI docs checked 2026-05-02 say the submission must satisfy these
practical gates:

- Public app submissions are for public distribution; private/workspace use
  should stay in developer mode.
- Publisher identity must be verified as the individual or business name used
  for publication.
- The MCP server must be on a publicly accessible HTTPS domain, not a local or
  testing endpoint.
- Submission form fields include app name, logo, description, company and
  privacy policy URLs, MCP/tool information, screenshots, test prompts and
  responses, and localization information.
- Common rejection causes include unreachable MCP URLs, failing test cases,
  outputs that contain irrelevant personal/internal identifiers, missing
  privacy disclosures, and inaccurate tool annotations.
- Test cases should pass in ChatGPT web and mobile, with direct,
  outcome-oriented, and negative prompts represented.
- Metadata should be precise enough to call Workflow only for relevant prompts
  and avoid negative prompts.
- Tool inputs and outputs should minimize data collection and avoid restricted
  or credential-like fields.

Sources:

- `https://developers.openai.com/apps-sdk/deploy/submission`
- `https://developers.openai.com/apps-sdk/app-submission-guidelines`
- `https://developers.openai.com/apps-sdk/guides/security-privacy`
- `https://developers.openai.com/apps-sdk/plan/tools`
- `https://developers.openai.com/apps-sdk/guides/optimize-metadata`
- `https://developers.openai.com/apps-sdk/deploy/testing`
- `https://developers.openai.com/apps-sdk/deploy`

## Current Readiness Verdict

Verdict: not ready for final submit yet.

Source packet is review-aligned and deployed, and ChatGPT web proof is clean.
Final submission should wait for the OpenAI-specific blockers below:

1. ChatGPT mobile must complete the main read/write flows.
2. Logo/screenshots or demo asset choices, release notes, mature-content
   answer, publisher selector, verification assertion, and compliance/legal
   checkboxes need host review.
3. Host must approve final `Submit for Review` at action time.

Parallel onboarding gaps that are not OpenAI-submit blockers:

- Claude.ai rendered connector proof still needs a fresh live UI trace.
- Claude Connectors Directory form submit still needs contact/org field and
  final-submit approval.

Post-submit monitoring:

- First-user clean-use evidence beyond controlled tests cannot be proven before
  public distribution without a real external user. Keep it as a watch item
  after OpenAI/Claude submission rather than a blocker for clicking OpenAI
  review.

Closed 2026-05-02T12:56-07:00:

- PR #183 merged to `main` at `69b93ae`.
- Deploy prod run `25260452881` passed and deployed image tag
  `69b93ae89027`.
- Public canaries passed for both `https://tinyassets.io/mcp` and
  `https://tinyassets.io/mcp-directory`.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp-directory --timeout 20 --verbose`
  passed from the updated worktree and invoked `get_workflow_status`.
- Live `/mcp-directory` `get_workflow_status` no longer returns raw
  `activity_log_tail`, raw `last_n_calls`, `policy_hash`,
  `session_boundary`, `host_id`, or storage subsystem `path` fields. It
  returns `directory_privacy_note`.
- PR #184 later removed remaining review-noisy `activity_log_tail_count`,
  `last_n_calls_count`, and `evidence_caveats.last_n_calls` labels before
  final OpenAI submit proof.

Closed 2026-05-02T13:13-07:00:

- PR #184 merged to `main` at `30363c7`.
- Deploy prod run `25260784025` passed and deployed image tag
  `30363c709a28`.
- Public canaries passed for both `https://tinyassets.io/mcp` and
  `https://tinyassets.io/mcp-directory`.
- `python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp-directory --timeout 20 --verbose`
  passed and invoked `get_workflow_status`.
- Strict live redaction probe passed: `evidence` only contains
  `activity_log_line_count` and `last_completed_request_llm_used`;
  `evidence_caveats` only contains `last_completed_request_llm_used`; and
  `activity_log_tail`, `last_n_calls`, `activity_log_tail_count`,
  `last_n_calls_count`, `policy_hash`, `session_boundary`, `host_id`, and
  storage subsystem `path` fields are absent.

Closed 2026-05-02T13:23-07:00:

- ChatGPT web Developer Mode read prompt completed using Workflow status with
  no `Unknown action`, hang, or 5xx.
- ChatGPT web rendered the `Propose a public workflow goal?` approval card for
  `propose_workflow_goal`.
- Host approved the public write at action time.
- ChatGPT completed and returned goal id `20e2339c82e3` with
  `Called tool was propose_workflow_goal: yes`.
- Direct `/mcp-directory` verification via `search_workflow_goals` and
  `get_workflow_goal` confirmed goal `20e2339c82e3` exists, is public, and has
  tags `submission, smoke`.

Historical ChatGPT Developer Mode proof and BUG-034 boundaries are preserved in
`docs/ops/openai-app-submission-chatgpt-proof-2026-05-02.md`.

## Tool Hint Audit

Source audited: `workflow/directory_server.py`.

Result: 11 source tools match `chatgpt-app-submission.json` exactly for
`readOnlyHint`, `openWorldHint`, and `destructiveHint`.

ChatGPT Apps submission packet audit on 2026-05-02:

- 11 source tools, 11 JSON tools, no missing or extra packet tools.
- 10 positive test cases after adding two outcome-oriented discovery/write
  prompts.
- 4 negative test cases.
- No widget/resource templates are exposed from this directory surface, so no
  widget CSP domains are required for this submission packet.

Fresh validation on 2026-05-02T13:37-07:00 from
`codex/onboarding-readiness-consolidation`:

- `python -m json.tool chatgpt-app-submission.json` passed.
- `python -m pytest tests/test_directory_server.py -q` passed: 7 tests.
- Public canaries passed for both `https://tinyassets.io/mcp` and
  `https://tinyassets.io/mcp-directory`.
- Tool canaries passed for both endpoints; `/mcp-directory` listed the 11
  directory tools and invoked `get_workflow_status`.
- Strict live redaction probe passed with `directory_privacy_note`; no raw
  logs, recent call arrays, count labels, policy hash, session boundary,
  host id, or storage `path` keys appeared.
- `python scripts/check_cross_provider_drift.py` and `git diff --check`
  passed.

Write tools:

- `propose_workflow_goal`: `readOnlyHint=false`,
  `openWorldHint=true`, `destructiveHint=false`. It creates a shared Workflow
  goal proposal and can be public.
- `submit_workflow_request`: `readOnlyHint=false`,
  `openWorldHint=false`, `destructiveHint=false`. It queues a bounded request
  inside Workflow and does not itself publish to third-party systems.

Read tools:

- `get_workflow_status`
- `list_workflow_universes`
- `inspect_workflow_universe`
- `list_workflow_goals`
- `search_workflow_goals`
- `get_workflow_goal`
- `search_workflow_wiki`
- `read_workflow_wiki_page`
- `list_workflow_runs`

All are annotated read-only, non-destructive, and non-open-world.

## Privacy/Data Review

OpenAI docs flag unnecessary logs, telemetry, internal identifiers, timestamps,
request IDs, and personal identifiers as rejection risks.

Branch hardening:

- Directory `get_workflow_status` redacts raw activity logs.
- Directory `get_workflow_status` redacts host account identifiers.
- Directory `get_workflow_status` redacts internal policy hashes.
- Directory `get_workflow_status` removes local/storage paths from subsystem
  storage details.
- Directory `get_workflow_status` removes session-boundary account data.

Remaining categories the privacy policy should disclose for the OpenAI app
path:

- User-submitted goal names, descriptions, tags, and visibility.
- User-submitted Workflow request text and optional target universe/branch.
- Workflow goal, branch, wiki, run, queue, and daemon status metadata returned
  to answer user prompts.
- Generated Workflow identifiers that are necessary for follow-up actions
  (`goal_id`, `run_id`, `request_id`, `branch_task_id`, `universe_id`).
- Operational status/routing/sandbox/storage-pressure metadata in redacted
  form.

The directory surface does not request passwords, API keys, MFA codes, payment
data, government IDs, biometrics, SSNs, PHI, or PCI data.

## Golden Prompt Set

Use these for ChatGPT web and mobile. For write prompts, confirm at action-time
before approving the write. The set intentionally includes direct Workflow
prompts plus outcome-oriented prompts that should still map to Workflow because
they ask for durable workflow goals.

Positive:

1. `Use Workflow to check the current daemon status and tell me any caveats before I start.`
2. `Use Workflow to search for goals related to onboarding and show the best matches.`
3. `I'm planning onboarding for new MCP hosts. Search durable workflow goals about onboarding and summarize the best matches.`
4. `Use Workflow to list shared goals, then inspect the first relevant goal you find.`
5. `Use Workflow to list available universes, then inspect the active one.`
6. `Use Workflow to search the wiki for current launch risks, then read the most relevant page.`
7. `Use Workflow to list recent runs and tell me whether anything is currently active or blocked.`
8. `Use Workflow to propose a public goal named 'Onboard new MCP hosts' with tags discovery,onboarding.`
9. `Create a shared durable workflow goal named 'Reduce MCP onboarding friction' with tags onboarding,hosts.`
10. `Use Workflow to submit a request asking the daemon to summarize today's discoverability blockers.`

Negative:

1. `What is the weather in San Francisco tomorrow?`
2. `Use Workflow to send an email to my team about the launch.`
3. `Use Workflow to delete every universe and wipe all stored data.`
4. `Use Workflow to save my API key and password for later.`

Pass criteria:

- The expected tool is selected for positive prompts.
- No Workflow tool is selected for negative prompts.
- Write actions show approval UX and complete after explicit approval.
- Outputs are relevant and do not include raw logs, local filesystem paths,
  host account identifiers, or irrelevant internal IDs.

## Pre-Submit Command Gate

Run from the branch that will be submitted:

```powershell
python -m json.tool chatgpt-app-submission.json > $null
python -m pytest tests/test_directory_server.py -q
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --timeout 15 --verbose
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp-directory --timeout 15 --verbose
python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp --timeout 20 --verbose
python scripts/mcp_tool_canary.py --url https://tinyassets.io/mcp-directory --timeout 20 --verbose
python scripts/mcp_probe.py --url https://tinyassets.io/mcp-directory --tool get_workflow_status --args "{}" --raw
```

For the final probe, parse the tool result text as JSON and verify these
diagnostic keys are absent:

- `activity_log_tail`
- `last_n_calls`
- `activity_log_tail_count`
- `last_n_calls_count`
- `policy_hash`
- `session_boundary`
- `host_id`
- storage subsystem `path` fields

## Final Submit Checklist

- Branch landed and deployed.
- Public canaries green after deploy.
- Live status redaction proof captured.
- ChatGPT web golden prompts captured.
- ChatGPT mobile golden prompts captured.
- Logo and any chosen screenshots/demo assets uploaded.
- Privacy policy categories reviewed.
- Release notes reviewed.
- Publisher selector and verification assertion approved.
- Compliance/legal boxes approved.
- Mature/adult-content answer approved.
- Host says "submit now" at action-time.
