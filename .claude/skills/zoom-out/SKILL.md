---
name: zoom-out
description: Builds a high-level map of relevant modules, callers, and boundaries before detailed work starts. Use when entering an unfamiliar area, the repo feels large, or you need broader context before changing code.
---

# Zoom Out

## Overview

Go up one layer of abstraction before diving in. The goal is a fast, usable map
of how the area fits into the bigger system.

## Workflow

### 1. Define the target area

Name the feature, module, workflow, or bug surface you are trying to
understand.

### 2. Trace inward

Identify the main entrypoints and callers:

- commands
- endpoints
- UI flows
- scheduled jobs
- tests that exercise the area

### 3. Trace outward

Identify the main dependencies and side effects:

- storage
- external services
- subprocesses
- background jobs
- config and environment

### 4. Mark the boundaries

Call out:

- handoff points between modules
- where policy lives
- where orchestration lives
- where I/O begins

### 5. Recommend the next skill

After the map, decide what to do next:

- `debugging-and-error-recovery` for failures
- `improve-codebase-architecture` for seam problems
- `test-driven-development` for behavior work
- `api-and-interface-design` for contracts

## Output Shape

Produce a compact map with:

- mission of the area
- main files or modules
- inbound callers
- outbound dependencies
- key invariants
- recommended next move

## Verification

- [ ] The map includes both callers and dependencies
- [ ] Boundaries between orchestration, policy, and I/O are named
- [ ] The recommended next skill matches the real problem
