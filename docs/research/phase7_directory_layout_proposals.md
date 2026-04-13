# Phase 7 Directory Layout Proposals

## Purpose

Phase 7's pivot: scrap multi-tenant hosted runtime, treat a public
GitHub repo as the catalog. A workflow (Goal + Branches + Nodes) becomes
a small tree of plain files that a human can read on a phone, a bot
can edit via PR, and `grep` / `gh search` can discover.

This doc compares concrete directory shapes. Five candidates below,
each evaluated on:

1. **Phone-legibility** — opening one file on a 4-inch screen.
2. **Diff-friendliness** — what a typical PR looks like.
3. **Discoverability** — "show me every Branch for the research-paper Goal".
4. **Conflict rate** — two users editing in parallel.
5. **`node_ref` fit** — file path is the reuse reference.

The canonical file shape in every option is YAML + a body section. A
minimal Branch file:

```yaml
---
id: research-paper-pipeline
name: Research paper pipeline
goal: produce-academic-paper
author: dev-3
tags: [research, academic]
version: 3
nodes:
  - id: literature_scan
    ref: ../../nodes/literature_scan.yaml
  - id: rigor_checker
    ref: ../../nodes/rigor_checker.yaml
  - id: section_drafter
    inline:
      phase: draft
      prompt_template: |
        Draft section {section_name} given {outline}.
edges:
  - [START, literature_scan]
  - [literature_scan, rigor_checker]
  - [rigor_checker, section_drafter]
  - [section_drafter, END]
state_schema:
  - {name: outline, type: str}
  - {name: section_name, type: str}
---
# Research paper pipeline

Produces a draft academic paper from a literature scan, rigor audit,
and section-by-section drafting.
```

Two things worth noting up front that are shape-independent:

- **`node_ref` becomes a file path.** Wherever a Branch reuses a Node,
  it cites a relative or canonical path. Path shape varies by option.
- **YAML-frontmatter + markdown body** keeps the file phone-legible: a
  reader sees the description/docs without wading through the spec.

---

## Option A — Flat per-type

```
goals/
  produce-academic-paper.yaml
  plan-wedding.yaml
  track-recipes.yaml
branches/
  research-paper-pipeline.yaml
  fast-position-paper.yaml
  prosecutorial-brief.yaml
  wedding-planner-v1.yaml
nodes/
  literature_scan.yaml
  rigor_checker.yaml
  outline_drafter.yaml
  ...
```

**Phone-legibility.** Very good. Every file is small and single-purpose.
One click = one concept.

**Diff-friendliness.** Excellent. A Branch edit is one-file; a Node edit
is one-file. Per-type directories mean rename churn is rare.

**Discoverability.** Medium. "Show me every Branch for the
research-paper Goal" is not direct — requires grepping each Branch file's
`goal:` frontmatter. Tolerable at 100 branches, awkward at 10K.

**Conflict rate.** Low. Two users adding different Branches never touch
the same file. Two users editing the SAME Branch (e.g. iterating) do
conflict — unavoidable in any shape.

**`node_ref` fit.** Natural. `ref: nodes/rigor_checker.yaml` from
any Branch. One canonical node path. No duplication.

**Downside.** No structural signal of Goal membership. A Branch "belongs"
to a Goal only via frontmatter. Renaming a Goal requires a rewrite of
every Branch that referenced it.

---

## Option B — Nested by Goal

```
goals/
  produce-academic-paper/
    goal.yaml
    branches/
      research-paper-pipeline/
        branch.yaml
        nodes/
          rigor_checker.yaml
          section_drafter.yaml
      fast-position-paper/
        branch.yaml
        nodes/
          skim_synthesizer.yaml
  plan-wedding/
    goal.yaml
    branches/
      wedding-planner-v1/
        branch.yaml
        nodes/
          guest_list.yaml
```

**Phone-legibility.** Good for reading. Deep nesting is fine on a phone
because you navigate one level at a time.

**Diff-friendliness.** Mixed. Single-Goal PRs look clean. Cross-Goal
edits (e.g. retagging 5 Branches) span many directories.

