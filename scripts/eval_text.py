"""Baseline evaluation harness for text recommendations."""

from __future__ import annotations

import json
from pathlib import Path

from apps.api.routers.catalog import search_catalog
from apps.api.schemas import SearchRequest

GOLD_PATH = Path(__file__).resolve().parents[1] / "data" / "golden_queries.json"


def main() -> None:
    if not GOLD_PATH.exists():
        raise SystemExit("Missing golden_queries.json. Populate it before running evaluation.")

    dataset = json.loads(GOLD_PATH.read_text())
    for item in dataset:
        if "query" not in item:
            continue
        request = SearchRequest(query=item["query"], filters=None, limit=5)
        response = search_catalog(request)
        print(f"Query: {item['query']} -> {len(response.results)} results")


if __name__ == "__main__":
    main()