---
name: gpt-update
description: Update the Custom GPT configuration files (system prompt + OpenAPI schema) and push to the live GPT via browser tools.
user_invocable: true
---

Review and update the two Custom GPT configuration files, then push them to the live GPT:

1. `custom_gpt/instructions.md` -- the system prompt (hard limit: 8000 characters)
2. `custom_gpt/actions_schema.yaml` -- the OpenAPI 3.1.0 Actions schema

## Update flow

### 1. Diff API vs schema

Before touching files, check what changed. The schema must match `fantasy_author/api.py`.

```bash
# List all routes in api.py
grep -E '^\s*@app\.(get|post|put|patch|delete)' fantasy_author/api.py

# List all operationIds in schema
grep 'operationId:' custom_gpt/actions_schema.yaml
```

Look for: new endpoints missing from schema, removed endpoints still in schema, changed request/response shapes, new fields on existing models.

### 2. Edit the local files

Update `instructions.md` and `actions_schema.yaml` as needed.

**Schema design principles:**
- Stay well under 30 operations. Target 20-25. Every operation must earn its place.
- When multiple endpoints return overlapping data, consolidate. `getOverview` should absorb status/progress/activity rather than having separate endpoints for each.
- Cut developer-facing endpoints (provider config, workspace CRUD) that the GPT doesn't use in practice.
- New API endpoints don't automatically need schema entries. Ask: will the GPT ever need to call this?

**Instruction distribution:**
- Instructions field (8000 char limit): hard rules, violation examples, architecture, identity, tone. Target ~4000 chars.
- Schema `info.description`: routing overview, file upload workflow, new universe workflow, cancellation workflow. No hard size limit.
- Endpoint descriptions (300 char limit): what this does for the user, when to call it.
- Parameter descriptions (700 char limit): format examples, guidance.

### 3. Validate before pushing

**All three checks must pass. Do NOT push if any fail.**

```bash
# Instructions size (must be < 8000)
wc -c custom_gpt/instructions.md

# Operation count (must be <= 30)
grep -c 'operationId:' custom_gpt/actions_schema.yaml

# Description lengths
python3 -c "
import yaml
with open('custom_gpt/actions_schema.yaml') as f:
    schema = yaml.safe_load(f)
over = []
for path, methods in schema.get('paths', {}).items():
    for method, details in methods.items():
        if not isinstance(details, dict): continue
        desc = (details.get('description') or '').strip()
        if len(desc) > 300:
            over.append(f'{details.get(\"operationId\",\"?\")} endpoint = {len(desc)} chars')
        for param in details.get('parameters', []):
            pdesc = (param.get('description') or '').strip()
            if len(pdesc) > 700:
                over.append(f'{details.get(\"operationId\",\"?\")}.{param[\"name\"]} param = {len(pdesc)} chars')
print('ALL OK' if not over else 'VIOLATIONS:\\n' + '\\n'.join(over))
"
```

### 4. Push to the live GPT — pick your method

**The push should be invisible to the user.** Don't narrate each click.

#### Method A: Chrome MCP (Cowork — preferred for updates)

Invisible by default — the MCP tab group is hidden. This is ideal for updates.

```
tabs_context_mcp (createIfEmpty: true)
navigate to: https://chatgpt.com/gpts/editor/g-69cd9dc9c52c8191a18dd84829712447
```

**Inject instructions** (Configure tab → Instructions textarea):
```javascript
// CRITICAL: Use native setter + event dispatch. Do NOT use the type action
// for long content — it times out. React textareas ignore direct .value assignment.
const textarea = document.querySelector('textarea[placeholder*="What does this GPT do"]');
const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
  window.HTMLTextAreaElement.prototype, 'value'
).set;
nativeInputValueSetter.call(textarea, NEW_CONTENT_HERE);
textarea.dispatchEvent(new Event('input', { bubbles: true }));
textarea.dispatchEvent(new Event('change', { bubbles: true }));
```

**Inject schema** (Configure → Actions → gear icon → schema textarea):
```javascript
const textareas = document.querySelectorAll('textarea');
let schemaTA = null;
for (const ta of textareas) {
  if (ta.value && ta.value.includes('openapi:')) { schemaTA = ta; break; }
}
const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
  window.HTMLTextAreaElement.prototype, 'value'
).set;
nativeInputValueSetter.call(schemaTA, NEW_SCHEMA_HERE);
schemaTA.dispatchEvent(new Event('input', { bubbles: true }));
schemaTA.dispatchEvent(new Event('change', { bubbles: true }));
```

