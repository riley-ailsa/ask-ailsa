#!/usr/bin/env python3
"""
Example script showing how to query Pinecone after migration.

This demonstrates:
1. Connecting to Pinecone
2. Creating query embeddings with OpenAI
3. Searching for relevant grants
4. Displaying results with metadata

Usage:
    python scripts/query_pinecone_example.py "quantum computing grants"
"""

import os
import sys
from pinecone import Pinecone
from openai import OpenAI


def query_grants(query_text: str, top_k: int = 5):
    """
    Search for grants using semantic search.

    Args:
        query_text: Natural language query
        top_k: Number of results to return
    """
    # Get API keys
    pinecone_key = os.getenv("PINECONE_API_KEY") or "pcsk_6R6Zuv_JR2YcZgUN58HfuoC1mNGnKgEofzEQQh3fmumQTCas9vZGdLQeAbuQJr9tHJmE5p"
    openai_key = os.getenv("OPENAI_API_KEY")

    if not openai_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        return

    # Initialize clients
    print(f"Searching for: '{query_text}'")
    print("=" * 80)
    print()

    pc = Pinecone(api_key=pinecone_key)
    openai_client = OpenAI(api_key=openai_key)
    index = pc.Index("ailsa-grants")

    # Create query embedding
    print("Generating query embedding...")
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=query_text
    )
    query_embedding = response.data[0].embedding
    print(f"✓ Generated {len(query_embedding)}-dimensional embedding")
    print()

    # Search Pinecone
    print(f"Searching Pinecone for top {top_k} results...")
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    print(f"✓ Found {len(results.matches)} matches")
    print()

    # Display results
    print("RESULTS")
    print("=" * 80)
    for i, match in enumerate(results.matches, 1):
        print(f"\n[{i}] Score: {match.score:.4f}")
        print(f"Grant ID: {match.metadata.get('grant_id', 'N/A')}")
        print(f"Doc Type: {match.metadata.get('doc_type', 'N/A')}")
        print(f"Scope: {match.metadata.get('scope', 'N/A')}")
        print(f"URL: {match.metadata.get('source_url', 'N/A')}")
        print(f"\nText Preview:")
        text = match.metadata.get('text', '')
        print(f"  {text[:300]}{'...' if len(text) > 300 else ''}")
        print("-" * 80)

    print()
    print("=" * 80)
    print(f"Search complete! Found {len(results.matches)} relevant documents")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/query_pinecone_example.py <query>")
        print()
        print("Examples:")
        print('  python scripts/query_pinecone_example.py "quantum computing"')
        print('  python scripts/query_pinecone_example.py "healthcare AI research"')
        print('  python scripts/query_pinecone_example.py "climate change innovation"')
        return

    query = " ".join(sys.argv[1:])
    query_grants(query)


if __name__ == "__main__":
    main()
