# Claude Plugin Packaging

This directory contains the Workflow plugin marketplace surface plus the
packaged `workflow-universe-server` plugin.

## Core

- [Plugin README](plugins/workflow-universe-server/README.md)

## Structure

- `.claude-plugin/marketplace.json` - marketplace manifest
- `plugins/workflow-universe-server/` - packaged plugin contents

## Notes

- The packaged plugin carries its own end-user slash-command skills. Those are
  plugin assets, not main project workflow skills.
