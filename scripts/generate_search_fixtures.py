#!/usr/bin/env python3
"""
Generate pre-computed embedding fixtures for E2E search tests.

Part of AMA-432: Semantic Search Endpoint

Run once (or whenever the embedding model changes) to populate
tests/e2e/fixtures/search_embeddings.json with real embedding vectors.

Usage:
    OPENAI_API_KEY=sk-... python scripts/generate_search_fixtures.py

Requires:
    pip install openai
"""

import json
import sys
from pathlib import Path

from openai import OpenAI

FIXTURES_PATH = Path(__file__).resolve().parents[1] / "tests" / "e2e" / "fixtures" / "search_embeddings.json"
MODEL = "text-embedding-3-small"


def main():
    client = OpenAI()

    with open(FIXTURES_PATH) as f:
        fixtures = json.load(f)

    print(f"Generating embeddings for {len(fixtures)} fixtures using {MODEL}...")

    for i, w in enumerate(fixtures):
        text = f"{w['title']} {w['description']}"
        response = client.embeddings.create(input=text, model=MODEL)
        w["embedding"] = response.data[0].embedding
        # Remove internal-only note if present
        w.pop("_note", None)
        print(f"  [{i + 1}/{len(fixtures)}] {w['title']} -> {len(w['embedding'])} dims")

    with open(FIXTURES_PATH, "w") as f:
        json.dump(fixtures, f, indent=2)

    print(f"Wrote {FIXTURES_PATH}")


if __name__ == "__main__":
    main()
