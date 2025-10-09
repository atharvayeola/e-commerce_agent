from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
try:
    from readability import Document  # optional, speeds extraction when available
except Exception:  # pragma: no cover - optional dependency
    Document = None

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "web_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

import os

# Simple domain allowlist for safety. Expand as needed. Can be overridden via
# WEB_FETCH_ALLOWLIST (comma-separated) or bypassed with WEB_FETCH_ALLOW_ALL=1.
_DEFAULT_ALLOWED = {"amazon.com", "walmart.com", "bestbuy.com"}
env_allow = os.environ.get("WEB_FETCH_ALLOWLIST")
if env_allow:
    ALLOWED_DOMAINS = set([d.strip() for d in env_allow.split(",") if d.strip()])
else:
    ALLOWED_DOMAINS = _DEFAULT_ALLOWED

WEB_FETCH_ALLOW_ALL = os.environ.get("WEB_FETCH_ALLOW_ALL") in ("1", "true", "True")


def _domain_allowed(url: str) -> bool:
    try:
        from urllib.parse import urlparse

        host = urlparse(url).netloc
        if WEB_FETCH_ALLOW_ALL:
            return True
        return any(host.endswith(domain) for domain in ALLOWED_DOMAINS)
    except Exception:
        return False


def _cache_path_for_url(url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.json"


def fetch_and_extract(url: str, max_chars: int = 20000, force: bool = False) -> Optional[dict]:
    """Fetch a URL, extract main article text using readability, and cache the result.

    Returns a dict with keys: url, title, text, excerpt, fetched_at
    """
    if not _domain_allowed(url):
        logging.warning("Blocked fetch attempt to disallowed domain: %s", url)
        return None

    cache_path = _cache_path_for_url(url)
    if cache_path.exists() and not force:
        try:
            data = json.loads(cache_path.read_text())
            return data
        except Exception:
            pass

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        title = ""
        text = ""
        soup = None
        if Document:
            doc = Document(resp.text)
            title = doc.short_title()
            content_html = doc.summary()
            soup = BeautifulSoup(content_html, "html.parser")
            paragraphs = [p.get_text(separator=" ").strip() for p in soup.find_all("p")]
            text = "\n\n".join([p for p in paragraphs if p])
        else:
            # Simple fallback: parse all <p> from the full HTML
            soup = BeautifulSoup(resp.text, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text().strip() if title_tag else ""
            paragraphs = [p.get_text(separator=" ").strip() for p in soup.find_all("p")]
            text = "\n\n".join([p for p in paragraphs if p])

        # Extract OpenGraph metadata and JSON-LD product schema when available
        og = {}
        try:
            og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
            og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "og:description"})
            og_image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
            if og_title and og_title.get("content"):
                og["title"] = og_title.get("content")
            if og_desc and og_desc.get("content"):
                og["description"] = og_desc.get("content")
            if og_image and og_image.get("content"):
                og["image"] = og_image.get("content")
            # twitter fallbacks
            if not og.get("image"):
                timg = soup.find("meta", attrs={"name": "twitter:image"})
                if timg and timg.get("content"):
                    og["image"] = timg.get("content")
        except Exception:
            og = {}

        json_ld = []
        try:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    raw = script.string
                    if not raw:
                        continue
                    parsed = json.loads(raw)
                    # JSON-LD can be a list or an object
                    if isinstance(parsed, list):
                        json_ld.extend(parsed)
                    else:
                        json_ld.append(parsed)
                except Exception:
                    continue
        except Exception:
            json_ld = []
        if len(text) > max_chars:
            text = text[:max_chars]
        data = {
            "url": url,
            "title": title,
            "text": text,
            "excerpt": text[:500],
            "meta": {"og": og, "json_ld": json_ld},
        }
        cache_path.write_text(json.dumps(data))
        return data
    except Exception as exc:
        logging.exception("Error fetching url %s: %s", url, exc)
        return None


def to_product_card(fetched: dict) -> dict:
    """Convert a fetched page record into a minimal product-like dict suitable for returning as a ProductCard.

    The returned dict matches the Product model fields used by the app.
    """
    if not fetched:
        return {}
    title = fetched.get("title") or "Product"
    text = fetched.get("excerpt") or fetched.get("text", "")

    # Prefer OpenGraph values when present
    og = (fetched.get("meta") or {}).get("og") or {}
    json_ld = (fetched.get("meta") or {}).get("json_ld") or []

    og_title = og.get("title")
    og_image = og.get("image")
    og_desc = og.get("description")

    # Try to find a Product schema in JSON-LD
    product_schema = None
    for item in json_ld:
        try:
            typ = item.get("@type") or item.get("type")
            if not typ:
                continue
            if isinstance(typ, list):
                ok = any("Product" in t for t in typ)
            else:
                ok = "Product" in typ
            if ok:
                product_schema = item
                break
        except Exception:
            continue

    brand = None
    image_urls = []
    price_cents = 0
    currency = "USD"
    in_stock = True

    if product_schema:
        brand = product_schema.get("brand") or (product_schema.get("manufacturer") or None)
        # brand can be object or string
        if isinstance(brand, dict):
            brand = brand.get("name")
        image_field = product_schema.get("image")
        if isinstance(image_field, list):
            image_urls = image_field
        elif isinstance(image_field, str):
            image_urls = [image_field]
        offers = product_schema.get("offers")
        if offers:
            if isinstance(offers, list):
                offers = offers[0]
            price = offers.get("price")
            price_currency = offers.get("priceCurrency") or offers.get("currency")
            try:
                price_cents = int(float(price) * 100) if price else 0
                if price_currency:
                    currency = price_currency
            except Exception:
                price_cents = 0
        availability = offers.get("availability") if offers else None
        if availability and "OutOfStock" in str(availability):
            in_stock = False

    # Fallback to OG image/title/description when JSON-LD not present
    if og_title:
        title = og_title
    if og_desc and not text:
        text = og_desc
    if og_image and not image_urls:
        image_urls = [og_image]

    url = fetched.get("url") or ""
    return {
         "id": "web_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:10],
        "title": title,
        "description": text,
        "brand": brand,
        "category": None,
        "price_cents": price_cents,
        "currency": currency,
        "sizes": [],
        "colors": [],
        "tags": ["web-sourced"],
        "image_urls": image_urls,
        "rating": None,
        "num_reviews": None,
        "in_stock": in_stock,
        "url": url,
    }
