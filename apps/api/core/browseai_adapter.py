from __future__ import annotations

import hashlib
import os
import json
import logging
from pathlib import Path
from typing import List, Optional

import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "web_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path_for_key(key: str) -> Path:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"browseai_{h}.json"


def fetch_from_browseai(extractor_id: str, api_key: str, force: bool = False) -> Optional[List[dict]]:
    """Call Browse.ai extractor run endpoint and return normalized product-like dicts.

    extractor_id: the Browse.ai extractor ID (string)
    api_key: the full API key string
    Returns a list of product-like dicts or None on error.
    """
    if not extractor_id or not api_key:
        logging.warning("browse.ai: missing extractor_id or api_key")
        return None

    cache_path = _cache_path_for_key(extractor_id + api_key)
    if cache_path.exists() and not force:
        try:
            if os.environ.get("BROWSEAI_DEBUG"):
                logging.info("browse.ai cache hit for extractor=%s", extractor_id)
            return json.loads(cache_path.read_text())
        except Exception:
            if os.environ.get("BROWSEAI_DEBUG"):
                logging.exception("browse.ai failed reading cache for extractor=%s", extractor_id)
            pass

    # Build the API call. Browse.ai's API expects the API key in the header
    # and a run endpoint like `https://api.browse.ai/extractors/{id}/runs` or
    # `https://api.browse.ai/extractors/{id}/run` depending on plan. We'll call
    # the documented run endpoint and accept common responses.
    base = "https://api.browse.ai"
    run_url = f"{base}/extractors/{extractor_id}/run"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    debug_enabled = bool(os.environ.get("BROWSEAI_DEBUG"))
    try:
        # Trigger a run
        if debug_enabled:
            logging.info("browse.ai POST %s", run_url)
        resp = requests.post(run_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if debug_enabled:
            logging.info("browse.ai run response top-level keys: %s", list(data.keys()) if isinstance(data, dict) else type(data))

        # The run response may include a `run_id` or immediate `results`.
        results = None
        if isinstance(data, dict):
            results = data.get("results") or data.get("items")
            # Some plans return an immediate `run_id` that you must poll.
            run_id = data.get("run_id") or data.get("id")
            if not results and run_id:
                poll_url = f"{base}/runs/{run_id}"
                # naive polling
                for attempt in range(10):
                    if debug_enabled:
                        logging.info("browse.ai polling (%s) %s", attempt + 1, poll_url)
                    r2 = requests.get(poll_url, headers=headers, timeout=10)
                    if r2.status_code == 200:
                        j = r2.json()
                        if debug_enabled:
                            logging.info("browse.ai poll keys: %s", list(j.keys()) if isinstance(j, dict) else type(j))
                        results = j.get("results") or j.get("items") or j.get("data")
                        if results:
                            break
        elif isinstance(data, list):
            results = data

        if not results:
            logging.warning("browse.ai: no results for extractor %s (keys seen=%s)", extractor_id, list(data.keys()) if isinstance(data, dict) else type(data))
            return None

        normalized = []
        for item in results:
            # Browse.ai returns arbitrary dicts depending on your extractor.
            # We'll map common product fields: title, price, image, url, description
            title = item.get("title") or item.get("name") or item.get("product")
            url = item.get("url") or item.get("link") or item.get("product_url")
            image = item.get("image") or item.get("image_url") or item.get("img")
            desc = item.get("description") or item.get("desc") or item.get("summary")

            # Enhanced price extraction
            price_data = item.get("price_data") or {}
            if isinstance(price_data, dict):
                # If the extractor provides structured price data
                price_cents = price_data.get("current_price_cents", 0)
                currency = price_data.get("currency", "USD")
            else:
                # Fallback to string parsing
                price = item.get("price") or item.get("amount") or item.get("price_text") or item.get("current_price")
                price_cents = 0
                currency = item.get("currency", "USD")
                try:
                    if price:
                        # Handle various price formats
                        price_str = str(price).upper()
                        # Remove currency symbols and commas
                        price_str = price_str.replace("$", "").replace(",", "").replace("USD", "").strip()
                        # Handle ranges like "19.99 - 29.99" by taking the lower price
                        if "-" in price_str:
                            price_str = price_str.split("-")[0].strip()
                        # Convert to cents
                        price_cents = int(float(price_str) * 100)
                except (ValueError, TypeError):
                    # If parsing fails, look for any number in the string
                    import re
                    numbers = re.findall(r'\d+\.?\d*', str(price))
                    if numbers:
                        try:
                            price_cents = int(float(numbers[0]) * 100)
                        except (ValueError, TypeError):
                            price_cents = 0

            nid = "browse_" + hashlib.sha256((url or title or "").encode("utf-8")).hexdigest()[:10]
            normalized.append(
                {
                    "id": nid,
                    "title": title or "Product",
                    "description": desc or "",
                    "brand": item.get("brand"),
                    "category": item.get("category"),
                    "price_cents": price_cents,
                    "currency": currency,
                    "sizes": item.get("sizes") or [],
                    "colors": item.get("colors") or [],
                    "tags": item.get("tags") or ["browseai"],
                    "image_urls": [image] if image else (item.get("images") or []),
                    "rating": item.get("rating"),
                    "num_reviews": item.get("num_reviews"),
                    "in_stock": item.get("in_stock", True),
                    "url": url or "",
                }
            )

        try:
            cache_path.write_text(json.dumps(normalized))
        except Exception:
            if debug_enabled:
                logging.exception("browse.ai failed writing cache %s", cache_path)
        return normalized
    except Exception as exc:
        logging.exception("Error calling browse.ai extractor %s: %s", extractor_id, exc)
        return None
