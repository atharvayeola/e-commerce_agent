"""Stub image embedding generator.

The CLI mirrors the expected interface for integrating CLIP or another visual
embedding model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List


def fake_image_embed(images: List[str]) -> List[List[float]]:
    vectors = []
    for image in images:
        length = len(image)
        vectors.append([float((length + i) % 7) / 7.0 for i in range(4)])
    return vectors


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate embeddings for product images")
    parser.add_argument("input", type=Path, help="Path to JSON with image URLs or base64 blobs")
    parser.add_argument("--output", type=Path, default=Path("image_embeddings.json"))
    args = parser.parse_args()

    rows = json.loads(args.input.read_text())
    vectors = fake_image_embed([row["image"] for row in rows])
    payload = [{"id": row["id"], "embedding": vec} for row, vec in zip(rows, vectors)]
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(payload)} image embeddings to {args.output}")


if __name__ == "__main__":
    main()