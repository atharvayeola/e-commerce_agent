"""Recommendation endpoint with deterministic heuristics.

This module sketches the scoring recipe described in the roadmap using the
in-memory catalog so developers can focus on wiring before integrating real
retrieval infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from fastapi import APIRouter

from ..core.dataset import Product, filter_products, load_catalog
from ..core.retriever import retrieve_candidates, cross_encoder_rerank, get_last_rag_result
from ..schemas import ProductCard, RecommendRequest, SearchResponse

router = APIRouter()


@dataclass
class ScoredProduct:
    product: Product
    score: float
    rationale: str
    baseline: float


def _attribute_match_score(product: Product, constraints: Dict) -> float:
    if not constraints:
        return 0.0
    matches = 0
    total = 0
    if color := constraints.get("color"):
        total += 1
        if set(map(str.lower, color)) & set(map(str.lower, product.colors)):
            matches += 1
    if size := constraints.get("size"):
        total += 1
        if set(size) & set(product.sizes):
            matches += 1
    if brand := constraints.get("brand"):
        total += 1
        if product.brand and product.brand.lower() == brand.lower():
            matches += 1
    if constraints.get("price_max"):
        total += 1
        if product.price_cents <= constraints["price_max"]:
            matches += 1
    if constraints.get("price_min"):
        total += 1
        if product.price_cents >= constraints["price_min"]:
            matches += 1
    return matches / total if total else 0.0


def _popularity_score(product: Product) -> float:
    if product.rating is None or product.num_reviews is None:
        return 0.0
    return float(product.rating) * (1 + (product.num_reviews or 0) ** 0.5 / 10)


def _baseline_score(product: Product, goal: str) -> float:
    haystack = " ".join(
        filter(
            None,
            [
                product.title,
                product.brand,
                product.category,
                " ".join(product.tags),
                product.description,
            ],
        )
    )
    goal_terms = [term.lower() for term in goal.split() if term]
    haystack_lower = haystack.lower()
    matches = sum(1 for term in goal_terms if term in haystack_lower)
    return matches / max(len(goal_terms), 1)


def _score_products(products: Iterable[Product], goal: str, constraints: Dict) -> List[ScoredProduct]:
    scored: List[ScoredProduct] = []
    for product in products:
        baseline = _baseline_score(product, goal)
        attribute_score = _attribute_match_score(product, constraints)
        popularity = _popularity_score(product)
        stock_boost = 0.05 if product.in_stock else -0.1

        score = (
            0.55 * baseline
            + 0.20 * baseline  # placeholder for rerank similarity
            + 0.10 * attribute_score
            + 0.10 * (popularity / 10)
            + stock_boost
        )
        rationale_parts = []
        if constraints.get("price_max") and product.price_cents <= constraints["price_max"]:
            rationale_parts.append(f"under ${constraints['price_max'] / 100:.0f}")
        if constraints.get("color"):
            matched = set(map(str.lower, constraints["color"])) & set(map(str.lower, product.colors))
            if matched:
                rationale_parts.append(f"available in {', '.join(sorted(matched))}")
        if constraints.get("size"):
            matched_sizes = set(constraints["size"]) & set(product.sizes)
            if matched_sizes:
                rationale_parts.append(f"sizes {', '.join(sorted(matched_sizes))}")
        if product.tags:
            rationale_parts.append(product.tags[0])
        rationale = ", ".join(rationale_parts) or product.description or "Popular pick"

        scored.append(
            ScoredProduct(
                product=product,
                score=score,
                rationale=rationale,
                baseline=baseline,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored


def _diversify(scored: List[ScoredProduct], limit: int) -> List[ScoredProduct]:
    seen_brands = set()
    diversified: List[ScoredProduct] = []
    for item in scored:
        brand = item.product.brand or ""
        if brand in seen_brands and len(diversified) + 1 < limit:
            continue
        diversified.append(item)
        seen_brands.add(brand)
        if len(diversified) == limit:
            break
    return diversified or scored[:limit]


@router.post("/recommend", response_model=SearchResponse)
def recommend_products(request: RecommendRequest) -> SearchResponse:
    constraints = request.constraints.dict(exclude_none=True) if request.constraints else {}

    # Retrieve candidates using the retriever adapter (lexical or vector-backed)
    candidates = retrieve_candidates(request.goal, limit=200)

    # Apply local filtering constraints first to narrow the candidate set
    filtered_candidates = filter_products(candidates, filters=constraints)

    # If a semantic cross-encoder is available, rerank the filtered candidates
    reranked = cross_encoder_rerank(request.goal, filtered_candidates)

    # Score the (reranked) candidate list with our heuristic scorer
    scored = _score_products(reranked, request.goal, constraints)
    
    max_baseline = max((item.baseline for item in scored), default=0.0)
    diversified: List[ScoredProduct] = []
    if scored:
        diversified = _diversify(scored, request.limit)
    if not diversified and scored:
        diversified = scored[: request.limit]

    cards = [
        ProductCard(
            id=item.product.id,
            title=item.product.title,
            image=item.product.image_urls[0] if item.product.image_urls else None,
            price_cents=item.product.price_cents,
            currency=item.product.currency,
            category=item.product.category,
            description=item.product.description,
            badges=[item.product.brand] if item.product.brand else [],
            rationale=item.rationale,
            source="catalog",
        )
        for item in diversified
    ]

    debug = {
        "scored": len(scored),
        "after_diversity": len(diversified),
        "max_baseline": max_baseline,
        "fallback_used": bool(scored and not max_baseline),
    }

    rag_result = get_last_rag_result()
    external_cards: List[ProductCard] = []
    if rag_result:
        debug["rag"] = {
            "enabled": True,
            "summary": rag_result.answer,
            "references": rag_result.references[:5],
        }
        if rag_result.web_cards:
            external_cards = rag_result.web_cards[: request.limit]
    else:
        debug["rag"] = {"enabled": False}
    return SearchResponse(results=cards, external_results=external_cards, debug=debug)