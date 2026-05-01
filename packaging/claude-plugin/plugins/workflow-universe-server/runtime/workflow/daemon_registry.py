"""Project-wide daemon identity facade.

This module presents daemon/soul language while the existing SQLite
substrate still stores rows in the transitional author_* tables. The mapping
keeps the migration additive: public callers use daemon_id, while storage can
move later without changing the caller contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow import daemon_server

SOULLESS_SOUL_TEXT = "Default soulless daemon. Uses the platform dispatcher policy."
VALID_SOUL_MODES = {"soul", "soulless"}
PROJECT_LOOP_FLAG = "project_loop_default"


def _daemon_id_from_author_id(author_id: str) -> str:
    if author_id.startswith("author::"):
        return "daemon::" + author_id[len("author::"):]
    return author_id


def _author_id_from_daemon_id(daemon_id: str) -> str:
    if daemon_id.startswith("daemon::"):
        return "author::" + daemon_id[len("daemon::"):]
    return daemon_id


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    return dict(meta) if isinstance(meta, dict) else {}


def _soul_mode(row: dict[str, Any]) -> str:
    meta = _metadata(row)
    raw = str(meta.get("daemon_soul_mode") or "").strip()
    if raw in VALID_SOUL_MODES:
        return raw
    if meta.get("auto_created"):
        return "soulless"
    soul_text = str(row.get("soul_text") or "")
    return "soulless" if soul_text == SOULLESS_SOUL_TEXT else "soul"


def _domain_claims(row: dict[str, Any]) -> list[str]:
    raw = _metadata(row).get("domain_claims", [])
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _daemon_from_author(row: dict[str, Any], *, include_soul: bool = False) -> dict[str, Any]:
    mode = _soul_mode(row)
    out = {
        "daemon_id": _daemon_id_from_author_id(str(row["author_id"])),
        "legacy_author_id": str(row["author_id"]),
        "display_name": str(row["display_name"]),
        "soul_hash": str(row["soul_hash"]),
        "soul_mode": mode,
        "has_soul": mode == "soul",
        "domain_claims": _domain_claims(row),
        "lineage_parent_id": (
            _daemon_id_from_author_id(str(row["lineage_parent_id"]))
            if row.get("lineage_parent_id")
            else None
        ),
        "reputation_score": float(row.get("reputation_score") or 0.0),
        "created_at": row.get("created_at"),
        "metadata": _metadata(row),
    }
    if include_soul:
        out["soul_text"] = str(row.get("soul_text") or "")
    return out


def _runtime_from_author_runtime(
    row: dict[str, Any],
    *,
    daemon: dict[str, Any] | None = None,
) -> dict[str, Any]:
    daemon_id = (
        daemon["daemon_id"]
        if daemon is not None
        else _daemon_id_from_author_id(str(row["author_id"]))
    )
    return {
        "runtime_instance_id": str(row["instance_id"]),
        "daemon_id": daemon_id,
        "legacy_author_id": str(row["author_id"]),
        "universe_id": str(row["universe_id"]),
        "provider_name": str(row["provider_name"]),
        "model_name": str(row["model_name"]),
        "branch_id": row.get("branch_id"),
        "status": str(row["status"]),
        "created_by": str(row["created_by"]),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "metadata": dict(row.get("metadata") or {}),
    }


def create_daemon(
    base_path: str | Path,
    *,
    display_name: str,
    created_by: str,
    soul_mode: str | None = None,
    soul_text: str = "",
    domain_claims: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or return a named daemon identity.

    ``soul_mode="soulless"`` creates the default platform-dispatcher daemon.
    ``soul_mode="soul"`` requires non-empty ``soul_text`` and records optional
    domain claims for future node/gate eligibility checks.
    """
    name = display_name.strip()
    if not name:
        raise ValueError("display_name is required")
    daemon_server.initialize_author_server(base_path)

    mode = (soul_mode or ("soul" if soul_text.strip() else "soulless")).strip()
    if mode not in VALID_SOUL_MODES:
        raise ValueError(f"soul_mode must be one of {sorted(VALID_SOUL_MODES)}")
    if mode == "soul" and not soul_text.strip():
        raise ValueError("soul_text is required when soul_mode='soul'")

    clean_claims = [
        str(item).strip()
        for item in (domain_claims or [])
        if str(item).strip()
    ]
    merged_metadata = dict(metadata or {})
    merged_metadata.update({
        "daemon_registry": True,
        "daemon_soul_mode": mode,
        "domain_claims": clean_claims,
    })
    if mode == "soul":
        merged_metadata["daemon_wiki"] = {
            "host_local": True,
            "schema_version": 1,
        }

    author = daemon_server.register_author(
        base_path,
        display_name=name,
        soul_text=soul_text.strip() if mode == "soul" else SOULLESS_SOUL_TEXT,
        created_by=created_by,
        metadata=merged_metadata,
    )
    daemon = _daemon_from_author(author, include_soul=False)
    if mode == "soul":
        from workflow.daemon_wiki import scaffold_daemon_wiki

        scaffold_daemon_wiki(base_path, daemon=daemon, soul_text=soul_text)
    return daemon


