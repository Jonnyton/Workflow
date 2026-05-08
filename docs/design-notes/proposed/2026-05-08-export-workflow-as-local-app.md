---
title: Export Workflow As Local App
date: 2026-05-08
author: codex-wiki-patch
status: proposed
request_id: WIKI-PATCH
github_issue: 440
wiki_source: pages/patch-requests/pr-038-workflow-needs-an-export-as-app-primitive-bundle-a-workflow-.md
scope: design-only; no runtime code in this branch
builds_on:
  - PLAN.md#scoping-rules
  - PLAN.md#user-capability-axis-browser-only-vs-local-app-across-providers
  - PLAN.md#distribution-and-discoverability
  - docs/mcpb_packaging.md
  - docs/specs/multi-provider-tray-runtime.md
primitive_collision_check:
  - "2026-05-08: python scripts/check_primitive_exists.py action export_as_app -> CLEAN on origin/main"
  - "2026-05-08: python scripts/check_primitive_exists.py action bundle_workflow_app -> CLEAN on origin/main"
---

# Export Workflow As Local App

## 1. Classification

Issue #440 is a project-design request, not a mechanical runtime patch. It
asks Workflow to add an "export as app" primitive that turns a workflow into a
runnable local desktop application. That crosses three architectural surfaces:
the public primitive set, local-app capability tier, and distribution
packaging.

Per the PLAN scoping rules, this branch should not add a new MCP action or
desktop packager directly. The useful patch is to define the smallest platform
shape that could later satisfy the request without crowding the primitive
surface with a convenience wrapper.

## 2. Recommendation Summary

Do not ship a broad `export_as_app` MCP primitive as the first step. Treat the
request as a missing **portable workflow application package** contract:
a deterministic bundle manifest plus a local runner entry point that can be
wrapped by existing distribution layers.

The platform-owned primitive, if accepted, should be narrower than "make me an
app":

1. Resolve a workflow, its approved nodes, required capabilities, and local
   run policy into a signed package manifest.
2. Materialize a reproducible local run directory from that manifest.
3. Launch it through the existing local Workflow runtime/tray path, with host
   approval for file writes, external tools, credentials, and software installs.

Desktop shortcuts, OS installers, icons, and branded shells are wrapper layers.
They can be community-evolved around the package contract rather than becoming
first-class platform primitives.

## 3. Smallest Useful Shape

### Workflow App Manifest

The manifest is the actual primitive candidate. It is stable, inspectable, and
host-verifiable:

```yaml
format: workflow.local_app.v1
workflow_ref:
  universe_id: "..."
  branch_id: "..."
  run_id: "optional pinned run"
entry:
  node_id: "..."
  command: "workflow run-app --manifest workflow-app.yaml"
capabilities:
  required:
    - filesystem.read
    - filesystem.write
    - external_tool.invoke
  optional:
    - desktop.tray
    - desktop.shortcut
artifacts:
  include:
    - nodes/**
    - branches/**
    - workflow.lock
host_policy:
  network: disabled_by_default
  writes: prompt
  external_tools: prompt
provenance:
  exported_by: "..."
  exported_at: "2026-05-08T00:00:00Z"
  source_commit: "optional"
  manifest_sha256: "..."
```

The manifest does not embed private platform data. Private workflow content
stays host-local per commons-first architecture. Public/community templates may
be referenced by stable IDs and rehydrated from the commons.

### Local Runner

The runner should reuse existing local-app surfaces:

- `workflow.desktop` provides tray, launcher, notifications, and shortcuts.
- `workflow.__main__` already owns local CLI startup and tray flags.
- `packaging/mcpb` and the Claude plugin already stage the portable Workflow
  runtime from `workflow/`.

The future implementation should add a small runner command that accepts a
manifest path, validates it, checks host approvals, and starts the pinned
workflow. The command can be wrapped by desktop shortcut generation without
making shortcut generation part of the core primitive.

## 4. Why This Clears The Scoping Rules

**Minimal primitives.** A one-click desktop app builder is a convenience. The
irreducible gap is the portable, deterministic package contract that lets many
app wrappers exist without each wrapper inventing its own semantics.

**Community-build over platform-build.** The community can evolve launchers,
icons, branded shells, Electron/Tauri wrappers, and domain-specific templates
once the manifest contract exists. The platform should own only the contract
and safety checks that must be consistent.

**Commons-first.** Exporting a private workflow must not upload private content
to the platform. The package is built and run on the host. Public commons
content can be referenced or vendored according to explicit manifest policy.

**User capability axis.** Browser-only users can request an export and receive
a package artifact when a host is available. Local-app users can build and run
the package immediately. The primitive should produce the same manifest across
Claude, ChatGPT, and future MCP hosts; only artifact delivery and launch differ.

## 5. Security And Approval Boundaries

The exported app must not become a bypass around Workflow's existing local
software safety model:

- Every required capability is declared before launch.
- External tool invocation remains host-approved and isolated.
- File writes default to prompt or a manifest-scoped directory.
- Credentials are references to host secret slots, never bundled values.
- Network access defaults off unless declared and approved.
- Source-code nodes still require the existing host approval path before run.
- The manifest is hashed before launch; any post-export mutation invalidates
  the provenance receipt unless explicitly re-signed by the host.

## 6. Proposed Build Ladder

1. **Design acceptance.** Approve or revise this manifest-first shape in
   PLAN.md before runtime work.
2. **Manifest schema.** Add a typed schema and parser with fixture tests for
   valid packages, missing capabilities, path traversal, and malformed
   provenance.
3. **Dry-run exporter.** Add a non-launching command that resolves a workflow
   into a manifest and run directory, then reports required host approvals.
4. **Local runner.** Add `workflow run-app --manifest ...` with no desktop
   shortcut generation.
5. **Desktop wrapper.** Reuse `workflow.desktop.create_shortcut` to point at
   the runner only after the manifest and runner are proven.
6. **MCP surface decision.** Add a chatbot-visible action only if users cannot
   reliably compose the dry-run/export/launch flow from existing primitives.

## 7. Acceptance Gates For Runtime Work

Runtime implementation should not be considered done until it has:

- Unit tests for manifest parsing, path validation, capability declarations,
  and credential non-bundling.
- Focused integration tests that export and dry-run a tiny workflow from a temp
  directory without network or global filesystem writes.
- A local-app smoke test for `workflow run-app --manifest ...`.
- Packaging checks showing the new runner stages into MCPB and the Claude
  plugin mirror.
- Real chatbot-surface proof if a public MCP action is eventually added.

## 8. Open Questions

- What is the canonical workflow reference for export: branch head, run result,
  approved node set, or a new immutable package snapshot?
- Should exported apps be reproducible from public commons IDs alone, or always
  vendor their resolved public dependencies?
- Which host signs a package when the requesting user is browser-only and the
  build happens on a donated/community host?
- Does the first implementation need cross-platform shortcut support, or is a
  manifest plus CLI runner sufficient for v1?

## 9. Non-Goals

- No runtime MCP action in this branch.
- No Electron, Tauri, PyInstaller, DMG, MSI, or app-store packaging decision.
- No bundled credentials.
- No platform storage for private workflow content.
- No new desktop UX until the manifest/runner contract is accepted.
