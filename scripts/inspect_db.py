#!/usr/bin/env python3
"""
Database inspection and validation tool.

Usage:
    python scripts/inspect_db.py
    python scripts/inspect_db.py --db grants.db --verbose
"""

import argparse
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseInspector:
    """
    Inspect and validate SQLite database contents.

    Features:
    - Table statistics (row counts)
    - Grant statistics (total, active, by source)
    - Document statistics (by type, by scope)
    - Embedding statistics (total, avg per grant)
    - Data quality checks (orphans, missing relationships)
    - Database size calculation
    """

    def __init__(self, db_path: str):
        """Initialize database inspector."""
        self.db_path = db_path

        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def get_table_stats(self) -> Dict[str, int]:
        """Get row counts for all tables."""
        cursor = self.conn.cursor()

        tables = ["grants", "documents", "embeddings", "explanations"]
        stats = {}

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]

        return stats

    def get_grant_stats(self) -> Dict[str, Any]:
        """Get grant statistics."""
        cursor = self.conn.cursor()

        # Total and active grants
        cursor.execute("SELECT COUNT(*) FROM grants")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM grants WHERE is_active = 1")
        active = cursor.fetchone()[0]

        # Grants by source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM grants
            GROUP BY source
            ORDER BY count DESC
            """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        # Grants with funding info
        cursor.execute(
            "SELECT COUNT(*) FROM grants WHERE total_fund IS NOT NULL AND total_fund != ''"
        )
        with_funding = cursor.fetchone()[0]

        # Grants with deadlines
        cursor.execute(
            "SELECT COUNT(*) FROM grants WHERE closes_at IS NOT NULL"
        )
        with_deadline = cursor.fetchone()[0]

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "by_source": by_source,
            "with_funding_info": with_funding,
            "with_deadline": with_deadline,
        }

    def get_document_stats(self) -> Dict[str, Any]:
        """Get document statistics."""
        cursor = self.conn.cursor()

        # Total documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]

        # Documents by type
        cursor.execute(
            """
            SELECT doc_type, COUNT(*) as count
            FROM documents
            GROUP BY doc_type
            ORDER BY count DESC
            """
        )
        by_type = {row["doc_type"]: row["count"] for row in cursor.fetchall()}

        # Documents by scope
        cursor.execute(
            """
            SELECT scope, COUNT(*) as count
            FROM documents
            GROUP BY scope
            ORDER BY count DESC
            """
        )
        by_scope = {row["scope"]: row["count"] for row in cursor.fetchall()}

        # Average documents per grant
        cursor.execute(
            """
            SELECT AVG(doc_count) as avg_docs
            FROM (
                SELECT grant_id, COUNT(*) as doc_count
                FROM documents
                GROUP BY grant_id
            )
            """
        )
        avg_per_grant = cursor.fetchone()["avg_docs"] or 0

        # Grants with no documents
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM grants g
            LEFT JOIN documents d ON g.id = d.grant_id
            WHERE d.id IS NULL
            """
        )
        grants_without_docs = cursor.fetchone()[0]

        return {
            "total": total,
            "by_type": by_type,
            "by_scope": by_scope,
            "avg_per_grant": round(avg_per_grant, 2),
            "grants_without_docs": grants_without_docs,
        }

    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding statistics."""
        cursor = self.conn.cursor()

        # Total embeddings
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        total = cursor.fetchone()[0]

        # Unique documents embedded
        cursor.execute("SELECT COUNT(DISTINCT doc_id) FROM embeddings")
        unique_docs = cursor.fetchone()[0]

        # Unique grants embedded
        cursor.execute("SELECT COUNT(DISTINCT grant_id) FROM embeddings WHERE grant_id IS NOT NULL")
        unique_grants = cursor.fetchone()[0]

        # Average embeddings per document
        cursor.execute(
            """
            SELECT AVG(chunk_count) as avg_chunks
            FROM (
                SELECT doc_id, COUNT(*) as chunk_count
                FROM embeddings
                GROUP BY doc_id
            )
            """
        )
        avg_per_doc = cursor.fetchone()["avg_chunks"] or 0

        # Average embeddings per grant
        cursor.execute(
            """
            SELECT AVG(chunk_count) as avg_chunks
            FROM (
                SELECT grant_id, COUNT(*) as chunk_count
                FROM embeddings
                WHERE grant_id IS NOT NULL
                GROUP BY grant_id
            )
            """
        )
        avg_per_grant = cursor.fetchone()["avg_chunks"] or 0

        # Documents without embeddings
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM documents d
            LEFT JOIN embeddings e ON d.id = e.doc_id
            WHERE e.id IS NULL
            """
        )
        docs_without_embeddings = cursor.fetchone()[0]

        return {
            "total": total,
            "unique_docs": unique_docs,
            "unique_grants": unique_grants,
            "avg_per_doc": round(avg_per_doc, 2),
            "avg_per_grant": round(avg_per_grant, 2),
            "docs_without_embeddings": docs_without_embeddings,
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get explanation cache statistics."""
        cursor = self.conn.cursor()

        # Total cached queries
        cursor.execute("SELECT COUNT(*) FROM explanations")
        total = cursor.fetchone()[0]

        if total == 0:
            return {
                "total_cached": 0,
                "total_accesses": 0,
                "avg_accesses": 0,
                "by_model": {},
            }

        # Total accesses
        cursor.execute("SELECT SUM(access_count) FROM explanations")
        total_accesses = cursor.fetchone()[0] or 0

        # Average accesses per query
        avg_accesses = total_accesses / total if total > 0 else 0

        # Cached queries by model
        cursor.execute(
            """
            SELECT model, COUNT(*) as count
            FROM explanations
            GROUP BY model
            """
        )
        by_model = {row["model"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_cached": total,
            "total_accesses": total_accesses,
            "avg_accesses": round(avg_accesses, 2),
            "by_model": by_model,
        }

    def get_data_quality_issues(self) -> List[Tuple[str, int, str]]:
        """
        Check for data quality issues.

        Returns:
            List of (issue_type, count, description) tuples
        """
        cursor = self.conn.cursor()
        issues = []

        # Orphaned documents (grant_id not in grants)
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM documents d
            LEFT JOIN grants g ON d.grant_id = g.id
            WHERE g.id IS NULL
            """
        )
        orphaned_docs = cursor.fetchone()[0]
        if orphaned_docs > 0:
            issues.append(("orphaned_documents", orphaned_docs, "Documents referencing non-existent grants"))

        # Orphaned embeddings (grant_id not in grants)
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM embeddings e
            LEFT JOIN grants g ON e.grant_id = g.id
            WHERE e.grant_id IS NOT NULL AND g.id IS NULL
            """
        )
        orphaned_embeddings = cursor.fetchone()[0]
        if orphaned_embeddings > 0:
            issues.append(("orphaned_embeddings", orphaned_embeddings, "Embeddings referencing non-existent grants"))

        # Grants with no title
        cursor.execute("SELECT COUNT(*) FROM grants WHERE title IS NULL OR title = ''")
        no_title = cursor.fetchone()[0]
        if no_title > 0:
            issues.append(("grants_no_title", no_title, "Grants missing title"))

        # Grants with no URL
        cursor.execute("SELECT COUNT(*) FROM grants WHERE url IS NULL OR url = ''")
        no_url = cursor.fetchone()[0]
        if no_url > 0:
            issues.append(("grants_no_url", no_url, "Grants missing URL"))

        # Documents with empty text
        cursor.execute("SELECT COUNT(*) FROM documents WHERE text IS NULL OR text = ''")
        empty_text = cursor.fetchone()[0]
        if empty_text > 0:
            issues.append(("documents_empty_text", empty_text, "Documents with empty text"))

        return issues

    def get_anomalies(self) -> Dict[str, Any]:
        """
        Detect data anomalies that may indicate quality issues.

        Returns:
            Dict with anomaly types and details
        """
        cursor = self.conn.cursor()
        anomalies = {}

        # 1. Suspiciously small funding amounts (<£100k)
        cursor.execute(
            """
            SELECT id, title, total_fund, total_fund_gbp
            FROM grants
            WHERE total_fund_gbp IS NOT NULL
              AND total_fund_gbp < 100000
            ORDER BY total_fund_gbp
            LIMIT 10
            """
        )
        small_amounts = cursor.fetchall()
        if small_amounts:
            anomalies['small_funding'] = [
                {
                    'id': row['id'],
                    'title': row['title'][:50],
                    'raw': row['total_fund'],
                    'parsed': row['total_fund_gbp']
                }
                for row in small_amounts
            ]

        # 2. Active grants with past deadlines
        cursor.execute(
            """
            SELECT id, title, closes_at
            FROM grants
            WHERE closes_at IS NOT NULL
              AND datetime(closes_at) < datetime('now')
              AND is_active = 1
            LIMIT 10
            """
        )
        past_active = cursor.fetchall()
        if past_active:
            anomalies['past_active'] = [
                {
                    'id': row['id'],
                    'title': row['title'][:50],
                    'closes_at': row['closes_at']
                }
                for row in past_active
            ]

        # 3. Unparsed funding amounts
        cursor.execute(
            """
            SELECT id, title, total_fund
            FROM grants
            WHERE total_fund IS NOT NULL
              AND total_fund != ''
              AND total_fund_gbp IS NULL
            LIMIT 10
            """
        )
        unparsed = cursor.fetchall()
        if unparsed:
            anomalies['unparsed_funding'] = [
                {
                    'id': row['id'],
                    'title': row['title'][:50],
                    'raw': row['total_fund']
                }
                for row in unparsed
            ]

        # 4. Titles with "Funding competition" prefix
        cursor.execute(
            """
            SELECT id, title
            FROM grants
            WHERE title LIKE '%Funding competition%'
               OR title LIKE '%funding competition%'
            LIMIT 10
            """
        )
        dirty_titles = cursor.fetchall()
        if dirty_titles:
            anomalies['dirty_titles'] = [
                {
                    'id': row['id'],
                    'title': row['title'][:80]
                }
                for row in dirty_titles
            ]

        return anomalies

    def get_database_size(self) -> Dict[str, Any]:
        """Get database file size information."""
        db_file = Path(self.db_path)
        size_bytes = db_file.stat().st_size

        # Convert to human-readable format
        size_mb = size_bytes / (1024 * 1024)
        size_gb = size_bytes / (1024 * 1024 * 1024)

        if size_gb >= 1:
            size_str = f"{size_gb:.2f} GB"
        else:
            size_str = f"{size_mb:.2f} MB"

        return {
            "bytes": size_bytes,
            "mb": round(size_mb, 2),
            "gb": round(size_gb, 4),
            "human": size_str,
        }

    def get_sample_grants(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample grants for verbose output."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, title, source, is_active, closes_at
            FROM grants
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_sample_documents(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample documents for verbose output."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT id, grant_id, doc_type, scope, LENGTH(text) as text_length
            FROM documents
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        return [dict(row) for row in cursor.fetchall()]

    def print_report(self, verbose: bool = False):
        """Print comprehensive database report."""
        print("=" * 80)
        print("DATABASE INSPECTION REPORT")
        print("=" * 80)
        print(f"Database: {self.db_path}")
        print()

        # Database size
        size_info = self.get_database_size()
        print(f"📦 Database Size: {size_info['human']}")
        print()

        # Table statistics
        print("📊 TABLE STATISTICS")
        print("-" * 80)
        table_stats = self.get_table_stats()
        for table, count in table_stats.items():
            print(f"  {table:20} {count:>10,} rows")
        print()

        # Grant statistics
        print("🎯 GRANT STATISTICS")
        print("-" * 80)
        grant_stats = self.get_grant_stats()
        print(f"  Total grants:        {grant_stats['total']:>10,}")
        print(f"  Active:              {grant_stats['active']:>10,}")
        print(f"  Inactive:            {grant_stats['inactive']:>10,}")
        print(f"  With funding info:   {grant_stats['with_funding_info']:>10,}")
        print(f"  With deadline:       {grant_stats['with_deadline']:>10,}")
        print()
        print("  By Source:")
        for source, count in grant_stats['by_source'].items():
            print(f"    {source:30} {count:>10,}")
        print()

        # Document statistics
        print("📄 DOCUMENT STATISTICS")
        print("-" * 80)
        doc_stats = self.get_document_stats()
        print(f"  Total documents:     {doc_stats['total']:>10,}")
        print(f"  Avg per grant:       {doc_stats['avg_per_grant']:>10.2f}")
        print(f"  Grants w/o docs:     {doc_stats['grants_without_docs']:>10,}")
        print()
        print("  By Type:")
        for doc_type, count in doc_stats['by_type'].items():
            print(f"    {doc_type:30} {count:>10,}")
        print()
        print("  By Scope:")
        for scope, count in doc_stats['by_scope'].items():
            print(f"    {scope:30} {count:>10,}")
        print()

        # Embedding statistics
        print("🔢 EMBEDDING STATISTICS")
        print("-" * 80)
        emb_stats = self.get_embedding_stats()
        print(f"  Total embeddings:    {emb_stats['total']:>10,}")
        print(f"  Unique documents:    {emb_stats['unique_docs']:>10,}")
        print(f"  Unique grants:       {emb_stats['unique_grants']:>10,}")
        print(f"  Avg per document:    {emb_stats['avg_per_doc']:>10.2f}")
        print(f"  Avg per grant:       {emb_stats['avg_per_grant']:>10.2f}")
        print(f"  Docs w/o embeddings: {emb_stats['docs_without_embeddings']:>10,}")
        print()

        # Cache statistics
        print("💾 EXPLANATION CACHE STATISTICS")
        print("-" * 80)
        cache_stats = self.get_cache_stats()
        print(f"  Cached queries:      {cache_stats['total_cached']:>10,}")
        print(f"  Total accesses:      {cache_stats['total_accesses']:>10,}")
        print(f"  Avg accesses/query:  {cache_stats['avg_accesses']:>10.2f}")
        if cache_stats['by_model']:
            print()
            print("  By Model:")
            for model, count in cache_stats['by_model'].items():
                print(f"    {model:30} {count:>10,}")
        print()

        # Anomaly detection
        print("🔍 ANOMALY DETECTION")
        print("-" * 80)
        anomalies = self.get_anomalies()

        if not anomalies:
            print("  ✅ No anomalies detected!")
        else:
            # Small funding amounts
            if 'small_funding' in anomalies:
                print(f"\n  ⚠️  Suspiciously small funding amounts (<£100k): {len(anomalies['small_funding'])} found")
                for item in anomalies['small_funding'][:5]:
                    print(f"      • {item['id']}: '{item['raw']}' → £{item['parsed']:,}")
                if len(anomalies['small_funding']) > 5:
                    print(f"      ... and {len(anomalies['small_funding']) - 5} more")

            # Active grants with past deadlines
            if 'past_active' in anomalies:
                print(f"\n  ⚠️  Active grants with past deadlines: {len(anomalies['past_active'])} found")
                for item in anomalies['past_active'][:5]:
                    print(f"      • {item['id']}: Closed {item['closes_at']}")
                if len(anomalies['past_active']) > 5:
                    print(f"      ... and {len(anomalies['past_active']) - 5} more")

            # Unparsed funding amounts
            if 'unparsed_funding' in anomalies:
                print(f"\n  ⚠️  Unparsed funding amounts: {len(anomalies['unparsed_funding'])} found")
                for item in anomalies['unparsed_funding'][:5]:
                    print(f"      • {item['id']}: '{item['raw']}'")
                if len(anomalies['unparsed_funding']) > 5:
                    print(f"      ... and {len(anomalies['unparsed_funding']) - 5} more")

            # Dirty titles
            if 'dirty_titles' in anomalies:
                print(f"\n  ⚠️  Titles with 'Funding competition' prefix: {len(anomalies['dirty_titles'])} found")
                for item in anomalies['dirty_titles'][:3]:
                    print(f"      • {item['id']}: {item['title']}")
                if len(anomalies['dirty_titles']) > 3:
                    print(f"      ... and {len(anomalies['dirty_titles']) - 3} more")

        print()

        # Data quality issues
        print("⚠️  DATA QUALITY CHECKS")
        print("-" * 80)
        issues = self.get_data_quality_issues()
        if issues:
            for issue_type, count, description in issues:
                print(f"  ❌ {description}: {count}")
        else:
            print("  ✅ No data quality issues found")
        print()

        # Verbose output
        if verbose:
            print("🔍 SAMPLE DATA (VERBOSE MODE)")
            print("-" * 80)

            print("Sample Grants (5 most recent):")
            sample_grants = self.get_sample_grants(5)
            for grant in sample_grants:
                print(f"  • {grant['id'][:20]}... | {grant['title'][:50]}")
                print(f"    Source: {grant['source']} | Active: {bool(grant['is_active'])} | Closes: {grant['closes_at']}")
            print()

            print("Sample Documents (5 most recent):")
            sample_docs = self.get_sample_documents(5)
            for doc in sample_docs:
                print(f"  • {doc['id'][:20]}... | Type: {doc['doc_type']} | Scope: {doc['scope']}")
                print(f"    Grant: {doc['grant_id'][:20]}... | Text length: {doc['text_length']:,} chars")
            print()

        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Inspect and validate Grant Discovery database"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="grants.db",
        help="Path to database file (default: grants.db)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed information including sample data"
    )

    args = parser.parse_args()

    try:
        inspector = DatabaseInspector(args.db)
        inspector.print_report(verbose=args.verbose)
        inspector.close()
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Error inspecting database: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
