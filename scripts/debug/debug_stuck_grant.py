#!/usr/bin/env python3
"""
Debug script to understand why the same grant keeps appearing.
Run this to see the actual search scores and what's being filtered out.
"""

import sys
import os
sys.path.insert(0, '/Users/rileycoleman/grant-analyst-v2')

from src.index.vector_index import VectorIndex
from src.storage.grant_store import GrantStore
from src.api.server import apply_semantic_boost, parse_company_website, extract_url_from_message

def analyze_query(query: str, show_top_n: int = 20):
    """Analyze what happens when you search with a query."""
    
    print("=" * 80)
    print(f"DIAGNOSTIC ANALYSIS: '{query}'")
    print("=" * 80)
    
    # Initialize stores
    vector_index = VectorIndex(db_path="grants.db", use_persistent_storage=True)
    grant_store = GrantStore(db_path="grants.db")
    
    # Check if query contains URL
    url = extract_url_from_message(query)
    if url:
        print(f"\n🌐 URL detected: {url}")
        company_info = parse_company_website(url)
        if company_info:
            print(f"   Sector: {company_info.get('sector', 'unknown')}")
            print(f"   Keywords: {', '.join(company_info['keywords'][:5])}")
            print(f"   TRL estimate: {company_info.get('trl_estimate', 'unknown')}")
        print()
    
    # Perform search
    print(f"\n🔍 Performing vector search (top_k={show_top_n})...")
    hits = vector_index.query(query_text=query, top_k=show_top_n * 2)
    
    # Group by grant and show scores
    from collections import defaultdict
    by_grant = defaultdict(list)
    
    for hit in hits:
        if hit.grant_id:
            by_grant[hit.grant_id].append(hit)
    
    print(f"\n📊 Found {len(by_grant)} unique grants from {len(hits)} document chunks\n")
    
    # Show top grants with scores
    grant_scores = []
    for gid, chunks in by_grant.items():
        grant = grant_store.get_grant(gid)
        if not grant:
            continue
            
        # Get best score
        best_score = max(c.score for c in chunks)
        
        # Apply semantic boosting
        boosted_score = apply_semantic_boost(query, grant.title, best_score)
        
        grant_scores.append({
            'id': gid,
            'title': grant.title,
            'source': grant.source,
            'base_score': best_score,
            'boosted_score': boosted_score,
            'boost_factor': boosted_score / best_score if best_score > 0 else 1.0,
            'status': 'open' if grant.is_active else 'closed',
            'num_chunks': len(chunks)
        })
    
    # Sort by boosted score
    grant_scores.sort(key=lambda x: x['boosted_score'], reverse=True)
    
    # Show results with threshold indicators
    MIN_SCORE_STRONG = 0.65
    MIN_SCORE_WEAK = 0.45
    
    print("TOP GRANTS (with semantic boosting):")
    print("-" * 80)
    
    for i, g in enumerate(grant_scores[:show_top_n], 1):
        # Determine tier
        if g['boosted_score'] >= MIN_SCORE_STRONG:
            tier = "🟢 STRONG"
        elif g['boosted_score'] >= MIN_SCORE_WEAK:
            tier = "🟡 WEAK"
        else:
            tier = "🔴 FILTERED"
        
        boost_pct = (g['boost_factor'] - 1.0) * 100
        
        print(f"{i:2}. {tier} | Score: {g['boosted_score']:.4f} (base: {g['base_score']:.4f}, +{boost_pct:.1f}%)")
        print(f"    {g['title'][:70]}")
        print(f"    Source: {g['source']:15} | Status: {g['status']:6} | Chunks: {g['num_chunks']}")
        print()
    
    # Show statistics
    strong = [g for g in grant_scores if g['boosted_score'] >= MIN_SCORE_STRONG]
    weak = [g for g in grant_scores if MIN_SCORE_WEAK <= g['boosted_score'] < MIN_SCORE_STRONG]
    filtered = [g for g in grant_scores if g['boosted_score'] < MIN_SCORE_WEAK]
    
    print("=" * 80)
    print(f"SUMMARY:")
    print(f"  🟢 Strong matches (≥0.65):  {len(strong):3} grants")
    print(f"  🟡 Weak matches (0.45-0.65): {len(weak):3} grants")
    print(f"  🔴 Filtered out (<0.45):     {len(filtered):3} grants")
    print("=" * 80)
    
    # Show source distribution for strong matches
    if strong:
        print("\nSTRONG MATCHES BY SOURCE:")
        from collections import Counter
        source_counts = Counter(g['source'] for g in strong)
        for source, count in source_counts.most_common():
            print(f"  {source:20} {count:3} grants")
    
    return grant_scores, strong, weak, filtered


if __name__ == "__main__":
    # Test with the user's example
    test_queries = [
        "what would be a good grant for my company to apply for: https://mildtech.co.uk/",
        "AI funding for technology companies",
        "healthcare innovation grants",
    ]
    
    for query in test_queries:
        scores, strong, weak, filtered = analyze_query(query, show_top_n=15)
        print("\n" * 2)
