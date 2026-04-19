"""T3 — discover_nodes returns ranked candidates with correct signal block."""

from __future__ import annotations

import json
import uuid

from conftest import as_user, stub_embedding


def test_ranks_by_composite_score(db, alice_id):
    as_user(db, alice_id)
    # Create 3 nodes with varying quality signals
    with db.cursor() as cur:
        for i, (name, upvotes, success) in enumerate([
            ("top", 100, 50),
            ("mid", 30, 20),
            ("low", 5, 5),
        ]):
            nid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.nodes "
                "(node_id, slug, name, domain, owner_user_id, concept, structural_hash, "
                " embedding, upvote_count, success_count, fail_count) "
                "VALUES (%s, %s, %s, 'test', %s, %s::jsonb, 'h', %s, %s, %s, 0)",
                (nid, f"n-{i}", name, alice_id, json.dumps({"purpose": name}),
                 stub_embedding(1), upvotes, success),
            )
        db.commit()

    with db.cursor() as cur:
        cur.execute(
            "SELECT public.discover_nodes(%s, %s::vector(16), NULL, NULL, NULL, 10, true)",
            ("test intent", stub_embedding(1)),
        )
        result = cur.fetchone()[0]

    names = [c["name"] for c in result["candidates"]]
    assert names == ["top", "mid", "low"], f"ranking order wrong: {names}"

    top = result["candidates"][0]
    assert "quality" in top
    assert top["quality"]["upvote_count"] == 100
    assert top["quality"]["success_rate"] == 1.0  # 50/50
    assert "semantic_match_score" in top
    assert "provenance" in top


def test_is_owner_flag_correct(db, alice_id, bob_id):
    as_user(db, alice_id)
    nid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO public.nodes (node_id, slug, name, domain, owner_user_id, "
            "concept, structural_hash, embedding) VALUES "
            "(%s, 'x', 'X', 'd', %s, %s::jsonb, 'h', %s)",
            (nid, alice_id, json.dumps({"p": "x"}), stub_embedding(2)),
        )
        db.commit()

    # Alice: is_owner=true
    as_user(db, alice_id)
    with db.cursor() as cur:
        cur.execute(
            "SELECT public.discover_nodes(%s, %s::vector(16), NULL, NULL, NULL, 10, true)",
            ("x", stub_embedding(2)),
        )
        r = cur.fetchone()[0]
    assert r["candidates"][0]["is_owner"] is True

    # Bob: is_owner=false
    as_user(db, bob_id)
    with db.cursor() as cur:
        cur.execute(
            "SELECT public.discover_nodes(%s, %s::vector(16), NULL, NULL, NULL, 10, true)",
            ("x", stub_embedding(2)),
        )
        r = cur.fetchone()[0]
    assert r["candidates"][0]["is_owner"] is False
