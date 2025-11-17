#!/usr/bin/env python3
"""
Delete all NIHR data (grants, documents, embeddings) from database.
Use before re-running backfill_nihr_production.py with fixed scraper.
"""

import argparse
import sqlite3


def main():
    parser = argparse.ArgumentParser(
        description="Reset NIHR data in database (grants, documents, embeddings)"
    )
    parser.add_argument("--db", default="grants.db", help="Path to database file")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required for safety)"
    )
    args = parser.parse_args()

    if not args.confirm:
        print("ERROR: This will delete all NIHR data from the database.")
        print("Use --confirm flag to proceed.")
        print(f"\nCommand: python3 scripts/reset_nihr_data.py --db {args.db} --confirm")
        return 1

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    print(f"Resetting NIHR data in {args.db}...")

    # Count before deletion
    cur.execute("SELECT COUNT(*) FROM grants WHERE source = 'nihr'")
    grant_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM documents
        WHERE grant_id IN (SELECT id FROM grants WHERE source = 'nihr')
    """)
    doc_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM embeddings
        WHERE grant_id IN (SELECT id FROM grants WHERE source = 'nihr')
    """)
    embedding_count = cur.fetchone()[0]

    print(f"\nFound:")
    print(f"  - {grant_count} NIHR grants")
    print(f"  - {doc_count} NIHR documents")
    print(f"  - {embedding_count} NIHR embeddings")

    # Delete embeddings for NIHR grants
    cur.execute("""
        DELETE FROM embeddings
        WHERE grant_id IN (SELECT id FROM grants WHERE source = 'nihr')
    """)
    print(f"\n✓ Deleted {embedding_count} embeddings")

    # Delete documents for NIHR grants
    cur.execute("""
        DELETE FROM documents
        WHERE grant_id IN (SELECT id FROM grants WHERE source = 'nihr')
    """)
    print(f"✓ Deleted {doc_count} documents")

    # Delete NIHR grants
    cur.execute("DELETE FROM grants WHERE source = 'nihr'")
    print(f"✓ Deleted {grant_count} grants")

    conn.commit()
    conn.close()

    print("\n✅ NIHR data successfully wiped.")
    print("You can now re-run the backfill script with fixed scraper.")


if __name__ == "__main__":
    exit(main() or 0)