**Discoverability.** Excellent for Goal-scoped queries. `ls
goals/produce-academic-paper/branches/` answers immediately.
Cross-Goal discovery (Option B's weakness) requires a walk.

**Conflict rate.** Low. The same tree structure that eases discovery
also prevents conflicts across Goals.

**`node_ref` fit.** Awkward. Reusing `rigor_checker` from
`research-paper-pipeline` in `prosecutorial-brief` (a different
Goal) means either:
- Duplicate the Node under both Goals (diverges).
- Reference across Goal boundaries:
  `../../../produce-academic-paper/branches/research-paper-pipeline/nodes/rigor_checker.yaml`
  which is both ugly and fragile under Branch renames.

**Major downside.** Cross-Goal reuse — the exact scenario Mission 5
surfaced — is the worst case. The tree's strength (Goal ownership)
penalizes the behavior we want to encourage.

---

## Option C — Author-namespaced with curated Goals

```
users/
  dev-3/
    branches/
      research-paper-pipeline.yaml
      prosecutorial-brief.yaml
    nodes/
      rigor_checker.yaml
  alice/
    branches/
      alice-wedding-v1.yaml
    nodes/
      venue_scout.yaml
goals/
  produce-academic-paper.yaml   # curated shared
  plan-wedding.yaml
```

**Phone-legibility.** Very good. Small files, clear ownership.

**Diff-friendliness.** Excellent for the common case: a user edits
their own tree and doesn't touch shared Goals.

**Discoverability.** Mixed. Per-author discovery is trivial
(`ls users/dev-3/branches/`). "All Branches for the research-paper
Goal" still requires a grep across `users/*/branches/`. Curated Goal
metadata lives in `goals/` but the Branches don't.

**Conflict rate.** Very low. Author namespacing eliminates most
collisions. Forks land in the forker's own tree; no race on the
original author's files.

**`node_ref` fit.** Natural but asymmetric. Reusing your own Node
is a short relative path. Reusing another user's Node is a longer
absolute-style path (`users/alice/nodes/venue_scout.yaml`) which is
fine but makes ownership visible in every reuse reference.

**Downside.** Goal↔Branch linkage is weaker than B. `produce-academic-paper.yaml`
is just a curated descriptor; Branches live elsewhere. Good for a git-native
world where curation is by community convention, not filesystem
structure.

**Cultural property worth noting.** This shape matches how
dotfiles-style repos work on GitHub today: `users/<name>/...` is a
familiar pattern. New contributors add their own subtree without
asking. Review burden on shared directories (`goals/`) stays low.

---

## Option D — Flat with lineage index

```
goals/
  produce-academic-paper.yaml
  plan-wedding.yaml
branches/
  research-paper-pipeline.yaml
  fast-position-paper.yaml
nodes/
  rigor_checker.yaml
  literature_scan.yaml
indexes/
  by-goal.yaml              # auto-generated
  by-author.yaml            # auto-generated
  node-reuse.yaml           # auto-generated
```

**Phone-legibility.** Very good (matches A).

**Diff-friendliness.** Very good (matches A). Index files regenerate
via a CI job so PRs don't need to hand-edit them.

**Discoverability.** Excellent. Pre-computed indexes answer the same
queries that Option B/C need a walk for. `cat
indexes/by-goal.yaml` lists every Branch per Goal.

**Conflict rate.** Same as A. Indexes regenerate automatically and
never conflict on PR because the workflow bot owns that file.

**`node_ref` fit.** Same as A — single canonical path.

**Downside.** Index files are derived state. Requires a CI job
(GitHub Action) that regenerates on every merge. Adds infrastructure.
If the index falls out of sync with frontmatter, confusion follows.

**Cultural property.** Derived indexes are standard practice in
package ecosystems (e.g. pip indexes, Homebrew bottles). Low
cognitive cost once the contributor-facing instruction is just
"don't edit files under `indexes/`".

---

## Option E — Content-addressed Nodes, flat Branches/Goals

```
goals/
  produce-academic-paper.yaml
branches/
  research-paper-pipeline.yaml
nodes/
  sha/
    a3f9c2b1/node.yaml       # canonical, immutable
    a3f9c2b1/rigor_checker/  # human-readable alias
  alias/
    rigor_checker -> sha/a3f9c2b1/
    rigor_checker@v2 -> sha/7e1fd02c/
```

**Phone-legibility.** Mixed. Files are small, but the sha layer is a
human speed bump.

**Diff-friendliness.** High for Node edits (create a new sha, update
the alias symlink — small PR). But the symlink/alias step is
non-obvious.

**Discoverability.** Good via aliases, confusing via raw paths.

**Conflict rate.** Very low for Nodes. Immutability means contributors
never overwrite. Alias updates are single-file but can race.

**`node_ref` fit.** **Best** for reuse semantics: a Branch references
either an immutable sha (`nodes/sha/a3f9c2b1/node.yaml`) or an alias
(`nodes/alias/rigor_checker`). Matches the snapshot-vs-live-ref
distinction from #66: sha ref = copy-of-exactly-this-body. Alias ref
= live reference that tracks updates.

**Downside.** Heavier mental model. Contributors have to understand
sha addressing. Git already content-addresses the whole repo so
this adds a parallel scheme.

**When it earns its complexity.** Only if the community needs the
sha-vs-alias distinction at the file-path level. `node_ref` with
`intent="copy"` vs `intent="reference"` already carries this meaning
at the tool layer — the file layout doesn't have to.

---

## Comparison matrix

| Criterion | A Flat | B Nested | C Authored | D Flat+Index | E Content-addressed |
|-----------|:------:|:--------:|:----------:|:------------:|:-------------------:|
| Phone-legibility | +++ | ++ | +++ | +++ | + |
| Diff-friendliness | +++ | ++ | +++ | +++ | ++ |
| Goal discoverability | + | +++ | + | +++ | + |
| Cross-Goal discoverability | + | - | + | +++ | + |
| Conflict rate (low = better) | +++ | +++ | ++++ | +++ | ++++ |
| node_ref fit (same Goal) | +++ | +++ | ++ | +++ | +++ |
| node_ref fit (cross Goal) | +++ | - | ++ | +++ | +++ |
| Infrastructure burden | 0 | 0 | 0 | CI index job | sha/alias tooling |
| Onboarding friction | low | low | very low | low | medium |

---

## Recommendation

**Lean toward D (Flat with lineage index)** as the primary shape.

Rationale:
1. Inherits Option A's strengths (phone-legibility, low conflict rate,
   natural `node_ref` paths) without its one weakness (discoverability).
