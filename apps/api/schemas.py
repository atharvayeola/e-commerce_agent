"""Pydantic schemas that mirror the API specification."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Filters(BaseModel):
    category: Optional[str] = None
    brand: Optional[str] = None
    color: Optional[List[str]] = None
    size: Optional[List[str]] = None
    price_min: Optional[int] = Field(default=None, ge=0)
    price_max: Optional[int] = Field(default=None, ge=0)
    in_stock: Optional[bool] = True


class ProductCard(BaseModel):
    id: str
    title: str
    image: Optional[HttpUrl] = None
    price_cents: int
    currency: str = "USD"
    badges: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    filters: Optional[Filters] = None
    limit: int = Field(default=12, ge=1, le=100)


class ImageSearchRequest(BaseModel):
    image_b64: str
    query: Optional[str] = None
    filters: Optional[Filters] = None
    limit: int = Field(default=12, ge=1, le=100)


class RecommendRequest(BaseModel):
    goal: str
    constraints: Optional[Filters] = None
    limit: int = Field(default=8, ge=1, le=50)


class SearchResponse(BaseModel):
    results: List[ProductCard] = Field(default_factory=list)
    debug: dict = Field(default_factory=dict)


class AgentChatRequest(BaseModel):
    message: str
    image_b64: Optional[str] = None
    session_id: Optional[str] = None
    user_context: Optional[dict] = None


class AgentChatResponse(BaseModel):
    intent: str
    text: str
    products: List[ProductCard] = Field(default_factory=list)
    follow_up_question: Optional[str] = None