"""Agent endpoint that routes between smalltalk, text recommendations, and image search.

The real implementation would leverage function calling with an external LLM.
Here we mimic the decision logic with simple keyword checks so the API remains
self-contained while exposing the same contract.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import AgentChatRequest, AgentChatResponse, ImageSearchRequest, RecommendRequest
from .catalog import image_search
from .recommend import recommend_products

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
    intent = _detect_intent(request.message, bool(request.image_b64))

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

    recommend_payload = RecommendRequest(goal=request.message, constraints=None, limit=6)
    response = recommend_products(recommend_payload)
    text = "Here are some options I think you'll like."
    follow_up = None
    if "size" not in request.message.lower():
        follow_up = "Do you have a preferred size?"
    return AgentChatResponse(intent=intent, text=text, products=response.results, follow_up_question=follow_up)