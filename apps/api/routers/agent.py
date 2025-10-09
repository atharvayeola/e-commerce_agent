"""Agent endpoint that routes between smalltalk, text recommendations, and image search.

The real implementation would leverage function calling with an external LLM.
Here we mimic the decision logic with simple keyword checks so the API remains
self-contained while exposing the same contract.
"""

from __future__ import annotations
import re
from typing import List, Optional, Set
from fastapi import APIRouter
from pydantic import ValidationError

from ..core.dataset import load_catalog
from ..core.llm_adapter import summarize_text
from ..core.web_fetch import fetch_and_extract, to_product_card
from ..core.web_search import search as web_search
from ..core.browseai_adapter import fetch_from_browseai
from ..core.image_analysis import analyze_image

from ..schemas import AgentChatRequest, AgentChatResponse, ProductCard, RecommendRequest
from .recommend import recommend_products


router = APIRouter()


IMAGE_KEYWORDS = {"image", "photo", "picture", "upload"}
_WEB_SEARCH_LIMIT = 6

_GREETING_PATTERN = re.compile(r"^(hi|hello|hey|good (morning|evening|afternoon))( there)?[!. ]*$")
_PRODUCT_KEYWORDS = {
    "recommend",
    "find",
    "need",
    "looking",
    "buy",
    "shop",
    "shoe",
    "sneaker",
    "shirt",
    "tee",
    "t-shirt",
    "jacket",
    "dress",
    "pant",
    "jean",
    "blender",
    "product",
    "size",
    "color",
}

_CATALOG_STOPWORDS = {
    "find",
    "show",
    "me",
    "for",
    "a",
    "an",
    "the",
    "please",
    "need",
    "looking",
    "search",
    "recommend",
    "recommendation",
    "want",
    "would",
    "like",
    "buy",
    "i",
    "am",
    "to",
    "on",
    "with",
    "of",
    "any",
    "some",
    "something",
    "help",
    "and",
    "or",
    "but",
    "so",
    "if",
    "then",
    "than",
    "not",
    "is",
    "are",
    "be",
    "being",
    "was",
    "were",
    "have",
    "has",
    "had",
    "my",
    "your",
    "their",
    "our",
    "this",
    "that",
    "these",
    "those",
    "here",
    "there",
    "under",
    "over",
    "between",
    "around",
    "more",
    "less",
    "budget",
}



def _catalog_query_terms(message: str) -> List[str]:
    tokens = [term for term in re.split(r"[^a-z0-9]+", message.lower()) if term]
    return [
        term
        for term in tokens
        if term not in _CATALOG_STOPWORDS
        and not term.isdigit()
        and len(term) > 1
    ]


def _catalog_product_cards(message: str, limit: int) -> List[ProductCard]:
    terms = _catalog_query_terms(message)
    if not terms:
        return []

    scored = []
    lowered_message = message.strip().lower()
    for product in load_catalog():
        haystack_parts = filter(
            None,
            [
                product.title,
                product.brand,
                product.category,
                " ".join(product.tags),
                product.description,
            ],
        )
        haystack = " ".join(haystack_parts).lower()
        if not haystack:
            continue
        haystack_tokens: Set[str] = {
            token
            for token in re.split(r"[^a-z0-9]+", haystack)
            if token
        }
        matches = sum(1 for term in terms if term in haystack_tokens)
        if matches == 0:
            continue
        score = matches / len(terms)
        if lowered_message and lowered_message in product.title.lower():
            score += 0.75
        scored.append((score, product))

    scored.sort(key=lambda item: item[0], reverse=True)
    cards: List[ProductCard] = []
    for _, product in scored[:limit]:
        badges: List[str] = []
        if product.brand:
            badges.append(product.brand)
        rationale = product.tags[0] if product.tags else product.description
        cards.append(
            ProductCard(
                id=product.id,
                title=product.title,
                image=product.image_urls[0] if product.image_urls else None,
                price_cents=product.price_cents,
                currency=product.currency,
                category=product.category,
                description=product.description,
                badges=badges,
                rationale=rationale,
                source="catalog",
            )
        )
    return cards


def _classify_smalltalk(message: str) -> Optional[str]:
    lowered = message.lower().strip()
    if not lowered:
        return None
    if any(keyword in lowered for keyword in _PRODUCT_KEYWORDS):
        return None

    if any(phrase in lowered for phrase in ["your name", "who are you", "what are you", "introduce yourself"]):
        return "identity"
    if any(phrase in lowered for phrase in ["what can you do", "capabilities", "how can you help", "what do you do"]):
        return "capabilities"
    if any(phrase in lowered for phrase in ["how are you", "how's it going", "how are things"]):
        return "wellbeing"
    if "thank" in lowered:
        return "gratitude"
    if any(phrase in lowered for phrase in ["who built", "who made you", "where do you come from"]):
        return "origin"
    if _GREETING_PATTERN.match(lowered):
        return "greeting"
    return None


