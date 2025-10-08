"""Baseline evaluation harness for image search."""

from __future__ import annotations

import json
from pathlib import Path

from apps.api.routers.catalog import image_search
from apps.api.schemas import ImageSearchRequest

GOLD_PATH = Path(__file__).resolve().parents[1] / "data" / "golden_queries.json"


def main() -> None:
    if not GOLD_PATH.exists():
        raise SystemExit("Missing golden_queries.json. Populate it before running evaluation.")

    dataset = json.loads(GOLD_PATH.read_text())
    for item in dataset:
        if "image_query" not in item:
            continue
        request = ImageSearchRequest(
            image_b64=item["image_query"],
            query=item.get("query"),
            filters=None,
            limit=5,
        )
        response = image_search(request)
        print(f"Image query: {item['image_query']} -> {len(response.results)} results")


if __name__ == "__main__":
    main()