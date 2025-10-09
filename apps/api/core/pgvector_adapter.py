"""PGVector adapter helpers (optional).

This module provides small helpers to upsert product embeddings and query the
nearest neighbors using Postgres + pgvector. It avoids hard runtime
dependencies by guarding imports and raising clear errors if the environment
isn't configured.
"""
from __future__ import annotations

from typing import List, Tuple
import os
import json
import logging


def _get_dsn() -> str:
    dsn = os.environ.get("PGVECTOR_DSN")
    if not dsn:
        raise EnvironmentError("PGVECTOR_DSN not set")
    return dsn


def _connect():
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except Exception as exc:
        raise RuntimeError("psycopg2 is required for pgvector adapter") from exc

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    return conn


def ensure_table():
    """Create a minimal table for product embeddings if it doesn't exist."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS product_embeddings (
            id TEXT PRIMARY KEY,
            embedding vector,
            metadata JSONB
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def upsert_embeddings(rows: List[Tuple[str, List[float], dict]]):
    """Upsert embeddings: rows is list of (id, vector, metadata).

    Note: requires pgvector extension and psycopg2.
    """
    conn = _connect()
    cur = conn.cursor()
    sql = "INSERT INTO product_embeddings (id, embedding, metadata) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata"
    for id_, vec, meta in rows:
        # psycopg2 will need the vector formatted as list -> pgvector handles array input
        cur.execute(sql, (id_, vec, json.dumps(meta)))
    conn.commit()
    cur.close()
    conn.close()


def query_by_embedding(query_vec: List[float], limit: int = 50) -> List[dict]:
    """Return list of rows ordered by cosine similarity (requires pgvector).

    Returns rows as dicts with keys: id, distance, metadata
    """
    conn = _connect()
    cur = conn.cursor()
    # Using <-> operator for vector distance; adjust if your pgvector version differs
    cur.execute(
        "SELECT id, 1 - (embedding <#> %s) AS score, metadata FROM product_embeddings ORDER BY embedding <#> %s LIMIT %s",
        (query_vec, query_vec, limit),
    )
    rows = cur.fetchall()
    results = []
    for id_, score, meta in rows:
        try:
            parsed = json.loads(meta) if isinstance(meta, str) else meta
        except Exception:
            parsed = meta
        results.append({"id": id_, "score": float(score), "metadata": parsed})
    cur.close()
    conn.close()
    return results
