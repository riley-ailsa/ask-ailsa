#!/usr/bin/env python3
"""
Quick test to verify Pinecone connection and setup.

This script:
1. Tests Pinecone API connection
2. Lists existing indexes
3. Shows index stats if ask-ailsa-grants exists
4. Runs a quick validation

Usage:
    python scripts/test_pinecone_connection.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from pinecone import Pinecone
except ImportError:
    print("❌ Pinecone library not installed!")
    print("Install with: pip install pinecone-client")
    sys.exit(1)


def main():
    print("=" * 80)
    print("PINECONE CONNECTION TEST")
    print("=" * 80)
    print()

    # Get API key
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        api_key = "pcsk_6R6Zuv_JR2YcZgUN58HfuoC1mNGnKgEofzEQQh3fmumQTCas9vZGdLQeAbuQJr9tHJmE5p"
        print("⚠️  PINECONE_API_KEY not in environment, using hardcoded key")
    else:
        print("✓ PINECONE_API_KEY found in environment")
    print()

    # Initialize Pinecone
    print("Connecting to Pinecone...")
    try:
        pc = Pinecone(api_key=api_key)
        print("✓ Connected successfully!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return 1
    print()

    # List indexes
    print("Listing existing indexes...")
    try:
        indexes = pc.list_indexes()
        if not indexes:
            print("  No indexes found")
        else:
            for idx in indexes:
                print(f"  - {idx.name}")
                print(f"    Dimension: {idx.dimension}")
                print(f"    Metric: {idx.metric}")
                print(f"    Host: {idx.host}")
                print()
    except Exception as e:
        print(f"❌ Failed to list indexes: {e}")
        return 1

    # Check if ask-ailsa-grants exists
    index_name = "ask-ailsa-grants"
    existing_names = [idx.name for idx in indexes]

    if index_name in existing_names:
        print(f"Index '{index_name}' already exists!")
        print("Fetching index stats...")
        try:
            index = pc.Index(index_name)
            stats = index.describe_index_stats()
            print(f"  Total vectors: {stats.total_vector_count}")
            print(f"  Dimension: {stats.dimension}")
            print()
            print("⚠️  WARNING: Running migration will ADD to existing vectors")
            print("   Consider deleting the index first if you want a fresh start:")
            print(f"   pc.delete_index('{index_name}')")
        except Exception as e:
            print(f"❌ Failed to get stats: {e}")
    else:
        print(f"Index '{index_name}' does not exist yet")
        print("✓ Migration will create a new index")
    print()

    print("=" * 80)
    print("CONNECTION TEST COMPLETE")
    print("=" * 80)
    print()
    print("Ready to migrate! Run:")
    print("  python scripts/migrate_all_to_pinecone.py --dry-run  # Preview")
    print("  python scripts/migrate_all_to_pinecone.py            # Full migration")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