def _detect_intent(message: str, has_image: bool) -> tuple[str, Optional[str]]:
    topic = _classify_smalltalk(message)
    if topic:
        return "smalltalk", topic
    lowered = message.lower()
    if has_image or any(keyword in lowered for keyword in IMAGE_KEYWORDS):
        return "image_search", None
    return "text_recommendation", None

def _smalltalk_response(message: str, topic: Optional[str]) -> str:
    lowered = message.lower()
    if topic == "identity" or "your name" in lowered:
        return "I'm CommerceAgent, your shopping sidekick for our curated catalog."
    if topic == "capabilities":
        return (
            "I can chat about what you need, recommend products from our catalog, "
            "and even use images you upload to spot items with similar colors or styles."
        )
    if topic == "wellbeing":
        return "I'm all code, but I'm running smoothly! How can I help with your shopping goals?"
    if topic == "gratitude":
        return "Happy to help! Let me know if you'd like to explore more options."
    if topic == "origin":
        return "I was trained by the CommerceAgent team to understand our product catalog and assist with discovery."
    # default to a friendly greeting
    return "Hi! I'm CommerceAgent—ask me for product recommendations or try our image-based search."


def _summarize_web(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        fetched = fetch_and_extract(str(url))
        if fetched and fetched.get("text"):
            return summarize_text(fetched.get("text"), max_length=500)
    except Exception:
        return ""
    return ""


_APPAREL_KEYWORDS = {
    "shirt",
    "tee",
    "t-shirt",
    "jacket",
    "hoodie",
    "dress",
    "sweater",
    "pant",
    "pants",
    "jean",
    "short",
    "skirt",
    "legging",
    "athletic",
    "top",
}


def _follow_up_question(message: str, product_count: int) -> Optional[str]:
    if product_count == 0:
        return None
    lowered = message.lower()
    # Keep follow-ups generic: ask about budget if not provided. Avoid per-product
    # follow-ups like size questions which don't make sense when returning many results.
    if all(keyword not in lowered for keyword in ["budget", "price", "$"]):
        return "What budget should I keep in mind?"
    return None


@router.post("/chat", response_model=AgentChatResponse)
def chat(request: AgentChatRequest) -> AgentChatResponse:
    web_text = ""
    if getattr(request, "allow_web", False) and getattr(request, "web_url", None):
        web_text = _summarize_web(str(request.web_url))

    combined_message = request.message + ("\n" + web_text if web_text else "")
    intent, topic = _detect_intent(request.message, bool(request.image_b64))

    if intent == "smalltalk":
        return AgentChatResponse(
            intent=intent,
            text=_smalltalk_response(request.message, topic),
            products=[],
        )

    if intent == "image_search":
        analysis = analyze_image(request.image_b64 or "") if request.image_b64 else None
        color_terms = [c for c in (analysis.dominant_colors if analysis else []) if c]
        object_terms = [o for o in (analysis.detected_objects if analysis else []) if o]

        query_parts: List[str] = []
        if request.message and request.message.strip():
            query_parts.append(request.message.strip())
        if object_terms:
            natural = [term.replace("_", " ") for term in object_terms[:2]]
            query_parts.append(" ".join(natural))
        if color_terms:
            query_parts.append(" ".join(color_terms[:3]) + " product")
        if not query_parts:
            query_parts.append("shopping inspiration")

        web_cards = _web_product_cards(" ".join(query_parts), limit=_WEB_SEARCH_LIMIT)

        descriptors: List[str] = []
        if color_terms:
            descriptors.append(f"the {', '.join(color_terms[:2])} palette")
        if object_terms:
            descriptors.append(f"what looks like {object_terms[0].replace('_', ' ')}")
        if analysis and "mostly_dark" in analysis.notes:
            descriptors.append("the darker lighting in your photo")
        elif analysis and "mostly_light" in analysis.notes:
            descriptors.append("the lighter tones in your photo")
        if not descriptors:
            descriptors.append("the overall look of your image")

        if web_cards:
            text = (
                "I searched the web for products that match "
                + (" and ".join(descriptors) if len(descriptors) > 1 else descriptors[0])
                + "."
            )
        else:
            text = "I couldn't find clear web matches for that image. Try adding a short description?"

        return AgentChatResponse(intent=intent, text=text, products=web_cards)

    limit = _WEB_SEARCH_LIMIT

    if intent == "text_recommendation":
        catalog_cards = _catalog_product_cards(request.message, limit)
        if catalog_cards:
            explanation = f"I found {len(catalog_cards)} item(s) in our catalog that match your request."
            follow_up = _follow_up_question(request.message, len(catalog_cards))
            return AgentChatResponse(
                intent=intent,
                text=explanation,
                products=catalog_cards,
                follow_up_question=follow_up,
            )
        
    web_cards: List[ProductCard] = []
    if getattr(request, "allow_web", False):
        web_cards = _web_product_cards(request.message, limit=limit)

    # Optional: if the client supplied a Browse.ai extractor id, call it and
    # convert results into ProductCard objects. The request may carry a
    # `browse_api_key`; otherwise the server can use an env var override.
    browse_cards: List[ProductCard] = []
    if getattr(request, "browse_extractor", None):
        api_key = getattr(request, "browse_api_key", None) or None
        # allow using BROWSEAI_API_KEY env var as fallback
        if not api_key:
            import os

            api_key = os.environ.get("BROWSEAI_API_KEY")
        force_browse = bool(getattr(request, "browse_force", False))
        items = fetch_from_browseai(str(request.browse_extractor), api_key, force=force_browse) if api_key else None
        if items:
            from pydantic import ValidationError

            for it in items[:limit]:
                try:
                    card = ProductCard(
                        id=it.get("id") or "",
                        title=it.get("title") or "Product",
                        image=(it.get("image_urls") or [None])[0],
                        price_cents=it.get("price_cents") or 0,
                        currency=it.get("currency") or "USD",
                        category=it.get("category"),
                        description=it.get("description"),
                        badges=it.get("tags") or [],
                        rationale=it.get("description"),
                        source="browseai",
                        url=it.get("url"),
                    )
                except (ValidationError, KeyError):
                    continue
                browse_cards.append(card)
            # treat browse results as web cards for merging behavior below
            if browse_cards:
                web_cards = browse_cards + web_cards

    # Prefer browse.ai results when available; otherwise use web search results.
    products: List[ProductCard] = []
    explanation = ""
    if browse_cards:
        products = browse_cards[:limit]
        explanation = f"I found {len(products)} product(s) from the specified extractor."
    elif web_cards:
        products = web_cards[:limit]
        explanation = f"I searched the web and found {len(products)} result(s) matching your request."
    else:
        # No web results — fall back to catalog recommendations
        recommend_payload = RecommendRequest(goal=combined_message, constraints=None, limit=limit)
        response = recommend_products(recommend_payload)
        products = list(response.results)
        count = len(products)
        if count:
            explanation = f"Here are {count} option(s) from our catalog that may fit your request."
        else:
            explanation = "I couldn't find relevant web results or catalog matches for that request."

    follow_up = _follow_up_question(request.message, len(products))
    return AgentChatResponse(intent=intent, text=explanation, products=products, follow_up_question=follow_up)


def _web_product_cards(message: str, limit: int = _WEB_SEARCH_LIMIT) -> List[ProductCard]:
    """Fetch web search results and convert them into product cards."""

    urls = web_search(message, limit=limit)
    cards: List[ProductCard] = []
    seen_ids: Set[str] = set()
    for url in urls:
        if not url:
            continue
        fetched = fetch_and_extract(url)
        if not fetched:
            continue
        product = to_product_card(fetched)
        if not product:
            continue

        image_urls = product.get("image_urls") or []
        image = next((img for img in image_urls if img), None)

        badges: List[str] = []
        brand = product.get("brand")
        if brand:
            badges.append(str(brand))
        for tag in product.get("tags", []):
            if tag and tag not in badges:
                badges.append(str(tag))

        description = product.get("description") or fetched.get("excerpt") or ""

        short_description = description[:280].strip() if description else None
        try:
            card = ProductCard(
                id=product["id"],
                title=product.get("title") or "Product",
                image=image,
                price_cents=product.get("price_cents") or 0,
                currency=product.get("currency") or "USD",
                category=product.get("category"),
                description=short_description,
                badges=badges[:3],
                rationale=short_description,
                source="web",
                url=fetched.get("url"),
            )
        except (ValidationError, KeyError):
            continue

        if card.id in seen_ids:
            continue
        seen_ids.add(card.id)
        cards.append(card)

        if len(cards) >= limit:
            break

    return cards