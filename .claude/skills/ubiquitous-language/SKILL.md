---
name: ubiquitous-language
description: Hardens project terminology so one concept has one name across code, docs, and tickets. Use when terms drift, aliases accumulate, concepts are overloaded, or a glossary or naming cleanup is needed.
---

# Ubiquitous Language

## Overview

Remove naming drift. Make domain terms crisp enough that humans and agents stop
using one word for multiple concepts or multiple words for one concept.

## Project Conventions

Workflow does not use a top-level `CONTEXT.md` convention today. Durable term
definitions belong in the existing truth surfaces:

- `PLAN.md` for architectural terms and stable concepts
- vetted specs or design notes for scoped concept work
- `STATUS.md` only for active live concerns, not permanent glossary entries

Do not create a parallel glossary system unless the repo explicitly adopts one.

## Workflow

### 1. Gather terms from all three surfaces

Collect candidate terms from:

- user language
- code identifiers
- `PLAN.md`, specs, and design notes
- issue or status wording

### 2. Find drift

Flag:

- one term used for multiple concepts
- multiple terms used for the same concept
- legacy aliases that still leak into active code
- marketing words that conflict with implementation words

### 3. Pick canonical language

For each conflict, define:

- canonical term
- short definition
- what it is not
- acceptable aliases, if any

If the choice affects architecture or public behavior, route the durable record
into `PLAN.md` or a design note instead of leaving it in chat.

### 4. Reconcile code and docs

Check whether code, docs, and user language agree. If not, say which one is
current, which one is historical, and which one should become canonical.

### 5. Propagate with scope discipline

Rename only in the requested or justified scope. Large sweeps need approval.
Prefer boundary-first cleanup over repo-wide cosmetic churn.

## Output Shape

Use a compact table or bullet list:

- term
- meaning
- ambiguous or rejected alternatives
- recommended next rename or doc update

## Verification

- [ ] Each canonical term maps to one concept
- [ ] Overloaded terms are called out explicitly
- [ ] Durable terminology updates land in existing repo truth surfaces
- [ ] Renames stay within approved scope
- [ ] Code and docs are not left contradicting each other silently
