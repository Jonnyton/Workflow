"""T5 — FastMCP gateway tool call round-trips through RPC.

Invokes gateway.discover_nodes and gateway.update_node as regular
Python functions (skipping the MCP transport layer for v0; real build
uses FastMCP streamable-http).
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

# Ensure prototype root on path for 'gateway' import
sys.path.insert(0, str(Path(__file__).parent.parent))

import gateway  # noqa: E402
from conftest import stub_embedding  # noqa: E402


def test_discover_nodes_returns_shape(db, alice_id):
    # Seed a node owned by Alice
    nid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_user_id', %s, false)", (alice_id,),
        )
        cur.execute(
            "INSERT INTO public.nodes (node_id, slug, name, domain, owner_user_id, "
            "concept, structural_hash, embedding) VALUES "
            "(%s, 'gateway-test', 'GatewayTest', 'proto', %s, %s::jsonb, 'h', %s)",
            (nid, alice_id, json.dumps({"p": "gateway"}), stub_embedding(3)),
        )
        db.commit()

    # Call through gateway (it opens its own conn; passes bearer_token as user_id)
    result = gateway.discover_nodes(
        intent="gateway",
        intent_embedding=stub_embedding(3),
        bearer_token=alice_id,
    )
    assert "candidates" in result
    assert any(c["name"] == "GatewayTest" for c in result["candidates"])


def test_update_node_cas_conflict_returns_envelope(db, alice_id):
    # Seed a node with version=3
    nid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_user_id', %s, false)", (alice_id,),
        )
        cur.execute(
            "INSERT INTO public.nodes (node_id, slug, name, domain, owner_user_id, "
            "concept, version, structural_hash, embedding) VALUES "
            "(%s, 'cas-test', 'CasTest', 'proto', %s, '{}'::jsonb, 3, 'h', "
            "'[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]'::vector(16))",
            (nid, alice_id),
        )
        db.commit()

    # Attempt stale write with version=1
    result = gateway.update_node(
        node_id=nid,
        concept={"bad": "write"},
        version=1,
        bearer_token=alice_id,
    )
    assert "error" in result
    assert result["error"]["data"]["kind"] == "cas_conflict"
    assert result["error"]["data"]["current_version"] == 3
