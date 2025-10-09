from __future__ import annotations

import logging
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def _duckduckgo_search(query: str, limit: int = 3) -> List[str]:
    """Simple DuckDuckGo HTML search scraping for top result URLs.

    Note: this is brittle and meant for quick prototyping only.
    """
    from urllib.parse import unquote, parse_qs

    q = query.replace(" ", "+")
    endpoints = [
        f"https://html.duckduckgo.com/html/?q={q}",
        f"https://duckduckgo.com/html/?q={q}",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = None
        for url in endpoints:
            try:
                resp = requests.get(url, timeout=6, headers=headers)
                if resp.ok and resp.text:
                    break
            except Exception:
                resp = None
        if not resp:
            return []
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        # Try a few known selectors, fall back to redirect handling and any https anchor
        selectors = [
            "a.result__a",
            "a[data-testid='result-title-a']",
            "div.result a",
            "a.result-link",
        ]
        for sel in selectors:
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                # handle DuckDuckGo redirect links like /l/?kh=-1&uddg=<encoded_url>
                if href.startswith("/l/?") or "uddg=" in href:
                    try:
                        qs = parse_qs(href.split("?", 1)[1])
                        if "uddg" in qs:
                            real = unquote(qs["uddg"][0])
                            links.append(real)
                            continue
                    except Exception:
                        pass
                if href.startswith("http"):
                    links.append(href)
                if len(links) >= limit:
                    break
            if len(links) >= limit:
                break

        if len(links) < limit:
            # fallback: collect any https anchors on the page
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and href not in links:
                    links.append(href)
                if len(links) >= limit:
                    break

        # Filter out known ad/redirect patterns that DuckDuckGo returns
        filtered = []
        for href in links:
            if not href:
                continue
            low = href.lower()
            # skip duckduckgo internal resources and JS redirect endpoints
            if "duckduckgo.com/y.js" in low or "duckduckgo.com/l/" in low or "duckduckgo.com/" == low:
                continue
            if "aclick?" in low or "ad_provider" in low or "ad_domain" in low or "devex" in low:
                continue
            if low.startswith("javascript:"):
                continue
            filtered.append(href)
            if len(filtered) >= limit:
                break

        logging.debug("DuckDuckGo search links for '%s' (raw %d, filtered %d): %s", query, len(links), len(filtered), filtered)
        return filtered
    except Exception as exc:
        logging.exception("DuckDuckGo search failed: %s", exc)
        return []


def search(query: str, limit: int = 3) -> List[str]:
    """Public search API: returns a list of candidate URLs for a query.

    Currently uses DuckDuckGo HTML endpoint as a free fallback.
    """
    return _duckduckgo_search(query, limit=limit)
