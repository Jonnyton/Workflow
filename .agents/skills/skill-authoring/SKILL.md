---
name: skill-authoring
description: Creates or updates project-local agent skills with Workflow-specific conventions. Use when adding a new skill, merging overlapping skills, tuning trigger descriptions, reorganizing skill resources, or updating the Claude mirror.
---

# Skill Authoring

## Overview

Create skills that fit this repo's conventions. Do not vendor external skills
raw when the project already has overlapping skills or stronger local patterns.

## Project Conventions

- Canonical source lives in `.agents/skills/<skill-name>/`.
- Claude mirror lives in `.claude/skills/<skill-name>/` and is refreshed by
  `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1`.
- Default to a single `SKILL.md`. Add `references/` or `scripts/` only when
  repeated detail or deterministic logic justifies it.
- Keep frontmatter to `name` and `description`.
- Use lowercase, hyphenated skill names.
- Write descriptions that say both what the skill does and when to use it.
- Prefer adapting outside ideas into Workflow conventions over copying their
  file layouts, naming, or docs blindly.
- Do not introduce `README.md`, `CHANGELOG.md`, `CONTEXT.md`, or
  `agents/openai.yaml` unless the repo explicitly adopts those patterns.

## Workflow

### 1. Audit overlap first

Before adding a skill:

- Check existing project skills.
- Decide whether the new capability is:
  - a new specialist skill,
  - an extension to an existing skill, or
  - a router concern for `using-agent-skills`.
- Keep routers thin. Put specialist guidance in the specialist skill.

### 2. Define the job boundary

Write down:

- Primary job of the skill
- What should trigger it
- What adjacent skills it should hand off to
- What it explicitly does not own

If two skills would trigger on the same requests, narrow one or both
descriptions until the handoff is obvious.

### 3. Draft the skill

Create `.agents/skills/<skill-name>/SKILL.md` with:

- concise frontmatter
- a short overview
- project-specific workflow steps
- verification steps

Keep instructions procedural. Avoid background theory unless the theory changes
execution decisions.

### 4. Add resources only when they earn their cost

Add `references/` when:

- the skill needs repo-specific schemas, conventions, or checklists
- the extra detail would bloat `SKILL.md`

Add `scripts/` when:

- a deterministic helper prevents repeated code generation
- validation or transformation is fragile enough to automate

### 5. Update the router when needed

If the new skill changes discovery behavior, patch
`using-agent-skills/SKILL.md` so future sessions know when to route to it.

### 6. Mirror and verify

After edits:

1. Run `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1`
2. Run `python scripts/validate_skills.py`
3. Run `git diff --check -- .agents/skills .claude/skills`
4. Spot-check the mirrored `SKILL.md`

## Merge Guidance

When two skills overlap:

- Keep the narrower workflow as a specialist skill.
- Keep `using-agent-skills` as the dispatcher.
- Merge only when both files truly own the same job.
- If one skill is repo-specific and the other is generic, prefer the repo-
  specific one and import only the useful heuristics from the generic source.

## Red Flags

- A router that tries to teach every specialist workflow
- Two skills with nearly identical trigger descriptions
- Copying an external skill's file layout when it conflicts with repo norms
- Adding resources that no one will load or execute
- Forgetting to sync `.claude/skills` after editing `.agents/skills`
- Skipping `scripts/validate_skills.py`; manual review alone misses drift

## Verification

- [ ] New or updated descriptions trigger cleanly and do not collide badly
- [ ] Skill folder follows `.agents/skills/<name>/SKILL.md`
- [ ] Extra resources exist only when justified
- [ ] `using-agent-skills` is updated if discovery changed
- [ ] Claude mirror refreshed with `scripts/sync-skills.ps1`
- [ ] `python scripts/validate_skills.py` passes
- [ ] `git diff --check` is clean for skill files
