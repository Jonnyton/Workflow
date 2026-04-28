"""Status subsystem — extracted from workflow/universe_server.py (Task #10).

Houses the `get_status` MCP-tool body and its `_policy_hash` helper. The MCP
tool decoration stays in `workflow/universe_server.py` (Pattern A2 from
``docs/exec-plans/active/2026-04-26-decomp-step-2-prep.md`` §4 — same as Task
#9 wiki extraction). The decorated tool there delegates to the plain
``get_status(...)`` function below.

Public surface (test imports continue to land via ``workflow.universe_server``
back-compat re-exports):
    get_status(universe_id="")  → str: full daemon status JSON
    _policy_hash(payload)       → str: deterministic sha256 of policy payload

Cross-module note: ``_parse_activity_line`` lives in ``workflow.universe_server``
(L~3346) and is lazy-imported inside ``get_status`` to avoid a circular import
at module load time (universe_server imports this module's ``get_status`` for
the back-compat re-export shim). All other lazy imports (dispatcher, storage,
providers.router, providers.base, storage.rotation) follow the pattern that
was already in place pre-extraction.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from workflow.api.helpers import _default_universe, _universe_dir


def _policy_hash(payload: dict[str, Any]) -> str:
    """Deterministic sha256 of sorted-JSON policy payload.

    Chatbot-side callers can compare the hash across calls to detect
    config drift. Hashing sorted JSON means key-order + whitespace
    don't perturb the fingerprint.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_status(universe_id: str = "") -> str:
    """Factual snapshot of the daemon's identity + routing config.

    See the chatbot-facing docstring on the @mcp.tool wrapper in
    ``workflow.universe_server`` — this implementation is what the
    decorated tool delegates to.
    """
    uid = universe_id or _default_universe()
    udir = _universe_dir(uid)
    universe_exists = udir.is_dir()
    host_id = os.environ.get("UNIVERSE_SERVER_HOST_USER", "host")

    # Load the dispatcher config for the universe.
    try:
        from workflow.dispatcher import (
            DispatcherConfig,
            load_dispatcher_config,
            paid_market_enabled,
        )
        cfg: DispatcherConfig = load_dispatcher_config(udir)
    except Exception as exc:
        return json.dumps({
            "error": "config_load_failed",
            "detail": str(exc),
            "universe_id": uid,
            "universe_exists": universe_exists,
        })

    served_llm_type = (cfg.served_llm_type or "").strip()
    import shutil as _shutil
    # Priority chain mirrors the provider-router's preference order:
    # local/bound endpoints beat SDK-key-only providers. Ollama is
    # always-local; anthropic is host-controlled relay; codex+claude
    # are subprocess-bound CLIs the daemon can drive; xai/gemini/groq
    # are SDK-key-keyed network providers (task #14 additions).
    if os.environ.get("OLLAMA_HOST"):
        endpoint_hint = "ollama"
    elif os.environ.get("ANTHROPIC_BASE_URL"):
        endpoint_hint = "anthropic"
    elif os.environ.get("OPENAI_API_KEY") and _shutil.which("codex"):
        endpoint_hint = "codex"
    elif _shutil.which("claude"):
        endpoint_hint = "claude"
    elif os.environ.get("XAI_API_KEY"):
        endpoint_hint = "xai"
    elif os.environ.get("GEMINI_API_KEY"):
        endpoint_hint = "gemini"
    elif os.environ.get("GROQ_API_KEY"):
        endpoint_hint = "groq"
    else:
        endpoint_hint = "unset"

    tier_routing_policy = {
        "served_llm_type": served_llm_type or "any",
        "accept_external_requests": cfg.accept_external_requests,
        "accept_goal_pool": cfg.accept_goal_pool,
        "accept_paid_bids": cfg.accept_paid_bids,
        "allow_opportunistic": cfg.allow_opportunistic,
        "paid_market_flag_on": paid_market_enabled(),
        "tier_status_map": cfg.tier_status_map(),
    }

    # Pull the last N lines of activity.log for evidence of what actually
    # ran recently — chatbot cites this when narrating trust claims.
    activity_tail: list[str] = []
    last_n_calls: list[dict[str, str]] = []
    last_completed_llm = "unknown"
    total_log_lines = 0
    log_path = udir / "activity.log"
    log_read_ok = True
    if log_path.exists():
        try:
            content = log_path.read_text(encoding="utf-8").strip()
            if content:
                # Lazy-import _parse_activity_line — defined in universe_server
                # which back-compat-imports get_status from this module. Lazy
                # avoids the load-time cycle.
                from workflow.api.universe import _parse_activity_line
                lines = content.splitlines()
                total_log_lines = len(lines)
                activity_tail = lines[-20:]
                # last_n_calls: structured parse of most-recent entries,
                # newest-first. Reuses _parse_activity_line so the shape
                # matches get_recent_events (dispatch_evidence idiom).
                last_n_calls = [
                    _parse_activity_line(line)
                    for line in reversed(lines[-10:])
                ]
                # Best-effort scan for "llm=" or "provider=" tokens in
                # recent lines. Legacy format varies; chatbot verifies by
                # reading the tail itself if this heuristic misses.
                for line in reversed(lines):
                    for token in ("llm=", "provider=", "model="):
                        idx = line.find(token)
                        if idx >= 0:
                            rest = line[idx + len(token):].split()[0]
                            last_completed_llm = rest.rstrip(",;)")
                            break
                    if last_completed_llm != "unknown":
                        break
        except Exception:  # noqa: BLE001 — best-effort evidence
            log_read_ok = False

    # Per-field caveats — chatbot cites only the degenerate keys instead
    # of wrapping every claim in the global caveat list.
    evidence_caveats: dict[str, list[str]] = {}
    if last_completed_llm == "unknown":
        evidence_caveats["last_completed_request_llm_used"] = [
            "Heuristic found no llm=/provider=/model= token in recent "
            "activity. Either the daemon has not completed a request, or "
            "the log format does not emit a provider token. Do not read "
            "'unknown' as 'no provider routing happened'."
        ]
    if not activity_tail:
        tail_caveats = [
            "activity.log is empty or missing — daemon has not run in "
            "this universe, or the log was cleared."
        ]
        if not log_read_ok:
            tail_caveats.append(
                "activity.log read failed (I/O error). Tail not available."
            )
        evidence_caveats["activity_log_tail"] = tail_caveats
        evidence_caveats["last_n_calls"] = tail_caveats
    else:
        untagged = sum(1 for c in last_n_calls if not c.get("tag"))
        if untagged:
            evidence_caveats["last_n_calls"] = [
                f"{untagged} of {len(last_n_calls)} recent entries carry "
                "no tag (pre-tagging call sites or legacy entries). "
                "Tag-based filtering on these is unreliable."
            ]

    # Global caveats — apply regardless of which evidence field is read.
    caveats: list[str] = []
    if not served_llm_type:
        caveats.append(
            "served_llm_type is unset — daemon accepts ANY LLM type. "
            "Not a local-only guarantee."
        )
    if endpoint_hint == "unset":
        caveats.append(
            "No LLM provider detected (checked: OLLAMA_HOST, ANTHROPIC_BASE_URL, "
            "OPENAI_API_KEY+codex CLI, claude CLI, XAI_API_KEY, GEMINI_API_KEY, "
            "GROQ_API_KEY). Provider routing is at-call discretion."
        )
    caveats.append(
        "Legacy surface does NOT enforce per-universe sensitivity_tier. "
        "Full enforcement ships with spec #79 §13 tray observability in "
        "the rewrite. For confidential work today: pin served_llm_type + "
        "run locally + verify via this tool's evidence field."
    )

    # Actionable next steps — §10.7 canonical shape. Only surfaced when
    # the chatbot has something concrete it can do or recommend.
    actionable_next_steps: list[str] = []
    if not served_llm_type:
        actionable_next_steps.append(
            "Set served_llm_type in the dispatcher config to constrain "
            "which LLM types this daemon will accept work for."
        )
    if endpoint_hint == "unset":
        actionable_next_steps.append(
            "Bind an LLM provider: set OLLAMA_HOST (local Ollama), "
            "ANTHROPIC_BASE_URL (Anthropic relay), OPENAI_API_KEY with "
            "codex CLI on PATH, install the claude CLI, or set one of "
            "XAI_API_KEY / GEMINI_API_KEY / GROQ_API_KEY."
        )
    if last_completed_llm == "unknown" and activity_tail:
        actionable_next_steps.append(
            "Inspect the full activity_log_tail — provider token heuristic "
            "may have missed a non-standard format."
        )

    policy_payload = {
        "active_host": {
            "host_id": host_id,
            "served_llm_type": served_llm_type or "any",
            "llm_endpoint_bound": endpoint_hint,
        },
        "tier_routing_policy": tier_routing_policy,
    }

    if not universe_exists:
        caveats.append(
            f"Universe '{uid}' does not exist on disk. Daemon is reporting "
            "default-fallback identity, not a live universe. Call "
            "universe action=list to see what exists; universe action=create "
            "to bootstrap."
        )
        actionable_next_steps.append(
            f"Create universe '{uid}' or pick an existing one via universe "
            "action=list."
        )

    # BUG-023 Phase 1 — surface per-subsystem disk observability so
    # operators can see a storage-pressure signal via the same MCP probe
    # that carries routing evidence. Uptime canary pages on
    # pressure_level in {warn, critical}; this block never raises so a
    # bad stat call can't break the status probe.
    try:
        from workflow.storage import inspect_storage_utilization, path_size_bytes
        storage_utilization = inspect_storage_utilization()
        # BUG-032 — activity_log + universe_outputs live inside the universe
        # directory, not at data_dir() root; patch the per-subsystem byte
        # counts using the already-resolved udir.
        if "per_subsystem" in storage_utilization:
            storage_utilization["per_subsystem"]["activity_log"] = {
                "bytes": path_size_bytes(udir / "activity.log"),
                "path": str(udir / "activity.log"),
            }
            storage_utilization["per_subsystem"]["universe_outputs"] = {
                "bytes": path_size_bytes(udir / "output"),
                "path": str(udir / "output"),
            }
    except Exception as exc:  # noqa: BLE001 — best-effort observability
        storage_utilization = {
            "error": "inspect_failed",
            "detail": str(exc),
        }

    # session_boundary — explicit tool fact so the chatbot can ground
    # "no prior session context" without relying solely on prompt rules.
    # Scans the activity.log for any entry within the last 30 days that
    # can be attributed to the current account user. Best-effort; never
    # raises so a log-read error doesn't break the status probe.
    account_user = os.environ.get("UNIVERSE_SERVER_USER", "anonymous")
    prior_session_ts: str | None = None
    try:
        if activity_tail:
            import re as _re
            for line in reversed(activity_tail):
                if account_user in line:
                    ts_match = _re.match(r"\[(\d{4}-\d{2}-\d{2}[^\]]*)\]", line)
                    if ts_match:
                        prior_session_ts = ts_match.group(1)
                        break
    except Exception:  # noqa: BLE001
        pass

    if prior_session_ts:
        session_boundary = {
            "prior_session_context_available": True,
            "account_user": account_user,
            "last_session_ts": prior_session_ts,
            "note": (
                f"Activity log contains entries for account '{account_user}'. "
                "Prior session context may be available in the log."
            ),
        }
    else:
        session_boundary = {
            "prior_session_context_available": False,
            "account_user": account_user,
            "last_session_ts": None,
            "note": (
                f"No activity log entries found for account '{account_user}' "
                "in this universe's log. Chatbot has no prior session record "
                "to reference — do not assert prior session context."
            ),
        }

    # per_provider_cooldown_remaining (BUG-029 Part A observability): expose
    # per-provider cooldown seconds so the chatbot can narrate "claude-code:
    # 87s remaining" to an operator asking why nothing is happening.
    # Best-effort — a missing router or quota object yields an empty dict.
    per_provider_cooldown_remaining: dict[str, int] = {}
    try:
        from workflow.providers.router import FALLBACK_CHAINS
        all_provider_names: list[str] = list(
            dict.fromkeys(p for chain in FALLBACK_CHAINS.values() for p in chain)
        )
        from workflow.graph_compiler import _get_shared_router
        router = _get_shared_router()
        if router is not None and hasattr(router, "_quota"):
            per_provider_cooldown_remaining = (
                router._quota.cooldown_remaining_dict(all_provider_names)
            )
    except Exception:  # noqa: BLE001 — best-effort observability
        pass

    # sandbox_status: probe bwrap availability once per process (cached).
    # Never raises — a probe error shows as bwrap_available=False with reason.
    try:
        from workflow.providers.base import get_sandbox_status
        sandbox_status = get_sandbox_status()
    except Exception as exc:  # noqa: BLE001 — best-effort observability
        sandbox_status = {"bwrap_available": False, "reason": f"probe_error: {exc}"}

    # BUG-027 — probe required static data files so operators can see which
    # files are absent in the cloud image without waiting for ASP to fail.
    try:
        from workflow.storage.rotation import startup_file_probe
        missing_data_files = startup_file_probe()
    except Exception:  # noqa: BLE001 — best-effort observability
        missing_data_files = []

    response = {
        "schema_version": 1,
        "active_host": policy_payload["active_host"],
        "tier_routing_policy": tier_routing_policy,
        "evidence": {
            "last_completed_request_llm_used": last_completed_llm,
            "activity_log_tail": activity_tail,
            "activity_log_line_count": total_log_lines,
            "last_n_calls": last_n_calls,
            "policy_hash": _policy_hash(policy_payload),
        },
        "evidence_caveats": evidence_caveats,
        "caveats": caveats,
        "actionable_next_steps": actionable_next_steps,
        "session_boundary": session_boundary,
        "storage_utilization": storage_utilization,
        "per_provider_cooldown_remaining": per_provider_cooldown_remaining,
        "sandbox_status": sandbox_status,
        "missing_data_files": missing_data_files,
        "universe_id": uid,
        "universe_exists": universe_exists,
    }
    return json.dumps(response)
