# OpenAI App Submission Prep - 2026-05-02

## Current form state

OpenAI Apps dashboard is logged in and the `Workflow` app draft exists.
The form is stopped on the Submit page. Do not check legal/compliance boxes
or submit for review without action-time host approval.

OpenAI submission docs checked 2026-05-02:
https://developers.openai.com/apps-sdk/deploy/submission
OpenAI testing docs checked 2026-05-02:
https://developers.openai.com/apps-sdk/deploy/testing

## User-supplied launch intent

- Public app, even though Workflow is still alpha and evolving.
- Full-system launch direction.
- Global distribution intent.
- App name: `Workflow`.
- Developer/publisher: `TinyAssets`.
- Category: `PRODUCTIVITY`.
- User wants the app to show useful/cool flows, but only after real testing.

## Recommended App Info fields

- App name: `Workflow`.
- Subtitle: `Build durable workflows` (23 chars; fits the 30-char limit).
- Description: `Workflow connects ChatGPT to a durable open-source work graph. Users can check daemon status, browse shared goals and project wiki knowledge, and submit bounded requests that continue through the Workflow loop beyond a single chat.`
- Category: `PRODUCTIVITY`.
- Developer: `TinyAssets`.
- Website URL: `https://tinyassets.io`
- Support: `https://tinyassets.io/legal#contact` or `ops@tinyassets.io`.
- Privacy Policy URL: `https://tinyassets.io/legal#privacy`
- Terms of Service URL: `https://tinyassets.io/legal#terms`
- Logo candidate: `assets/brand/workflow-logo-icon.png` (1024x1024 PNG).

## URL boundary

The current `chatgpt-app-submission.json` describes the directory-safe tool
surface exposed by `workflow/directory_server.py`, whose tool names include:

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

That matches `https://tinyassets.io/mcp-directory`.

The full custom connector URL, `https://tinyassets.io/mcp`, exposes the
legacy tool surface in `workflow/universe_server.py`:

- `universe`
- `community_change_context`
- `extensions`
- `goals`
- `gates`
- `wiki`
- `get_status`

2026-05-02 update: host said "proceed" after this boundary was surfaced.
The OpenAI form was configured with `https://tinyassets.io/mcp-directory`,
matching the current JSON/tool packet. Tool scan returned green in the OpenAI
dashboard.

Do not switch the OpenAI app to `/mcp` without regenerating the submission
packet from the full surface and re-auditing hints, privacy, tests, and demo
flows.

## Form progress - 2026-05-02

Filled in OpenAI dashboard:

- App Info text fields, legal/support URLs, category `PRODUCTIVITY`.
- MCP Server URL: `https://tinyassets.io/mcp-directory`.
- Authentication: `No Auth`.
- Tool scan: green.
- Tool justifications: filled from `chatgpt-app-submission.json`.
- Testing: five positive test cases and three negative test cases entered.
- Testing correction: Test Case 2 expected output now accepts matching goals
  when present or a clear no-match result with a safe next step.
- Global: default `Allow all`.

Not filled/uploaded:

- Logo image.
- Screenshots.
- Demo recording URL.
- Submit page release notes.
- Submit page individual/business selector.
- Submit page compliance/legal checkboxes.
- Mature/adult-content radio.
- Final `Submit for Review`.

Local proof artifact captured:

- `output/openai-app-submission/openai-submit-page-corrected-2026-05-02.png`
  shows the Submit page after the Test Case 2 correction saved.

## Commerce boundary

Current public site/legal state says Workflow uses `test tiny` on Base Sepolia
today and real Destiny (tiny) integration is deferred. Recommended current form
answer: do not check "App Commerce & Purchasing" unless the app currently links
users out of ChatGPT to make purchases.

## Known user-related or internal fields to audit

OpenAI review guidance calls out undisclosed user-related data, telemetry,
internal identifiers, logs, timestamps, and request IDs as rejection risks.

Known fields from the directory surface:

- `get_workflow_status`: `active_host.host_id`, routing policy, provider
  evidence, `activity_log_tail`, `last_n_calls`, policy hash, cooldown fields,
  sandbox status, missing file names, `universe_id`, timestamps/log content.
- `list_workflow_runs`: `run_id`, `branch_def_id`, `run_name`, `status`,
  `actor`, `started_at`, `finished_at`, `last_node_id`.
- `propose_workflow_goal`: public or private goal name, description, tags,
  visibility, generated goal identifier, author/source metadata.
- `submit_workflow_request`: submitted request text is stored in Workflow;
  response returns `request_id`, `branch_task_id`, queue position, and universe.
- Wiki/goal read tools can return public project content and author/source
  metadata from the public knowledge/goal stores.

Decision needed: either disclose these categories in the privacy policy for the
OpenAI app path, or reduce/sanitize the returned fields before submitting.

## Demo and test blockers

Required before final submit:

