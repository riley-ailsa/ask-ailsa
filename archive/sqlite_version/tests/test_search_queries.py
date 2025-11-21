#!/usr/bin/env python3
"""
Internal QA search harness for testing queries and inspecting results.

Usage:
    python3 scripts/test_search_queries.py "health economics modelling"
    python3 scripts/test_search_queries.py "AI in healthcare" --top_k 10
"""

import requests
import json
import argparse
from textwrap import indent

API_URL = "http://localhost:8000"


def run_query(query, top_k=5):
    """
    Run a search query and display formatted results.

    Args:
        query: Search query string
        top_k: Number of results to return
    """
    print("=" * 80)
    print(f"QUERY: {query}")
    print("=" * 80)

    try:
        resp = requests.get(
            f"{API_URL}/search",
            params={"query": query, "top_k": top_k, "active_only": False},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        print(f"   Make sure API is running at {API_URL}")
        return

    print(f"Total results: {data['total_results']}\n")

    if not data["results"]:
        print("No results found.")
        return

    for i, hit in enumerate(data["results"], 1):
        print(f"[{i}] {hit['title']} ({hit['grant_id']})")
        print(f"    Score:   {hit['score']:.4f}")
        print(f"    Source:  {hit.get('source', 'N/A')}")
        print(f"    DocType: {hit['doc_type']}")
        print(f"    Scope:   {hit['scope']}")
        print(f"    URL:     {hit['source_url']}")
        print("    Snippet:")
        print(indent(hit['snippet'], "      "))
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test search queries against grant discovery API"
    )
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--top_k", type=int, default=5, help="Number of results")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")

    args = parser.parse_args()
    API_URL = args.api_url

    run_query(args.query, args.top_k)
