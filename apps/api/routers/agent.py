"""Agent endpoint that routes between smalltalk, text recommendations, and image search.

The real implementation would leverage function calling with an external LLM.
Here we mimic the decision logic with simple keyword checks so the API remains
self-contained while exposing the same contract.
"""

from __future__ import annotations

from fastapi import APIRouter
from ..core.web_fetch import fetch_and_extract, to_product_card
from ..core.llm_adapter import summarize_text
import requests
from bs4 import BeautifulSoup

from ..schemas import AgentChatRequest, AgentChatResponse, ImageSearchRequest, RecommendRequest
from .catalog import image_search
from .recommend import recommend_products
from ..core.web_search import search as web_search

router = APIRouter()

SMALLTALK_KEYWORDS = {"hello", "hi", "hey", "name", "capabilities"}
IMAGE_KEYWORDS = {"image", "photo", "picture"}


def _detect_intent(message: str, has_image: bool) -> str:
    lowered = message.lower()
    if any(keyword in lowered for keyword in SMALLTALK_KEYWORDS):
        return "smalltalk"
    if has_image or any(keyword in lowered for keyword in IMAGE_KEYWORDS):
        return "image_search"
    return "text_recommendation"


def _smalltalk_response(message: str) -> str:
    if "name" in message.lower():
        return "I'm CommerceAgent, here to help you discover products."
    return "Hi! I'm CommerceAgent—ask me for product recommendations or try searching by image."


@router.post("/chat", response_model=AgentChatResponse)
def chat(request: AgentChatRequest) -> AgentChatResponse:
    # If allowed, fetch web page text and append to the user message so the
    # agent can leverage web content when forming recommendations.
    web_text = ""
    # If allowed, try to fetch and extract using the cached fetcher (preferred).
    if getattr(request, "allow_web", False) and getattr(request, "web_url", None):
        try:
            fetched = fetch_and_extract(str(request.web_url))
            if fetched and fetched.get("text"):
                # Summarize fetched page text via the LLM adapter to reduce prompt size
                web_text = summarize_text(fetched.get("text"), max_length=500)
            else:
                # fallback: do a lightweight GET and grab <p> text
                resp = requests.get(str(request.web_url), timeout=3)
                if resp.ok:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    paragraphs = [p.get_text(separator=" ").strip() for p in soup.find_all("p")]
                    raw = "\n".join([p for p in paragraphs if p])
                    web_text = summarize_text(raw, max_length=500) if raw else ""
        except Exception:
            web_text = ""

    combined_message = request.message + ("\n" + web_text if web_text else "")
    intent = _detect_intent(combined_message, bool(request.image_b64))

    if intent == "smalltalk":
        return AgentChatResponse(intent=intent, text=_smalltalk_response(request.message), products=[])

    if intent == "image_search":
        image_payload = ImageSearchRequest(
            image_b64=request.image_b64 or "",
            query=request.message,
            filters=None,
            limit=6,
        )
        response = image_search(image_payload)
        text = "Here are products that visually align with your request."
        return AgentChatResponse(intent=intent, text=text, products=response.results)

    recommend_payload = RecommendRequest(goal=combined_message, constraints=None, limit=6)
    response = recommend_products(recommend_payload)
    text = "Here are some options I think you'll like."
    follow_up = None
    if "size" not in request.message.lower():
        follow_up = "Do you have a preferred size?"
    # If no results were found locally, first try the provided web_url (if any)
    if not response.results and getattr(request, "allow_web", False) and getattr(request, "web_url", None):
        fetched = fetch_and_extract(str(request.web_url))
        card = to_product_card(fetched)
        if card:
                # transform to ProductCard pydantic dict shape expected by response
                product_card = {
                    "id": card["id"],
                    "title": card["title"],
                    "image": card.get("image_urls", [None])[0],
                    "price_cents": card.get("price_cents", 0),
                    "currency": card.get("currency", "USD"),
                    "badges": [card.get("brand")] if card.get("brand") else [],
                    "rationale": card.get("description") or card.get("excerpt") or None,
                    "source": "web",
                    "url": fetched.get("url"),
                }
                return AgentChatResponse(intent=intent, text="I found a product on the web that may match:", products=[product_card], follow_up_question=follow_up)

    # If still no results and allow_web is True, run a quick web search (DuckDuckGo fallback)
    if not response.results and getattr(request, "allow_web", False):
        try:
            urls = web_search(request.message, limit=3)
            cards = []
            for u in urls:
                fetched = fetch_and_extract(u)
                card = to_product_card(fetched)
                if card:
                    cards.append({
                        "id": card["id"],
                        "title": card["title"],
                        "image": card.get("image_urls", [None])[0],
                        "price_cents": card.get("price_cents", 0),
                        "currency": card.get("currency", "USD"),
                        "badges": [card.get("brand")] if card.get("brand") else [],
                        "rationale": card.get("description") or card.get("excerpt") or None,
                    })
            if cards:
                # mark web origin and include url
                for i, c in enumerate(cards):
                    c["source"] = "web"
                    # ensure url field preserved
                    try:
                        fetched = fetch_and_extract(urls[i])
                        c["url"] = fetched.get("url") if fetched else urls[i]
                    except Exception:
                        c["url"] = urls[i]
                return AgentChatResponse(intent=intent, text="I found some web results that may match:", products=cards[:6], follow_up_question=follow_up)
        except Exception:
            pass

    # tag local results as 'catalog' so frontend can display a badge
    for p in response.results:
        if isinstance(p, dict):
            p.setdefault("source", "catalog")
    return AgentChatResponse(intent=intent, text=text, products=response.results, follow_up_question=follow_up)