2. Indexes are cheap — a ~100-line GitHub Action can regenerate them
   from frontmatter. STATUS.md already has a docs conventions section;
   an `indexes/` subdirectory fits the project's existing patterns.
3. The Mission 5/6 insight that triggered #62 and #66 — "bot should
   reuse `rigor_checker` across research-paper and prosecutorial-brief
   Goals" — maps cleanly. Cross-Goal discovery is a single
   `cat indexes/node-reuse.yaml`. No symlinks, no deep paths.
4. Option C is very close runner-up. If community identity matters
   more than automated discovery (e.g. "this is Alice's research
   pipeline"), Option C is better. The two could combine: `users/`
   tree for authoring + `indexes/` derived surfaces for discovery.

## Open questions worth resolving before the executable spec

1. **Do Goals get their own files or are they inferred from Branch
   frontmatter?** A separates them; D preserves A's separation while
   auto-generating the Goal↔Branch index. I'd keep Goals as first-class
   files so they can carry description, tags, outcome metadata (#56
   ground truth).

2. **Versioning: frontmatter `version: N` vs git tags vs content-addressed
   subdirs?** Git already gives per-commit versioning; duplicating that
   in the file feels redundant. Use `version:` only as a user-facing
   display. `git log goals/...` is the durable audit.

3. **Inline vs referenced Nodes inside a Branch?** The example spec
   above allows both (`ref:` path or `inline:` body). Option E's
   sha addressing would force all Nodes to be referenced, which is
   probably too prescriptive for v1.

4. **Authoring flow through `extensions action=build_branch`**:
   the MCP tool would write files into this tree as the primary
   effect, not a SQLite row. The `author_server.py` SQLite store
   becomes a cache layer, not the source of truth. Worth a separate
   spec.

5. **Search semantics.** #62 Part B's `search_nodes` currently walks
   SQLite. In a git-native world it walks the filesystem (or uses
   GitHub's search API). The tool-layer contract doesn't change; the
   implementation does.

## Next

Explorer-2's broader git-native research will surface constraints I
haven't considered (branch protection rules, review workflows, rate
limits on the GitHub Search API for live lookups). Aligning this
directory doc with their findings produces the first executable
spec pass.
