"""Utility helpers for loading the demo product catalog into memory."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field

_POSSIBLE_PATHS = [
    Path(__file__).resolve().parents[3] / "data" / "sample_products.json",
    Path(__file__).resolve().parents[2] / "data" / "sample_products.json",
]


def _find_catalog_path() -> Path:
    for p in _POSSIBLE_PATHS:
        if p.exists():
            return p
    # fall back to the first path which will raise a readable error on access
    return _POSSIBLE_PATHS[0]


CATALOG_PATH = _find_catalog_path()


class Product(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    price_cents: int
    currency: str = "USD"
    sizes: List[str] = Field(default_factory=list)
    colors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    rating: Optional[float] = None
    num_reviews: Optional[int] = None
    in_stock: bool = True


@lru_cache(maxsize=1)
def load_catalog() -> List[Product]:
    data = json.loads(CATALOG_PATH.read_text())
    return [Product(**item) for item in data]


def filter_products(products: Iterable[Product], *, filters: Optional[dict] = None) -> List[Product]:
    if not filters:
        return list(products)

    def match(product: Product) -> bool:
        if filters.get("category") and product.category != filters["category"]:
            return False
        if filters.get("brand") and product.brand != filters["brand"]:
            return False
        if filters.get("in_stock") is False and product.in_stock is False:
            return False
        if filters.get("price_min") and product.price_cents < filters["price_min"]:
            return False
        if filters.get("price_max") and product.price_cents > filters["price_max"]:
            return False
        if filters.get("color"):
            if not set(map(str.lower, filters["color"])) & set(map(str.lower, product.colors)):
                return False
        if filters.get("size"):
            if not set(filters["size"]) & set(product.sizes):
                return False
        return True

    return [product for product in products if match(product)]