#!/usr/bin/env python3
"""Analyze embedding distribution across sources."""

import sqlite3

conn = sqlite3.connect("grants.db")
conn.row_factory = sqlite3.Row

print("=" * 80)
print("EMBEDDING ANALYSIS")
print("=" * 80)
print()

# 1. Overall stats by source
print("1. OVERALL STATS BY SOURCE")
print("-" * 80)

query = """
SELECT
    g.source,
    COUNT(DISTINCT g.id) as grants,
    COUNT(DISTINCT d.id) as documents,
    (SELECT COUNT(*) FROM embeddings e
     JOIN documents d2 ON e.doc_id = d2.id
     JOIN grants g2 ON d2.grant_id = g2.id
     WHERE g2.source = g.source) as embeddings,
    AVG(LENGTH(d.text)) as avg_doc_length
FROM grants g
LEFT JOIN documents d ON g.id = d.grant_id
WHERE g.source IN ('nihr', 'innovate_uk')
GROUP BY g.source
"""

for row in conn.execute(query):
    print(f"\n{row['source'].upper()}:")
    print(f"  Grants:             {row['grants']:>6,}")
    print(f"  Documents:          {row['documents']:>6,}")
    print(f"  Embeddings:         {row['embeddings']:>6,}")
    print(f"  Docs per grant:     {row['documents']/row['grants']:>6.1f}")
    print(f"  Embeddings per doc: {row['embeddings']/row['documents']:>6.1f}")
    print(f"  Embeddings per grant: {row['embeddings']/row['grants']:>6.1f}")
    print(f"  Avg doc length:     {row['avg_doc_length']:>6,.0f} chars")

# 2. Document distribution
print("\n\n2. DOCUMENT EMBEDDING DISTRIBUTION (NIHR)")
print("-" * 80)

query = """
SELECT
    CASE
        WHEN chunk_count = 0 THEN 'No embeddings'
        WHEN chunk_count BETWEEN 1 AND 2 THEN '1-2 chunks'
        WHEN chunk_count BETWEEN 3 AND 5 THEN '3-5 chunks'
        WHEN chunk_count BETWEEN 6 AND 10 THEN '6-10 chunks'
        WHEN chunk_count BETWEEN 11 AND 20 THEN '11-20 chunks'
        WHEN chunk_count > 20 THEN '20+ chunks'
    END as range,
    COUNT(*) as doc_count,
    CAST(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS DECIMAL(5,1)) as percentage
FROM (
    SELECT
        d.id,
        COUNT(e.id) as chunk_count
    FROM documents d
    JOIN grants g ON d.grant_id = g.id
    LEFT JOIN embeddings e ON d.id = e.doc_id
    WHERE g.source = 'nihr'
    GROUP BY d.id
)
GROUP BY range
ORDER BY
    CASE range
        WHEN 'No embeddings' THEN 0
        WHEN '1-2 chunks' THEN 1
        WHEN '3-5 chunks' THEN 2
        WHEN '6-10 chunks' THEN 3
        WHEN '11-20 chunks' THEN 4
        WHEN '20+ chunks' THEN 5
    END
"""

for row in conn.execute(query):
    print(f"  {row['range']:20s}: {row['doc_count']:>5,} docs ({row['percentage']:>4}%)")

# 3. Sample documents with most/least embeddings
print("\n\n3. SAMPLE NIHR DOCUMENTS")
print("-" * 80)

print("\nDocuments with MOST embeddings:")
query = """
SELECT
    d.id,
    d.doc_type,
    LENGTH(d.text) as text_length,
    COUNT(e.id) as chunks
FROM documents d
JOIN grants g ON d.grant_id = g.id
LEFT JOIN embeddings e ON d.id = e.doc_id
WHERE g.source = 'nihr'
GROUP BY d.id
ORDER BY chunks DESC
LIMIT 5
"""

for row in conn.execute(query):
    print(f"  {row['doc_type']:30s}: {row['chunks']:>3} chunks, {row['text_length']:>7,} chars")

print("\nDocuments with LEAST embeddings:")
query = """
SELECT
    d.id,
    d.doc_type,
    LENGTH(d.text) as text_length,
    COUNT(e.id) as chunks
FROM documents d
JOIN grants g ON d.grant_id = g.id
LEFT JOIN embeddings e ON d.id = e.doc_id
WHERE g.source = 'nihr'
GROUP BY d.id
ORDER BY chunks ASC, text_length DESC
LIMIT 5
"""

for row in conn.execute(query):
    print(f"  {row['doc_type']:30s}: {row['chunks']:>3} chunks, {row['text_length']:>7,} chars")

# 4. Check if all documents have embeddings
print("\n\n4. EMBEDDING COVERAGE")
print("-" * 80)

query = """
SELECT
    g.source,
    COUNT(DISTINCT d.id) as total_docs,
    COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN d.id END) as docs_with_embeddings,
    COUNT(DISTINCT CASE WHEN e.id IS NULL THEN d.id END) as docs_without_embeddings
FROM documents d
JOIN grants g ON d.grant_id = g.id
LEFT JOIN embeddings e ON d.id = e.doc_id
WHERE g.source IN ('nihr', 'innovate_uk')
GROUP BY g.source
"""

for row in conn.execute(query):
    coverage = row['docs_with_embeddings'] / row['total_docs'] * 100 if row['total_docs'] > 0 else 0
    print(f"\n{row['source'].upper()}:")
    print(f"  Total documents:        {row['total_docs']:>6,}")
    print(f"  With embeddings:        {row['docs_with_embeddings']:>6,}")
    print(f"  Without embeddings:     {row['docs_without_embeddings']:>6,}")
    print(f"  Coverage:               {coverage:>5.1f}%")

print("\n" + "=" * 80)

conn.close()
