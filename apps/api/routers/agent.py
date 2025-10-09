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

from ..core.llm_adapter import summarize_text
from ..core.web_fetch import fetch_and_extract, to_product_card
from ..core.web_search import search as web_search
from ..core.browseai_adapter import fetch_from_browseai

from ..schemas import (
    AgentChatRequest,
    AgentChatResponse,
    ImageSearchRequest,
    ProductCard,
    RecommendRequest,
)
from .catalog import image_search
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
        image_payload = ImageSearchRequest(
            image_b64=request.image_b64 or "",
            query=request.message or None,
            filters=None,
            limit=6,
        )
        response = image_search(image_payload)
        analysis = {}
        if isinstance(response.debug, dict):
            analysis = response.debug.get("image_analysis") or {}
        colors = [c for c in analysis.get("dominant_colors", []) if c]
        if colors:
            color_phrase = ", ".join(colors[:2])
            text = f"I looked for catalog items that match the {color_phrase} tones in your photo."
        else:
            text = "Here are products that visually align with your request."
        if not response.results:
            text = "I couldn't find a close visual match, so here are some popular catalog picks instead."
        return AgentChatResponse(intent=intent, text=text, products=response.results)

    limit = _WEB_SEARCH_LIMIT
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
        items = fetch_from_browseai(str(request.browse_extractor), api_key) if api_key else None
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

        try:
            card = ProductCard(
                id=product["id"],
                title=product.get("title") or "Product",
                image=image,
                price_cents=product.get("price_cents") or 0,
                currency=product.get("currency") or "USD",
                badges=badges[:3],
                rationale=description[:280] if description else None,
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