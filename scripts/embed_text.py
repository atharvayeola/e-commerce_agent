"""Stub embedding generator for text fields.

Replace the placeholder implementation with a call to your embedding service.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List


def fake_embed(texts: List[str]) -> List[List[float]]:
    return [[float(len(text)) % 1.0 for _ in range(4)] for text in texts]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate embeddings for product text")
    parser.add_argument("input", type=Path, help="Path to JSONL with product text_concat field")
    parser.add_argument("--output", type=Path, default=Path("text_embeddings.json"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line]
    vectors = fake_embed([row["text_concat"] for row in rows])
    payload = [{"id": row["id"], "embedding": vec} for row, vec in zip(rows, vectors)]
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(payload)} text embeddings to {args.output}")


if __name__ == "__main__":
    main()