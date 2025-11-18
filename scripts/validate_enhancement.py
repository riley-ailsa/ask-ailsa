#!/usr/bin/env python3
"""
Validate enhancement quality after processing grants.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.grant_store import GrantStore
from src.storage.document_store import DocumentStore
from src.storage.embedding_store import EmbeddingStore
import sqlite3

def validate_enhancement():
    """Check enhancement quality and statistics."""

    grant_store = GrantStore()
    doc_store = DocumentStore()
    embedding_store = EmbeddingStore()

    # Get sample of enhanced grants
    all_grants = grant_store.list_grants(limit=100)
    nihr_grants = [g for g in all_grants if g.source == 'nihr'][:20]

    print("=" * 60)
    print("ENHANCEMENT VALIDATION REPORT")
    print("=" * 60)

    total_docs = 0
    total_chars = 0
    grants_with_embeddings = 0
    grants_with_links = 0
    grants_with_pdfs = 0

    for grant in nihr_grants:
        docs = doc_store.get_documents_for_grant(grant.id)
        char_count = sum(len(d.text) for d in docs)

        total_docs += len(docs)
        total_chars += char_count

        # Check for different document types
        has_pdfs = any(d.doc_type == 'pdf' for d in docs)
        has_links = any(d.doc_type == 'linked_page' for d in docs)

        if has_pdfs:
            grants_with_pdfs += 1
        if has_links:
            grants_with_links += 1

        # Check if embeddings exist
        conn = sqlite3.connect("grants.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM embeddings WHERE grant_id = ?",
            (grant.id,)
        )
        embedding_count = cursor.fetchone()[0]
        conn.close()

        if embedding_count > 0:
            grants_with_embeddings += 1

    print(f"\nSample Size: {len(nihr_grants)} grants")
    print(f"\nContent Statistics:")
    print(f"  Total documents: {total_docs}")
    print(f"  Total characters: {total_chars:,}")
    print(f"  Avg docs per grant: {total_docs / len(nihr_grants):.1f}")
    print(f"  Avg chars per grant: {total_chars / len(nihr_grants):,.0f}")

    print(f"\nDocument Types:")
    print(f"  Grants with PDFs: {grants_with_pdfs}/{len(nihr_grants)}")
    print(f"  Grants with linked pages: {grants_with_links}/{len(nihr_grants)}")
    print(f"  Grants with embeddings: {grants_with_embeddings}/{len(nihr_grants)}")

    # Sample quality check
    print(f"\nSample Grant Details (first 3):")
    for grant in nihr_grants[:3]:
        docs = doc_store.get_documents_for_grant(grant.id)
        print(f"\n  {grant.title[:50]}...")
        print(f"    Documents: {len(docs)}")
        print(f"    Characters: {sum(len(d.text) for d in docs):,}")

        doc_types = {}
        for doc in docs:
            doc_types[doc.doc_type] = doc_types.get(doc.doc_type, 0) + 1
        for doc_type, count in doc_types.items():
            print(f"    - {doc_type}: {count}")

    print("=" * 60)

if __name__ == "__main__":
    validate_enhancement()