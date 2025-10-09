"""Compute embeddings for sample products and upsert into Postgres (pgvector).

Usage:
  export PGVECTOR_DSN='postgresql://user:pass@host:5432/dbname'
  python scripts/compute_embeddings.py

This script is intentionally optional and will print helpful errors if the
environment isn't set up (missing DSN, missing sentence-transformers, etc.).
"""
import os
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_products.json"


def main():
    dsn = os.environ.get("PGVECTOR_DSN")
    if not dsn:
        print("PGVECTOR_DSN not set. Export your Postgres DSN and try again.")
        sys.exit(1)

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        print("sentence-transformers is required. Install with: pip install sentence-transformers")
        raise

    try:
        from apps.api.core.pgvector_adapter import ensure_table, upsert_embeddings
    except Exception as exc:
        print("pgvector adapter requires psycopg2 and PGVector-enabled Postgres.")
        raise

    data = json.loads(SAMPLE.read_text())
    model = SentenceTransformer("all-MiniLM-L6-v2")

    rows = []
    for item in data:
        pid = item["id"]
        text = " ".join(filter(None, [item.get("title"), item.get("description") or ""]))
        emb = model.encode(text).tolist()
        meta = {"title": item.get("title"), "brand": item.get("brand")}
        rows.append((pid, emb, meta))

    print("Ensuring table exists...")
    ensure_table()
    print(f"Upserting {len(rows)} embeddings...")
    upsert_embeddings(rows)
    print("Done.")


if __name__ == "__main__":
    main()
