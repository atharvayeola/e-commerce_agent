"""CLI scaffold for catalog ingestion.

This script documents the steps required to load a catalog file and enrich it
with embeddings before inserting into Postgres. The current implementation only
validates and echoes the payload to demonstrate the expected flow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_catalog(path: Path) -> List[Dict[str, Any]]:
    if path.suffix not in {".json", ".csv"}:
        raise ValueError("Catalog must be a JSON or CSV file")

    if path.suffix == ".json":
        return json.loads(path.read_text())

    import csv

    with path.open() as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest catalog into Postgres")
    parser.add_argument("catalog", type=Path, help="Path to catalog JSON/CSV")
    args = parser.parse_args()

    items = load_catalog(args.catalog)
    print(f"Loaded {len(items)} products. Stub implementation—connect to Postgres here.")


if __name__ == "__main__":
    main()