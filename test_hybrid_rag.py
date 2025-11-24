#!/usr/bin/env python3
"""
Test script for Hybrid RAG system
Tests Pinecone + PostgreSQL integration
"""

import sys
sys.path.insert(0, '/Users/rileycoleman/grant-analyst-v2')

print("=" * 70)
print("HYBRID RAG SYSTEM TEST")
print("=" * 70)

# Test 1: Import and check components
print("\n1️⃣ Checking Components...")
try:
    from src.api.server import hybrid_search, grant_store, vector_index
    print("   ✓ Imports successful")
    print(f"   ✓ grant_store: {type(grant_store).__name__}")
    print(f"   ✓ vector_index: {type(vector_index).__name__}")
except Exception as e:
    print(f"   ✗ Import error: {e}")
    sys.exit(1)

# Test 2: Check data availability
print("\n2️⃣ Checking Data Availability...")
try:
    pg_count = grant_store.count_grants()
    pc_stats = vector_index.get_index_stats()
    pc_count = pc_stats.get('total_vectors', 0)

    print(f"   ✓ PostgreSQL grants: {pg_count:,}")
    print(f"   ✓ Pinecone vectors: {pc_count:,}")

    if pg_count == 0 or pc_count == 0:
        print("   ⚠️  Warning: No data found!")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# Test 3: Test hybrid_search with different queries
print("\n3️⃣ Testing hybrid_search()...")

test_queries = [
    ("healthcare", 5),
    ("artificial intelligence", 3),
    ("quantum computing", 3),
]

for query_text, num_results in test_queries:
    print(f"\n📍 Query: '{query_text}' (top_k={num_results})")
    try:
        grants = hybrid_search(
            query=query_text,
            top_k=num_results,
            active_only=False
        )

        print(f"   ✓ Found {len(grants)} grants")

        if grants:
            for i, grant in enumerate(grants, 1):
                print(f"\n   {i}. {grant.title[:70]}")
                print(f"      Score: {grant.relevance_score:.3f}")
                print(f"      Source: {grant.source}")
                print(f"      Active: {'Yes' if grant.is_active else 'No'}")
                print(f"      URL: {grant.url[:60]}...")
        else:
            print("   ⚠️  No grants returned")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()

# Test 4: Test with active_only filter
print("\n4️⃣ Testing with active_only=True...")
try:
    grants = hybrid_search(
        query="digital health",
        top_k=3,
        active_only=True
    )

    print(f"   ✓ Found {len(grants)} ACTIVE grants")

    for i, grant in enumerate(grants, 1):
        print(f"   {i}. {grant.title[:60]}")
        print(f"      Active: {grant.is_active}")

except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 5: Test build_grant_context
print("\n5️⃣ Testing build_grant_context()...")
try:
    from src.api.server import build_grant_context

    grants = hybrid_search(query="innovation", top_k=2, active_only=False)

    if grants:
        context = build_grant_context("innovation", grants, verbose=False)
        print(f"   ✓ Context generated ({len(context)} characters)")
        print("\n   Preview:")
        print("   " + context[:300].replace("\n", "\n   ") + "...")
    else:
        print("   ⚠️  No grants to build context from")

except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 70)
print("✅ HYBRID RAG TEST COMPLETE")
print("=" * 70)
print("\nIf all tests passed, your hybrid RAG system is working!")
print("The API endpoint issue is separate - check server logs for that.")
