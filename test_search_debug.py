#!/usr/bin/env python3
"""
Debug script to test hybrid search system.
"""

from dotenv import load_dotenv
load_dotenv()

from src.storage.pinecone_index import PineconeVectorIndex
from src.storage.postgres_store import PostgresGrantStore

# Test Pinecone search
print("=" * 80)
print("Testing Pinecone Vector Search")
print("=" * 80)

vector_index = PineconeVectorIndex()
print(f"✓ Connected to Pinecone index: {vector_index.index_name}")

# Test a simple query
query = "NIHR grants for clinical trials"
print(f"\nQuery: {query}")
print("Searching Pinecone...")

results = vector_index.search(query=query, top_k=5)
print(f"Found {len(results)} results from Pinecone\n")

for i, result in enumerate(results[:3], 1):
    print(f"{i}. Grant ID: {result['grant_id']}")
    print(f"   Score: {result['score']:.4f}")
    print(f"   Metadata: {result['metadata']}")
    print()

# Test PostgreSQL fetch
print("=" * 80)
print("Testing PostgreSQL Grant Store")
print("=" * 80)

grant_store = PostgresGrantStore()
print(f"✓ Connected to PostgreSQL")

# Get total grant count
from src.storage.db import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM grants")
count = cursor.fetchone()[0]
print(f"Total grants in database: {count}")
conn.close()

# Test fetching by IDs
if results:
    grant_ids = [r['grant_id'] for r in results[:3]]
    print(f"\nFetching grants by IDs: {grant_ids[:3]}")
    grants = grant_store.get_grants_by_ids(grant_ids)
    print(f"Retrieved {len(grants)} grants from PostgreSQL\n")

    for grant in grants:
        print(f"- {grant.id}: {grant.title[:80]}...")
        print(f"  Source: {grant.source}, Active: {grant.is_active}")
        print()

print("=" * 80)
print("Debug Complete")
print("=" * 80)
