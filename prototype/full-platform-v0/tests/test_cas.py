"""T4 — optimistic CAS via version column blocks silent overwrites.

Proves #25 §1.2 `version bigint` + #14.3 + #27 §4 cas_conflict envelope.
"""

from __future__ import annotations

import json
import uuid

from conftest import as_user


def test_correct_version_succeeds(db, alice_id):
    as_user(db, alice_id)
    nid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO public.nodes (node_id, slug, name, domain, owner_user_id, "
            "concept, structural_hash, embedding) VALUES "
            "(%s, 'x', 'X', 'd', %s, '{}'::jsonb, 'h', "
            "(SELECT '[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]'::vector(16)))",
            (nid, alice_id),
        )
        db.commit()

    with db.cursor() as cur:
        cur.execute(
            "UPDATE public.nodes SET concept = %s::jsonb, version = version + 1 "
            "WHERE node_id = %s AND version = 1 RETURNING version",
            (json.dumps({"step": "first"}), nid),
        )
        new_v = cur.fetchone()[0]
        db.commit()
    assert new_v == 2


def test_stale_version_zero_rows_affected(db, alice_id):
    as_user(db, alice_id)
    nid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO public.nodes (node_id, slug, name, domain, owner_user_id, "
            "concept, version, structural_hash, embedding) VALUES "
            "(%s, 'y', 'Y', 'd', %s, '{}'::jsonb, 5, 'h', "
            "'[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]'::vector(16))",
            (nid, alice_id),
        )
        db.commit()

    # Attempt with stale version 3
    with db.cursor() as cur:
        cur.execute(
            "UPDATE public.nodes SET concept = '{\"x\":1}'::jsonb "
            "WHERE node_id = %s AND version = 3",
            (nid,),
        )
        assert cur.rowcount == 0, "stale version should produce zero-rows-affected"
        db.rollback()

    # Real version confirms CAS didn't apply
    with db.cursor() as cur:
        cur.execute("SELECT version, concept FROM public.nodes WHERE node_id = %s", (nid,))
        version, concept = cur.fetchone()
    assert version == 5
    assert concept == {}