def list_daemons(base_path: str | Path) -> list[dict[str, Any]]:
    daemon_server.initialize_author_server(base_path)
    return [
        _daemon_from_author(row, include_soul=False)
        for row in daemon_server.list_authors(base_path)
    ]


def _is_project_loop_daemon(daemon: dict[str, Any]) -> bool:
    metadata = daemon.get("metadata")
    if not isinstance(metadata, dict):
        return False
    if not daemon.get("has_soul"):
        return False
    return bool(
        metadata.get(PROJECT_LOOP_FLAG)
        or (
            metadata.get("project_default")
            and metadata.get("loop_primary")
        )
    )


def select_project_loop_daemon(
    base_path: str | Path,
    *,
    include_soul: bool = False,
) -> dict[str, Any] | None:
    """Return the latest soul-bearing daemon marked as the project loop default.

    The autonomous loop still has a deterministic soulless fallback. This
    selector only opts into a soul when the host explicitly marked that daemon
    as the project loop default.
    """
    daemon_server.initialize_author_server(base_path)
    for daemon in reversed(list_daemons(base_path)):
        if _is_project_loop_daemon(daemon):
            if include_soul:
                return get_daemon(
                    base_path,
                    daemon_id=daemon["daemon_id"],
                    include_soul=True,
                )
            return daemon
    return None


def get_daemon(
    base_path: str | Path,
    *,
    daemon_id: str,
    include_soul: bool = False,
) -> dict[str, Any]:
    daemon_server.initialize_author_server(base_path)
    author_id = _author_id_from_daemon_id(daemon_id)
    row = daemon_server.get_author(base_path, author_id=author_id)
    return _daemon_from_author(row, include_soul=include_soul)


def summon_daemon(
    base_path: str | Path,
    *,
    daemon_id: str,
    universe_id: str,
    provider_name: str,
    model_name: str,
    created_by: str,
    branch_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    daemon_server.initialize_author_server(base_path)
    daemon = get_daemon(base_path, daemon_id=daemon_id)
    merged_metadata = dict(metadata or {})
    merged_metadata.update({
        "daemon_id": daemon["daemon_id"],
        "daemon_soul_hash": daemon["soul_hash"],
        "daemon_soul_mode": daemon["soul_mode"],
        "domain_claims": daemon["domain_claims"],
    })
    runtime = daemon_server.spawn_runtime_instance(
        base_path,
        universe_id=universe_id,
        author_id=daemon["legacy_author_id"],
        provider_name=provider_name,
        model_name=model_name,
        branch_id=branch_id,
        created_by=created_by,
        metadata=merged_metadata,
    )
    return _runtime_from_author_runtime(runtime, daemon=daemon)


def banish_daemon(
    base_path: str | Path,
    *,
    runtime_instance_id: str,
) -> dict[str, Any]:
    daemon_server.initialize_author_server(base_path)
    runtime = daemon_server.retire_runtime_instance(
        base_path,
        instance_id=runtime_instance_id,
    )
    return _runtime_from_author_runtime(runtime)


def list_runtime_instances(
    base_path: str | Path,
    *,
    universe_id: str | None = None,
) -> list[dict[str, Any]]:
    daemon_server.initialize_author_server(base_path)
    return [
        _runtime_from_author_runtime(row)
        for row in daemon_server.list_runtime_instances(
            base_path, universe_id=universe_id,
        )
    ]


def provider_capacity_warning(
    provider_name: str,
    *,
    running_count: int,
) -> dict[str, Any] | None:
    """Return advisory same-provider capacity guidance.

    This is deliberately warning-only. Workflow does not cap host fleet size.
    """
    if running_count <= 0:
        return None
    next_count = running_count + 1
    return {
        "provider_name": provider_name,
        "current_count": running_count,
        "next_count": next_count,
        "severity": "warning",
        "can_override": True,
        "message": (
            f"Launching daemon #{next_count} on {provider_name} may require "
            "additional subscription or rate-limit headroom. Workflow will not "
            "block this; confirm your provider plan can support it."
        ),
    }
