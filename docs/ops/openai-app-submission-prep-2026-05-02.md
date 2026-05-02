# OpenAI App Submission Prep - 2026-05-02

## Current form state

OpenAI Apps dashboard is logged in and the `Workflow` app draft exists.
The form is stopped on App Info. Do not upload files, enter contact fields,
or submit for review until the remaining blockers below are resolved.

OpenAI submission docs checked 2026-05-02:
https://developers.openai.com/apps-sdk/deploy/submission

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

Do not upload the current JSON while configuring the app to use `/mcp`; the
submitted tool packet and live MCP tool list would not describe the same app.
If `/mcp` remains the OpenAI target, regenerate the submission packet from the
full surface and re-audit hints, privacy, tests, and demo flows.

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

Required before upload/final submit:

- Demo recording URL showing the app in Developer Mode.
- Real ChatGPT web test of every submitted prompt.
- Mobile evidence for the main flows, because the OpenAI review docs call out
  web and mobile test correctness.
- Clear expected outputs with no personal identifiers or irrelevant debug data.

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