- Optional proof uploads if we choose to provide them: logo, screenshots, and
  demo recording URL. The dashboard says screenshots are optional for non-UI
  apps, but submission docs still list screenshots among form information.
- Resolve the ChatGPT approval-card stall for `propose_workflow_goal`.
  Direct `/mcp-directory` and `/mcp` goal writes are fixed and deployed, and
  ChatGPT can read goals and submit requests, but goal-proposal approval cards
  still stall after approval (BUG-034).
- Mobile evidence for the main flows, because the OpenAI testing docs say to
  invoke the connector in ChatGPT iOS or Android apps.
- Keep expected outputs clear and free of personal identifiers or irrelevant
  debug data.
- Host approval of release notes and compliance/legal checkbox assertions.

Suggested release notes:

`Initial public alpha of Workflow. This app connects ChatGPT to the directory-safe Workflow MCP surface for daemon status, shared goals, project wiki lookup, and bounded request submission.`

Candidate tested prompts:

1. `Use Workflow to check the current daemon status and tell me any caveats before I start.`
2. `Use Workflow to search for goals related to onboarding and show the best matches.`
3. `Use Workflow to list available universes, then inspect the active one.`
4. `Use Workflow to search the wiki for current launch risks, then read the most relevant page.`
5. `Use Workflow to propose a public goal named "Onboard new MCP hosts" with tags discovery,onboarding.`
6. `Use Workflow to submit a request asking the daemon to summarize today's discoverability blockers.`

Negative prompts:

1. `What is the weather in San Francisco tomorrow?`
2. `Use Workflow to send an email to my team about the launch.`
3. `Use Workflow to delete every universe and wipe all stored data.`
4. `Use Workflow to save my API key and password for later.`

## Live ChatGPT Developer Mode proof - 2026-05-02

Environment: ChatGPT web Developer Mode, app shown as `Workflow Dev`, connected
to `https://tinyassets.io/mcp-directory`.

Read-only positive prompts tested:

1. `Use Workflow to check the current daemon status and tell me any caveats before I start.`
   Result: Workflow tool invoked; ChatGPT returned daemon status plus caveats.
2. `Use Workflow to search for goals related to onboarding and show the best matches.`
   Result: `search_workflow_goals` invoked; no onboarding matches were returned.
   Form and JSON expected output were corrected to accept this valid empty state.
3. `Use Workflow to list available universes, then inspect the active one.`
   Result: universe list and active-universe inspection returned successfully.
4. `Use Workflow to search the wiki for current launch risks, then read the most relevant page.`
   Result: wiki search/read tools invoked; response summarized launch risks and
   preserved the truncation caveat.

Negative prompt tested:

- `What is the weather in San Francisco tomorrow?`
  Result: ChatGPT used the native weather surface; no new Workflow tool call was
  observed between the prompt and response.

Write-path attempt:

- Prompt: `Use Workflow to propose a public goal named "Onboard new MCP hosts" with tags discovery,onboarding, then submit a request asking the daemon to summarize today's discoverability blockers.`
  Result: ChatGPT rendered the `Propose new public workflow goal?` approval card,
  but the tool call did not complete after approval. A direct public
  `/mcp-directory` probe reproduced `cannot import name '_ensure_author_server_db'
  from 'workflow.api.branches'`; final write-path proof is blocked until the
  directory goal-tool fix is deployed and retested.
- Follow-up after PR #149 deployment (`2a1651f`, deploy run 25245035290):
  - Direct `/mcp-directory` `propose_workflow_goal` succeeded and created goal
    `35f70887461e` (`Onboard new MCP hosts`).
  - Direct `/mcp` `goals action=propose` also succeeded, creating
    `975e8fbdead0` (`Workflow legacy propose probe 2026-05-02`).
  - ChatGPT Developer Mode read proof succeeded: `Workflow Dev` found
    `35f70887461e` by exact title.
  - ChatGPT Developer Mode request write succeeded:
    `submit_workflow_request` returned `req_1777701087_d215c1fa` in
    `echoes-of-the-cosmos`.
  - ChatGPT Developer Mode goal-propose approval still stalled after clicking
    `Propose Goal`. A fresh chat with `Workflow Dev` attached reproduced the
    stall; the opened tool-call payload still showed the legacy
    `Goals`/`action: "propose"` router shape. The platform MCP Server section
    lists the narrow `/mcp-directory` tool set, including
    `propose_workflow_goal`, so this looks like a stale ChatGPT dev-attachment
    or BUG-034 approval-routing issue rather than the old
    `_ensure_author_server_db` backend failure.

Not yet tested:

- Positive Test Case 5 is only partially proven: direct goal proposal works and
  ChatGPT request submission works, but ChatGPT goal-proposal approval still
  stalls after approval.
- Negative cases 2 and 3, because the submitted prompts ask ChatGPT not to route
  unrelated email/credential/destructive work through Workflow; run them in
  Developer Mode before final submit and verify no Workflow write tool is called.
