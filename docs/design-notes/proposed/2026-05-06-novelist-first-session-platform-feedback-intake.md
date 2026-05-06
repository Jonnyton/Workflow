---
status: proposed
source_issue: https://github.com/Jonnyton/Workflow/issues/312
source_wiki_path: pages/design-proposals/design-002-novelist-first-session-platform-feedback-six-gaps-from-merid.md
request_kind: project-design
---

# Novelist First-Session Feedback Intake

**Date:** 2026-05-06
**Status:** Proposed intake recovery note, not an accepted platform design.
**Classification:** Project design.

## Context

Issue #312 was auto-filed from a wiki design page titled "Novelist
first-session platform feedback: six gaps from meridian-ashes
continuity-engine test." The issue body only contains metadata and a pointer
to the wiki path. The actual community-authored design page is not available
in this checkout or in GitHub raw content for `main` or the issue branch.

Verified 2026-05-06 UTC:

- Local search found no matching `design-002`, `meridian`, `meridian-ashes`,
  or `six gaps` design content in the repository.
- `https://api.github.com/repos/Jonnyton/Workflow/issues/312` contains only
  the wiki-sync pointer and request metadata.
- GitHub raw reads for the referenced wiki path on `main` and on
  `design-note-draft/issue-312-codex-25458109276` returned `404`.

The missing source page blocks a faithful design response. The title says
"six gaps," but the six gap descriptions, evidence, reproduction transcript,
and proposed remedies are absent.

## Recommendation

Treat this request as an **intake recovery** task until the community-authored
wiki body is restored. Do not infer the six gaps from the title.

The smallest useful project change is this proposed note: it preserves the
request in the design-note lane, records the exact evidence gap, and defines
the minimum source package needed before a daemon or human turns the request
into an architectural proposal.

## Required Source Package

Before implementation or PLAN.md changes, recover or re-file the missing wiki
content with these fields:

1. The six observed gaps, each with the user prompt or first-session step that
   exposed it.
2. The expected novelist-facing behavior, written in domain vocabulary.
3. The observed Workflow behavior, including whether the failure came from MCP
   tool discovery, daemon execution, retrieval/memory, domain API shape, or
   chatbot narration.
4. Evidence from the `meridian-ashes` continuity-engine test: transcript,
   trace, artifact paths, screenshots, or run identifiers.
5. A suggested classification per gap: engine primitive, fantasy-domain
   capability, chatbot-surface copy/tool metadata, retrieval/memory policy,
   onboarding/discoverability, or community-process issue.
6. Privacy notes for any story text, canon, or user-authored content included
   in the evidence.

## Design Constraints For The Follow-Up

Any follow-up design note should preserve the current PLAN.md boundaries:

- `workflow/` remains domain-agnostic infrastructure.
- Fantasy/novelist behavior belongs in the fantasy domain or in domain
  registration, not in shared engine naming.
- MCP clients are control stations; the daemon performs the creative or
  continuity work.
- Prefer small composable primitives over new overlapping tools.
- Generator, evaluator, and ground-truth evidence remain separate.

## Rejected Alternatives

### Draft the six gaps from the title

Rejected. The repo contains novelist continuity code and prior fiction-memory
designs, but using those to reconstruct this specific community report would
invent facts.

### Change runtime code now

Rejected. No implementation target is available, and the request is explicitly
architectural/project-design.

### Close the request as unworkable

Rejected. The filing is valid enough to preserve as a proposed design-note
lane. What is missing is the source body, not the project-design classification.

## Open Questions

1. Can the wiki-sync job recover the deleted or unsynced wiki page from its
   source store, branch artifact, or event payload?
2. Was `meridian-ashes` a private test whose content must be summarized or
   redacted before landing in the public repo?
3. Which provider should perform the opposite-family review once the real six
   gaps are restored?
4. Should wiki-change-sync reject future design issues when the referenced wiki
   body cannot be fetched, or file a distinct `missing-source` request instead?
5. Should the eventual follow-up split one note per gap if the gaps land across
   different boundaries such as engine API, fantasy-domain API, onboarding, and
   retrieval policy?

## Acceptance Gate For The Real Design

This note is complete when it lands as a placeholder and the issue remains
blocked on source recovery. The real design response is complete only after the
source package exists and a follow-up note maps each verified gap to an
accepted design boundary or an explicit non-goal.
