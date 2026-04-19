"""Shared pytest fixtures — fresh DB state per test.

Assumes:
    docker compose up -d
    psql ... -f migrations/001_core_tables.sql
    psql ... -f migrations/002_rls.sql
    psql ... -f migrations/003_discover_nodes.sql

Each test gets a clean slate via TRUNCATE in a transaction.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from pgvector.psycopg import register_vector

DSN = os.environ.get(
    "WORKFLOW_V0_DSN",
    "postgresql://workflow:workflow_v0_dev@localhost:5433/workflow_v0",
)


@pytest.fixture
def db():
    """Open a connection, truncate to clean state, register pgvector."""
    conn = psycopg.connect(DSN)
    register_vector(conn)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE public.artifact_field_visibility, public.nodes, public.users CASCADE"
        )
        conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def alice_id(db) -> str:
    uid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (user_id, display_name, github_handle, account_age_days) "
            "VALUES (%s, 'Alice', 'alice-gh', 30)",
            (uid,),
        )
        db.commit()
    return uid


@pytest.fixture
def bob_id(db) -> str:
    uid = str(uuid.uuid4())
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO public.users (user_id, display_name, github_handle, account_age_days) "
            "VALUES (%s, 'Bob', 'bob-gh', 30)",
            (uid,),
        )
        db.commit()
    return uid


def as_user(conn, user_id: str):
    """Set session-level user id via the GUC that auth.uid() reads."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.current_user_id', %s, false)",
            (user_id,),
        )


def stub_embedding(seed: int, dim: int = 16) -> list[float]:
    """Deterministic pseudo-embedding; close vectors for close seeds."""
    return [((seed + i) % 7) / 7.0 for i in range(dim)]