#### Method B: gpt_builder CLI (Codex, Codex)

```bash
python -m fantasy_author.testing.gpt_builder update-instructions custom_gpt/instructions.md
python -m fantasy_author.testing.gpt_builder update-schema custom_gpt/actions_schema.yaml
```

If the CLI doesn't have update commands, use CDP directly to drive the editor page at `https://chatgpt.com/gpts/editor/g-69cd9dc9c52c8191a18dd84829712447` — same JS injection pattern as Method A.

#### How to choose

- Have Chrome MCP tools? → Method A (invisible, no user disruption)
- Running on the user's machine with Python? → Method B

### 5. Verify after pushing

- Scroll down in schema editor — "Available actions" should list all operations with Test buttons
- If it shows "Operations in your schema will show here" or a red 30-op warning → schema was rejected
- **Disable Web Search:** On Configure tab under Capabilities, Web Search must be UNCHECKED. #1 cause of misbehavior.
- Click "Update" button (top right). Wait for "GPT Updated" confirmation.

### 6. After updating

1. Start a **new GPT session** to pick up instruction changes.
2. If the tunnel URL changed, schema must include the new URL.

## Hard limits (as of 2026-04)

| Limit | Value |
|-------|-------|
| Instructions character limit | 8,000 characters |
| Action timeout | 45 seconds round-trip |
| Request/response payload | 100,000 characters max each |
| Endpoint description | 300 characters max |
| Parameter description | 700 characters max |
| Operations (operationIds) | 30 max per schema |
| TLS requirement | TLS 1.2+ on port 443, valid public cert |

## Prompt engineering patterns

- **Positive instructions over prohibitions.** "Always use Actions" beats "Don't search the web."
- **Be concrete.** "Call `getOverview` immediately" beats "check the story status." Name the operationId.
- **Reference operationIds exactly.** The GPT matches instruction text against schema operationIds.
- **`When X -> do Y` conditionals.** GPTs follow explicit conditionals better than prose.
- **Descriptions as user intent, not API docs.** "Returns everything about your story in one call" beats "Aggregates status, progress, output listing."

## File upload handling

GPTs can read uploaded file content directly but don't automatically pass it through Actions.

- `uploadCanonFiles` uses `openaiFileIdRefs` — GPT sends file references, API downloads them.
- Fallback: GPT reads file content, calls `addCanon` with `{filename, content}`.
- Instructions must spell out the workflow explicitly or the GPT invents a nonexistent upload endpoint.

## Schema best practices

- camelCase operationIds: `getStatus`, `addCanon`, `listOutput`, `controlWriter`.
- `x-openai-isConsequential: false` on non-destructive operations (shows "Always allow").
- `x-openai-isConsequential: true` on destructive operations (forces per-call confirmation).
- Return raw data, not natural language. The GPT generates its own response.

## Tunnel URL management

The schema `servers[0].url` points to a Cloudflare tunnel (ephemeral, changes on restart).
- Check `STATUS.md` for the current tunnel URL.
- When updating the schema, verify the URL is current.
- The GPT instructions handle dead tunnels: "Your host is offline."

## Lessons from observed GPT misbehavior

| Misbehavior | Root cause | Fix |
|-------------|-----------|-----|
| GPT searched the web for story info | Web Search capability was enabled | Disable Web Search in Capabilities |
| GPT looked for an "import upload" tool | Instructions didn't say "you ARE the upload tool" | Explicit file-upload workflow |
| GPT wrote diagnostic file to output/ | Didn't know workspace exists | Added workspace guidance |
| GPT hit dead tunnel URL and flailed | No mental model of host states | Three system states in architecture |
| GPT asked if it should start the daemon | Instructions didn't say to auto-start | "Writer follows the user" section |
| Schema silently rejected by OpenAI | Had 31 operations (over 30 limit) | Validate operation count before pushing |
| Type action timed out filling textarea | React textarea rejects slow char-by-char input | Use native JS setter + event dispatch |
