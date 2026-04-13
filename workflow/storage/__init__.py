"""Phase 7 — git-native storage backend.

Spec: ``docs/specs/phase7_github_as_catalog.md``. Phase 7.1 is the
storage layout + serializer with no git seam yet. Subsequent phases
bolt on ``git_bridge.py`` (7.2) and cutover the ~12 MCP write handlers
(7.3).

Exports:

- ``YamlRepoLayout`` — resolves repo-relative paths for Branches,
  Goals, Nodes, and sidecar metadata.
- ``branch_to_yaml_payload`` / ``branch_from_yaml_payload`` — YAML
  serialization for ``BranchDefinition`` with per-node extraction.
- ``goal_to_yaml_payload`` / ``goal_from_yaml_payload`` — same for
  Goal dicts.
- ``StorageBackend`` protocol with ``SqliteOnlyBackend`` (current
  default) and ``SqliteCachedBackend`` (writes YAML alongside the
  SQLite mirror; git op deferred to 7.2).

Reads stay through the SQLite cache for query performance. Writes go
through both backends when the cached variant is enabled. On clone /
pull the cache rebuilds from YAML via a separate tool (7.1 ships the
writer; 7.2 ships the reader-rehydration path).
"""

from workflow.storage.backend import (
    DirtyFileError,
    SqliteCachedBackend,
    SqliteOnlyBackend,
    StorageBackend,
)
from workflow.storage.layout import YamlRepoLayout
from workflow.storage.serializer import (
    branch_from_yaml_payload,
    branch_to_yaml_payload,
    goal_from_yaml_payload,
    goal_to_yaml_payload,
)

__all__ = [
    "DirtyFileError",
    "SqliteCachedBackend",
    "SqliteOnlyBackend",
    "StorageBackend",
    "YamlRepoLayout",
    "branch_from_yaml_payload",
    "branch_to_yaml_payload",
    "goal_from_yaml_payload",
    "goal_to_yaml_payload",
]
