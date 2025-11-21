#!/usr/bin/env python3
"""
Analyze the results of the enhancement process.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from src.storage.grant_store import GrantStore
from src.storage.document_store import DocumentStore

def analyze_enhancement():
    """Comprehensive analysis of enhancement results."""

    print("=" * 80)
    print("ENHANCEMENT RESULTS ANALYSIS")
    print("=" * 80)

    conn = sqlite3.connect("grants.db")
    cursor = conn.cursor()

    # 1. Overall statistics
    print("\n1. OVERALL STATISTICS")
    print("-" * 40)

    # Total grants
    cursor.execute("SELECT COUNT(*) FROM grants WHERE source='nihr'")
    total_grants = cursor.fetchone()[0]
    print(f"Total NIHR grants: {total_grants}")

    # Grants with enhanced content
    cursor.execute("""
        SELECT COUNT(DISTINCT grant_id)
        FROM documents
        WHERE grant_id IN (SELECT id FROM grants WHERE source='nihr')
        AND doc_type IN ('linked_page', 'pdf', 'partner_page')
    """)
    enhanced_grants = cursor.fetchone()[0]
    print(f"Grants with enhanced content: {enhanced_grants}")
    print(f"Enhancement coverage: {enhanced_grants/total_grants*100:.1f}%")

    # 2. Document statistics
    print("\n2. DOCUMENT STATISTICS")
    print("-" * 40)

    # Total documents by type
    cursor.execute("""
        SELECT doc_type, COUNT(*)
        FROM documents
        WHERE grant_id IN (SELECT id FROM grants WHERE source='nihr')
        GROUP BY doc_type
        ORDER BY COUNT(*) DESC
    """)
    doc_types = cursor.fetchall()
    print("Documents by type:")
    for doc_type, count in doc_types:
        print(f"  {doc_type}: {count}")

    # Total and average characters
    cursor.execute("""
        SELECT COUNT(*), SUM(LENGTH(text)), AVG(LENGTH(text))
        FROM documents
        WHERE grant_id IN (SELECT id FROM grants WHERE source='nihr')
    """)
    doc_count, total_chars, avg_chars = cursor.fetchone()
    print(f"\nTotal documents: {doc_count}")
    print(f"Total characters: {total_chars:,}")
    print(f"Average chars per document: {avg_chars:,.0f}")

    # 3. Enhancement impact
    print("\n3. ENHANCEMENT IMPACT")
    print("-" * 40)

    # Compare before and after
    cursor.execute("""
        SELECT
            COUNT(*) as grant_count,
            SUM(base_chars) as total_base,
            SUM(enhanced_chars) as total_enhanced
        FROM (
            SELECT
                grant_id,
                SUM(CASE WHEN doc_type IN ('competition_section', 'nihr_section::overview',
                                          'nihr_section::contact-details')
                    THEN LENGTH(text) ELSE 0 END) as base_chars,
                SUM(CASE WHEN doc_type IN ('linked_page', 'pdf', 'partner_page')
                    THEN LENGTH(text) ELSE 0 END) as enhanced_chars
            FROM documents
            WHERE grant_id IN (SELECT id FROM grants WHERE source='nihr')
            GROUP BY grant_id
            HAVING enhanced_chars > 0
        )
    """)
    result = cursor.fetchone()
    if result:
        grant_count, total_base, total_enhanced = result
        if total_base and total_base > 0:
            improvement = (total_enhanced / total_base) * 100
            print(f"Enhanced grants analyzed: {grant_count}")
            print(f"Base content: {total_base:,} chars")
            print(f"Enhanced content: {total_enhanced:,} chars")
            print(f"Content increase: {improvement:.1f}%")

    # 4. Embeddings coverage
    print("\n4. EMBEDDINGS COVERAGE")
    print("-" * 40)

    cursor.execute("""
        SELECT COUNT(*) FROM embeddings
        WHERE grant_id IN (SELECT id FROM grants WHERE source='nihr')
    """)
    total_embeddings = cursor.fetchone()[0]
    print(f"Total embeddings created: {total_embeddings}")

    cursor.execute("""
        SELECT COUNT(DISTINCT grant_id) FROM embeddings
        WHERE grant_id IN (SELECT id FROM grants WHERE source='nihr')
    """)
    grants_with_embeddings = cursor.fetchone()[0]
    print(f"Grants with embeddings: {grants_with_embeddings}")

    # 5. Top enhanced grants
    print("\n5. TOP ENHANCED GRANTS (by content added)")
    print("-" * 40)

    cursor.execute("""
        SELECT
            g.title,
            COUNT(d.id) as doc_count,
            SUM(LENGTH(d.text)) as total_chars
        FROM grants g
        JOIN documents d ON g.id = d.grant_id
        WHERE g.source = 'nihr'
        AND d.doc_type IN ('linked_page', 'pdf', 'partner_page')
        GROUP BY g.id, g.title
        ORDER BY total_chars DESC
        LIMIT 5
    """)
    top_grants = cursor.fetchall()
    for i, (title, doc_count, total_chars) in enumerate(top_grants, 1):
        print(f"{i}. {title[:60]}...")
        print(f"   Documents: {doc_count}, Characters: {total_chars:,}")

    # 6. Processing statistics
    print("\n6. PROCESSING STATUS")
    print("-" * 40)

    # Check log file for progress
    try:
        with open("enhancement_full_450.log", "r") as f:
            content = f.read()
            processing_count = content.count("[")
            completed_count = content.count("COMPLETE:")
            print(f"Processing attempts: {processing_count}")
            print(f"Successfully completed: {completed_count}")
    except:
        print("Log file not available")

    conn.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    analyze_enhancement()