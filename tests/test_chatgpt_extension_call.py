"""BUG-034: compact extension_call route for clients that reject extensions."""

from __future__ import annotations

import inspect
import json

from workflow import universe_server as us
from workflow.api.prompts import _CONTROL_STATION_PROMPT


def test_extension_call_has_small_public_signature() -> None:
    """The fallback must stay much smaller than the large extensions schema."""
    extension_params = inspect.signature(us.extensions).parameters
    compact_params = inspect.signature(us.extension_call).parameters

    assert len(extension_params) > 80
    assert len(compact_params) <= 9
    assert {"action", "args_json", "branch_def_id", "spec_json"}.issubset(
        compact_params
    )


def test_extension_call_rejects_non_object_args_json() -> None:
    result = json.loads(us.extension_call(action="list_branches", args_json="[]"))

    assert result["error"] == "args_json must decode to a JSON object"


def test_extension_call_delegates_to_extensions_impl(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_extensions_impl(**kwargs: object) -> str:
        seen.update(kwargs)
        return json.dumps({"status": "ok", "received": kwargs})

    monkeypatch.setattr(us, "_extensions_impl", fake_extensions_impl)

    result = json.loads(us.extension_call(
        action="patch_branch",
        branch_def_id="Climate Claim Checker",
        changes_json='[{"op":"set_name","name":"Renamed"}]',
        args_json=json.dumps({
            "node_id": "draft",
            "unknown_param": "ignored",
        }),
        force=True,
    ))

    assert result["status"] == "ok"
    assert seen == {
        "action": "patch_branch",
        "branch_def_id": "Climate Claim Checker",
        "changes_json": '[{"op":"set_name","name":"Renamed"}]',
        "node_id": "draft",
        "limit": 50,
        "force": True,
    }


def test_control_station_names_extension_call_fallback() -> None:
    assert "No approval received" in _CONTROL_STATION_PROMPT
    assert "`extension_call`" in _CONTROL_STATION_PROMPT
    assert "compact compatibility route" in _CONTROL_STATION_PROMPT
