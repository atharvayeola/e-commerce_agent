"""Retrieval helpers: optional pgvector/semantic retrieval with safe fallbacks.

This module provides a small adapter so the recommendation route can prefer
vector/semantic retrieval when available, and fall back to a lightweight
lexical retriever otherwise. It intentionally avoids hard runtime dependencies
and will degrade gracefully if optional packages or external services are
missing.
"""
from __future__ import annotations

from typing import List
import os
import logging

from ..core.dataset import load_catalog, Product


def _lexical_retrieve(goal: str, limit: int = 50) -> List[Product]:
    """Simple lexical retrieval that ranks by term overlap (fast, no deps)."""
    terms = [t.lower() for t in goal.split() if t]
    catalog = load_catalog()

    def score(p: Product) -> int:
        hay = " ".join(filter(None, [p.title, p.brand, p.category, " ".join(p.tags), p.description or ""]))
        hay_lower = hay.lower()
        return sum(1 for t in terms if t in hay_lower)

    scored = sorted(catalog, key=score, reverse=True)
    return scored[:limit]


def _semantic_rerank_available() -> bool:
    try:
        import sentence_transformers  # type: ignore

        return True
    except Exception:
        return False


def retrieve_candidates(goal: str, limit: int = 50) -> List[Product]:
    """Retrieve candidate products for a goal.

    Priority:
    - If PGVECTOR_DSN is set and a proper pgvector backend is available, this
      function could be adapted to query that DB. That requires embeddings to
      be stored in the DB and a query embedding computed. (Not implemented
      here to keep this repo dependency-free.)
    - If sentence-transformers is installed, we still use a lexical pass to
      limit candidates and let the reranker optionally refine ordering.
    - Otherwise fall back to simple lexical retrieval.
    """
    # If a Postgres pgvector DSN is provided, try to query nearest neighbors.
    if os.environ.get("PGVECTOR_DSN"):
        try:
            from .pgvector_adapter import query_by_embedding
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")
            query_emb = model.encode(goal).tolist()
            rows = query_by_embedding(query_emb, limit=limit)
            # Map returned IDs to Product objects in the local catalog
            id_to_product = {p.id: p for p in load_catalog()}
            results = []
            for r in rows:
                pid = r.get("id")
                if pid and pid in id_to_product:
                    results.append(id_to_product[pid])
            if results:
                return results
            # if no matches found, fall back to lexical
        except Exception as exc:
            logging.exception("pgvector query failed or not configured properly: %s", exc)

    # Fallback lexical retrieval
    return _lexical_retrieve(goal, limit=limit)


def cross_encoder_rerank(goal: str, candidates: List[Product]) -> List[Product]:
    """Try to rerank with a lightweight semantic model if available.

    Falls back to the lexical ordering if sentence-transformers isn't installed.
    """
    if not candidates:
        return candidates

    try:
        # Attempt to use sentence-transformers for semantic scoring
        from sentence_transformers import SentenceTransformer, util  # type: ignore

        model = SentenceTransformer("all-MiniLM-L6-v2")
        corpus = [" ".join(filter(None, [p.title, p.description or ""])) for p in candidates]
        corpus_emb = model.encode(corpus, convert_to_tensor=True)
        query_emb = model.encode(goal, convert_to_tensor=True)
        scores = util.cos_sim(query_emb, corpus_emb)[0].tolist()
        paired = list(zip(candidates, scores))
        paired.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in paired]
    except Exception:
        # semantic reranker not available; return original order
        return candidates
