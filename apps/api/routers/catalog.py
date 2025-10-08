"""Catalog search endpoints using the in-memory demo dataset.

These handlers are intentionally lightweight: they simulate the scoring pipeline
with deterministic heuristics so the skeleton API is runnable without external
services. The functions are structured so that they can be swapped out for real
vector search implementations later.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..core.dataset import filter_products, load_catalog
from ..schemas import ImageSearchRequest, ProductCard, SearchRequest, SearchResponse

router = APIRouter()


def _basic_match_score(query: str, *, haystack: str) -> float:
    query_terms = [term.lower() for term in query.split() if term]
    haystack_lower = haystack.lower()
    score = 0.0
    for term in query_terms:
        if term in haystack_lower:
            score += 1.0
    return score / max(len(query_terms), 1)


def _product_to_card(product) -> ProductCard:
    return ProductCard(
        id=product.id,
        title=product.title,
        image=product.image_urls[0] if product.image_urls else None,
        price_cents=product.price_cents,
        currency=product.currency,
        badges=[product.brand] if product.brand else [],
        rationale=product.description,
    )


@router.post("/search", response_model=SearchResponse)
def search_catalog(request: SearchRequest) -> SearchResponse:
    products = load_catalog()
    filtered = filter_products(
        products,
        filters=request.filters.dict(exclude_none=True) if request.filters else None,
    )

    scored = []
    for product in filtered:
        haystack = " ".join(
            filter(
                None,
                [
                    product.title,
                    product.brand,
                    product.category,
                    " ".join(product.tags),
                    product.description or "",
                ],
            )
        )
        score = _basic_match_score(request.query, haystack=haystack)
        scored.append((score, product))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_products = [product for _, product in scored[: request.limit]]
    cards = [_product_to_card(product) for product in top_products]
    return SearchResponse(results=cards, debug={"matched": len(cards)})


@router.post("/image-search", response_model=SearchResponse)
def image_search(request: ImageSearchRequest) -> SearchResponse:
    filters = request.filters.dict(exclude_none=True) if request.filters else None
    products = filter_products(load_catalog(), filters=filters)

    if request.query:
        scored = [
            (
                _basic_match_score(
                    request.query,
                    haystack=" ".join([
                        product.title,
                        product.brand or "",
                        product.category or "",
                        " ".join(product.tags),
                        product.description or "",
                    ]),
                ),
                product,
            )
            for product in products
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        products = [product for _, product in scored]

    cards = [_product_to_card(product) for product in products[: request.limit]]
    return SearchResponse(results=cards, debug={"matched": len(cards)})