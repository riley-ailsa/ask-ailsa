#!/usr/bin/env python3
"""
Test PDF enhancement for NIHR grants.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.grant_store import GrantStore
from src.storage.document_store import DocumentStore
from src.storage.fetch_cache import FetchCache
from src.ingest.resource_fetcher import ResourceFetcher
from src.enhance.pdf_enhancer import PDFEnhancer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pdf_enhancement():
    """Test PDF enhancement on a sample NIHR grant."""

    # Initialize stores
    grant_store = GrantStore()
    doc_store = DocumentStore()

    # Get a test NIHR grant - first check all grants then filter
    all_grants = grant_store.list_grants(limit=100)
    nihr_grants = [g for g in all_grants if g.source == 'nihr']

    if not nihr_grants:
        logger.error("No NIHR grants found in database")
        return

    test_grant = nihr_grants[0]
    test_grant_id = test_grant.id

    logger.info(f"Testing with grant: {test_grant.title}")

    # Get existing documents
    existing_docs = doc_store.get_documents_for_grant(test_grant_id)
    base_char_count = sum(len(doc.text) for doc in existing_docs)
    logger.info(f"Existing: {len(existing_docs)} docs, {base_char_count:,} chars")

    # Initialize enhancement components
    cache = FetchCache()
    fetcher = ResourceFetcher(cache)
    enhancer = PDFEnhancer(fetcher)

    # Get resources from grant metadata
    resources = test_grant.metadata.get('resources', [])
    logger.info(f"Found {len(resources)} total resources")

    # Filter PDF resources
    pdf_resources = [r for r in resources if r.get('type') == 'pdf']
    logger.info(f"Found {len(pdf_resources)} PDF resources")

    if pdf_resources:
        for r in pdf_resources[:3]:  # Show first 3
            logger.info(f"  - {r.get('title')}: {r.get('url')}")

    # Enhance with PDFs
    pdf_docs = enhancer.enhance(test_grant_id, resources)

    if pdf_docs:
        logger.info(f"\nSuccessfully added {len(pdf_docs)} PDFs:")
        total_new_chars = 0
        for doc in pdf_docs:
            char_count = len(doc.text)
            total_new_chars += char_count
            logger.info(f"  - {doc.title}: {char_count:,} chars")

        improvement = ((base_char_count + total_new_chars) / base_char_count - 1) * 100 if base_char_count > 0 else 0
        logger.info(f"\nContent increase: {base_char_count:,} → {base_char_count + total_new_chars:,} chars ({improvement:.1f}% increase)")
    else:
        logger.warning("No PDFs were successfully enhanced")

if __name__ == "__main__":
    test_pdf_enhancement()