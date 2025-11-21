#!/usr/bin/env python3
"""
Check data balance across sources in the database.
"""

import sqlite3
from pathlib import Path

def main():
    db_path = Path("grants.db")

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 1. Check the data balance - grants
    print("=" * 80)
    print("1. GRANT COUNT BY SOURCE")
    print("=" * 80)
    cursor.execute("""
        SELECT source, COUNT(*) as grant_count
        FROM grants
        GROUP BY source
        ORDER BY grant_count DESC
    """)

    for row in cursor.fetchall():
        print(f"  {row[0]:30} {row[1]:>10,}")
    print()

    # 2. Check what's actually in your vector store (indexable_documents)
    print("=" * 80)
    print("2. INDEXABLE DOCUMENTS COUNT BY SOURCE")
    print("=" * 80)

    # Check if indexable_documents table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='indexable_documents'
    """)

    if cursor.fetchone():
        cursor.execute("""
            SELECT source, COUNT(*) as doc_count
            FROM indexable_documents
            GROUP BY source
            ORDER BY doc_count DESC
        """)

        results = cursor.fetchall()
        if results:
            for row in results:
                print(f"  {row[0]:30} {row[1]:>10,}")
        else:
            print("  No indexable documents found")
    else:
        print("  ⚠️  Table 'indexable_documents' does not exist")
        print("  Checking 'documents' table instead...")
        print()

        cursor.execute("""
            SELECT g.source, COUNT(*) as doc_count
            FROM documents d
            JOIN grants g ON d.grant_id = g.id
            GROUP BY g.source
            ORDER BY doc_count DESC
        """)

        for row in cursor.fetchall():
            print(f"  {row[0]:30} {row[1]:>10,}")

    print()

    # 3. Check embeddings by source
    print("=" * 80)
    print("3. EMBEDDINGS COUNT BY SOURCE")
    print("=" * 80)
    cursor.execute("""
        SELECT g.source, COUNT(*) as embedding_count
        FROM embeddings e
        JOIN grants g ON e.grant_id = g.id
        WHERE e.grant_id IS NOT NULL
        GROUP BY g.source
        ORDER BY embedding_count DESC
    """)

    for row in cursor.fetchall():
        print(f"  {row[0]:30} {row[1]:>10,}")
    print()

    conn.close()

if __name__ == "__main__":
    main()
