"""Catalog search endpoints using the in-memory demo dataset.

These handlers are intentionally lightweight: they simulate the scoring pipeline
with deterministic heuristics so the skeleton API is runnable without external
services. The functions are structured so that they can be swapped out for real
vector search implementations later.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..core.dataset import filter_products, load_catalog
from ..core.image_analysis import analyze_image, colors_to_filters, labels_to_hints
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
        category=product.category,
        description=product.description,
        badges=[product.brand] if product.brand else [],
        rationale=(product.tags[0] if product.tags else product.description),
        source="catalog",
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
    if not products:
        products = load_catalog()

    analysis = analyze_image(request.image_b64) if request.image_b64 else None
    color_hints = colors_to_filters(analysis)
    label_hints = labels_to_hints(analysis)
    label_keywords = label_hints.keywords
    label_categories = label_hints.categories
    query_text = request.query or ""
    if analysis and analysis.caption:
        query_text = (query_text + " " + analysis.caption).strip()

    scored = []
    for product in products:
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
        haystack_lower = haystack.lower()
        text_score = _basic_match_score(query_text, haystack=haystack) if query_text else 0.0

        product_colors = set(map(str.lower, product.colors))
        overlap = [color for color in color_hints if color in product_colors or (
            color == "navy" and "blue" in product_colors
        )]
        color_score = 0.0
        if color_hints:
            color_score = 0.6 * (len(overlap) / len(color_hints))

        brightness_score = 0.0
        if analysis:
            if "mostly_dark" in analysis.notes and ("black" in product_colors or "navy" in product_colors):
                brightness_score = 0.15
            elif "mostly_light" in analysis.notes and ("white" in product_colors or "gray" in product_colors):
                brightness_score = 0.1
        keyword_matches = [kw for kw in label_keywords if kw in haystack_lower]
        keyword_score = 0.0
        if label_keywords:
            keyword_score = 0.7 * (len(keyword_matches) / len(label_keywords))

        category_score = 0.0
        if label_categories and product.category and product.category in label_categories:
            category_score = 0.25

        stock_bonus = 0.05 if product.in_stock else -0.05

        score = (
            text_score
            + color_score
            + brightness_score
            + keyword_score
            + category_score
            + stock_bonus
        )

        rationale_parts = []
        if overlap:
            rationale_parts.append(f"color match: {', '.join(overlap)}")
        elif color_hints:
            rationale_parts.append(f"complements the {color_hints[0]} tones in your image")
        if text_score >= 0.4:
            rationale_parts.append("aligns with your description")
        if keyword_matches:
            rationale_parts.append(f"looks like {keyword_matches[0]}")
        elif category_score > 0 and label_categories:
            rationale_parts.append(f"similar {label_categories[0]} item")
        if analysis and analysis.caption and analysis.caption.lower() in haystack_lower:
            rationale_parts.append("matches the scene described in your image")
        if not rationale_parts and product.tags:
            rationale_parts.append(product.tags[0])

        scored.append((score, product, ", ".join(rationale_parts)))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = scored[: request.limit]
    cards = []
    for _, product, rationale in selected:
        card = _product_to_card(product)
        if rationale:
            card.rationale = rationale
        cards.append(card)

    debug = {"matched": len(cards)}
    if analysis:
        debug["image_analysis"] = analysis.to_dict()
    if color_hints:
        debug["color_hints"] = color_hints
    if label_keywords or label_categories:
        debug["label_hints"] = label_hints.to_dict()
    return SearchResponse(results=cards, debug=debug)