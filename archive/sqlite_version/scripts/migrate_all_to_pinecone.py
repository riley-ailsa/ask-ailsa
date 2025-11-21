#!/usr/bin/env python3
"""
Migrate all grants and embeddings from SQLite to Pinecone.

This script:
1. Connects to existing SQLite database (grants.db)
2. Reads all grants, documents, and embeddings
3. Uploads everything to Pinecone vector database
4. Uses existing embeddings (no re-generation needed!)
5. Preserves all metadata and relationships

Database Stats (as of migration):
- 486 grants (450 NIHR + 36 Innovate UK)
- 5,853 documents
- 108,658 embeddings (pre-generated)

Usage:
    python scripts/migrate_all_to_pinecone.py --dry-run  # Preview only
    python scripts/migrate_all_to_pinecone.py            # Full migration
"""

import os
import sys
import json
import pickle
import logging
import argparse
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
from tqdm import tqdm
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    # dotenv not installed, try to load manually
    env_file = project_root / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")

# Pinecone imports
try:
    from pinecone import Pinecone, ServerlessSpec
except ImportError:
    print("ERROR: Pinecone library not installed!")
    print("Install with: pip install pinecone-client")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_to_pinecone.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PineconeMigrator:
    """
    Migrates grants and embeddings from SQLite to Pinecone.
    """

    def __init__(
        self,
        db_path: str,
        pinecone_api_key: str,
        index_name: str = "ailsa-grants",
        dimension: int = 1536,
        metric: str = "cosine",
        cloud: str = "aws",
        region: str = "us-east-1",
        batch_size: int = 100,
    ):
        """
        Initialize migrator.

        Args:
            db_path: Path to SQLite database
            pinecone_api_key: Pinecone API key
            index_name: Name of Pinecone index
            dimension: Embedding dimension (1536 for text-embedding-3-small)
            metric: Distance metric (cosine, euclidean, dotproduct)
            cloud: Cloud provider (aws, gcp, azure)
            region: Cloud region
            batch_size: Vectors to upload per batch
        """
        self.db_path = db_path
        self.index_name = index_name
        self.dimension = dimension
        self.batch_size = batch_size

        # Initialize Pinecone
        logger.info("Initializing Pinecone client...")
        self.pc = Pinecone(api_key=pinecone_api_key)

        # Create or connect to index
        self.index = self._init_index(metric, cloud, region)

        # Connect to SQLite
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

        # Statistics
        self.stats = {
            "grants_read": 0,
            "documents_read": 0,
            "embeddings_read": 0,
            "vectors_uploaded": 0,
            "errors": 0,
            "start_time": datetime.now()
        }

    def _init_index(self, metric: str, cloud: str, region: str):
        """
        Create or connect to Pinecone index.

        Args:
            metric: Distance metric
            cloud: Cloud provider
            region: Cloud region

        Returns:
            Pinecone index object
        """
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]

        if self.index_name not in existing_indexes:
            logger.info(f"Creating new Pinecone index: {self.index_name}")
            logger.info(f"  Dimension: {self.dimension}")
            logger.info(f"  Metric: {metric}")
            logger.info(f"  Cloud: {cloud}/{region}")

            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=metric,
                spec=ServerlessSpec(
                    cloud=cloud,
                    region=region
                )
            )
            logger.info("✓ Index created successfully")
        else:
            logger.info(f"Connecting to existing index: {self.index_name}")

        return self.pc.Index(self.index_name)

    def get_database_stats(self) -> Dict[str, int]:
        """
        Get current database statistics.

        Returns:
            Dict with counts of grants, documents, embeddings
        """
        cursor = self.conn.cursor()

        stats = {}

        # Count grants
        cursor.execute("SELECT COUNT(*) FROM grants")
        stats["total_grants"] = cursor.fetchone()[0]

        # Count grants by source
        cursor.execute("SELECT source, COUNT(*) FROM grants GROUP BY source")
        for row in cursor.fetchall():
            stats[f"grants_{row[0]}"] = row[1]

        # Count documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        stats["total_documents"] = cursor.fetchone()[0]

        # Count embeddings
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        stats["total_embeddings"] = cursor.fetchone()[0]

        return stats

    def read_grants(self) -> List[Dict[str, Any]]:
        """
        Read all grants from SQLite.

        Returns:
            List of grant dictionaries
        """
        logger.info("Reading grants from SQLite...")
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                id, source, external_id, title, url, description,
                opens_at, closes_at, total_fund, total_fund_gbp,
                project_size, funding_rules_json, is_active, tags_json,
                created_at, updated_at
            FROM grants
            ORDER BY source, id
        """)

        grants = []
        for row in cursor.fetchall():
            grant = {
                "id": row["id"],
                "source": row["source"],
                "external_id": row["external_id"],
                "title": row["title"],
                "url": row["url"],
                "description": row["description"] or "",
                "opens_at": row["opens_at"],
                "closes_at": row["closes_at"],
                "total_fund": row["total_fund"],
                "total_fund_gbp": row["total_fund_gbp"],
                "project_size": row["project_size"],
                "funding_rules": json.loads(row["funding_rules_json"] or "{}"),
                "is_active": bool(row["is_active"]),
                "tags": json.loads(row["tags_json"] or "[]"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            grants.append(grant)

        self.stats["grants_read"] = len(grants)
        logger.info(f"✓ Read {len(grants)} grants")

        return grants

    def read_documents(self) -> List[Dict[str, Any]]:
        """
        Read all documents from SQLite.

        Returns:
            List of document dictionaries
        """
        logger.info("Reading documents from SQLite...")
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                id, grant_id, resource_id, doc_type,
                scope, source_url, text, created_at, updated_at
            FROM documents
            ORDER BY grant_id, id
        """)

        documents = []
        for row in cursor.fetchall():
            doc = {
                "id": row["id"],
                "grant_id": row["grant_id"],
                "resource_id": row["resource_id"],
                "doc_type": row["doc_type"],
                "scope": row["scope"],
                "source_url": row["source_url"],
                "text": row["text"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            documents.append(doc)

        self.stats["documents_read"] = len(documents)
        logger.info(f"✓ Read {len(documents)} documents")

        return documents

    def read_embeddings_batch(self, offset: int, limit: int) -> List[Tuple]:
        """
        Read embeddings in batches with enriched grant metadata (memory efficient).

        Args:
            offset: Starting row
            limit: Number of rows to read

        Returns:
            List of tuples: (id, vector, metadata)
        """
        cursor = self.conn.cursor()

        # Join with grants table to get rich metadata
        cursor.execute("""
            SELECT
                e.id, e.doc_id, e.grant_id, e.chunk_index,
                e.vector, e.text, e.source_url, e.doc_type, e.scope,
                g.source, g.title, g.opens_at, g.closes_at,
                g.total_fund, g.total_fund_gbp, g.is_active,
                g.tags_json, g.external_id, g.project_size
            FROM embeddings e
            LEFT JOIN grants g ON e.grant_id = g.id
            ORDER BY e.id
            LIMIT ? OFFSET ?
        """, (limit, offset))

        embeddings = []
        for row in cursor.fetchall():
            # Parse vector from pickle blob
            vector_array = pickle.loads(row["vector"])
            # Convert numpy array to list for Pinecone
            vector = vector_array.tolist()

            # Parse tags
            tags = []
            if row["tags_json"]:
                try:
                    tags = json.loads(row["tags_json"])
                except:
                    pass

            # Build enriched metadata (similar to your EU grants)
            # Pinecone requires all metadata values to be strings, numbers, or booleans (not None)
            metadata = {
                # Vector/document info
                "doc_id": row["doc_id"] or "",
                "grant_id": row["grant_id"] or "",
                "chunk_index": int(row["chunk_index"]) if row["chunk_index"] is not None else 0,
                "text": (row["text"] or "")[:1000],  # Limit text size in metadata
                "source_url": row["source_url"] or "",
                "doc_type": row["doc_type"] or "",
                "scope": row["scope"] or "competition",

                # Grant info (enriched from grants table)
                "source": row["source"] or "",
                "title": (row["title"] or "")[:500],  # Limit title length
                "external_id": row["external_id"] or "",
                "status": "open" if row["is_active"] else "closed",
                "opens_at": row["opens_at"] or "",
                "closes_at": row["closes_at"] or "",
                "total_fund": row["total_fund"] or "",
                "total_fund_gbp": int(row["total_fund_gbp"]) if row["total_fund_gbp"] else 0,
                "project_size": row["project_size"] or "",
                "tags": ",".join(tags[:5]) if tags else "",  # First 5 tags as CSV
            }

            embeddings.append((
                row["id"],
                vector,
                metadata
            ))

        return embeddings

    def upload_vectors_to_pinecone(self, dry_run: bool = False) -> None:
        """
        Upload all embeddings to Pinecone.

        Args:
            dry_run: If True, only preview without uploading
        """
        # Get total count
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        total_embeddings = cursor.fetchone()[0]

        logger.info(f"Uploading {total_embeddings} embeddings to Pinecone...")

        if dry_run:
            logger.info("DRY RUN MODE - No vectors will be uploaded")
            logger.info("")
            # Preview first 3 with full metadata
            embeddings = self.read_embeddings_batch(0, 3)
            for i, (emb_id, vector, metadata) in enumerate(embeddings, 1):
                logger.info(f"Preview {i}: {emb_id}")
                logger.info(f"  Grant ID:      {metadata['grant_id']}")
                logger.info(f"  Source:        {metadata['source']}")
                logger.info(f"  Title:         {metadata['title'][:80]}...")
                logger.info(f"  Status:        {metadata['status']}")
                logger.info(f"  Closes:        {metadata['closes_at']}")
                logger.info(f"  Funding:       {metadata['total_fund']}")
                logger.info(f"  Funding (GBP): £{metadata['total_fund_gbp']:,}" if metadata['total_fund_gbp'] else "  Funding (GBP): N/A")
                logger.info(f"  Tags:          {metadata['tags']}")
                logger.info(f"  Doc Type:      {metadata['doc_type']}")
                logger.info(f"  Scope:         {metadata['scope']}")
                logger.info(f"  Text Preview:  {metadata['text'][:150]}...")
                logger.info(f"  Vector dims:   {len(vector)}")
                logger.info("")
            return

        # Upload in batches
        offset = 0
        with tqdm(total=total_embeddings, desc="Uploading vectors") as pbar:
            while offset < total_embeddings:
                # Read batch
                embeddings = self.read_embeddings_batch(offset, self.batch_size)

                if not embeddings:
                    break

                # Format for Pinecone
                vectors = []
                for emb_id, vector, metadata in embeddings:
                    vectors.append({
                        "id": emb_id,
                        "values": vector,
                        "metadata": metadata
                    })

                # Upload batch
                try:
                    self.index.upsert(vectors=vectors)
                    self.stats["vectors_uploaded"] += len(vectors)
                    pbar.update(len(vectors))

                except Exception as e:
                    logger.error(f"Failed to upload batch at offset {offset}: {e}")
                    self.stats["errors"] += len(vectors)

                offset += self.batch_size

        logger.info(f"✓ Uploaded {self.stats['vectors_uploaded']} vectors to Pinecone")

    def create_metadata_backup(self, grants: List[Dict], documents: List[Dict]) -> None:
        """
        Create JSON backup of all grants and documents metadata.

        Args:
            grants: List of grant dicts
            documents: List of document dicts
        """
        backup_file = f"pinecone_metadata_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        logger.info(f"Creating metadata backup: {backup_file}")

        backup_data = {
            "migration_timestamp": datetime.now().isoformat(),
            "source_database": self.db_path,
            "pinecone_index": self.index_name,
            "statistics": {
                "total_grants": len(grants),
                "total_documents": len(documents),
                "total_embeddings": self.stats["embeddings_read"]
            },
            "grants": grants,
            "documents": documents
        }

        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)

        logger.info(f"✓ Metadata backup saved: {backup_file}")

    def print_summary(self) -> None:
        """Print migration summary."""
        elapsed = (datetime.now() - self.stats["start_time"]).total_seconds()

        logger.info("")
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Pinecone Index: {self.index_name}")
        logger.info("")
        logger.info(f"Grants read:        {self.stats['grants_read']}")
        logger.info(f"Documents read:     {self.stats['documents_read']}")
        logger.info(f"Embeddings read:    {self.stats['embeddings_read']}")
        logger.info(f"Vectors uploaded:   {self.stats['vectors_uploaded']}")
        logger.info(f"Errors:             {self.stats['errors']}")
        logger.info("")
        logger.info(f"Elapsed time:       {elapsed:.1f}s ({elapsed/60:.1f}min)")

        if self.stats["vectors_uploaded"] > 0:
            rate = self.stats["vectors_uploaded"] / elapsed
            logger.info(f"Upload rate:        {rate:.1f} vectors/sec")

        logger.info("=" * 80)

        # Get Pinecone index stats
        try:
            index_stats = self.index.describe_index_stats()
            logger.info("")
            logger.info("PINECONE INDEX STATUS")
            logger.info("=" * 80)
            logger.info(f"Total vectors:      {index_stats.total_vector_count}")
            logger.info(f"Dimension:          {index_stats.dimension}")
            logger.info("=" * 80)
        except Exception as e:
            logger.warning(f"Could not fetch Pinecone stats: {e}")

    def run(self, dry_run: bool = False, skip_backup: bool = False) -> None:
        """
        Run full migration.

        Args:
            dry_run: Preview only, don't upload
            skip_backup: Skip metadata backup
        """
        try:
            # Print database stats
            logger.info("=" * 80)
            logger.info("DATABASE STATISTICS")
            logger.info("=" * 80)
            db_stats = self.get_database_stats()
            for key, value in db_stats.items():
                logger.info(f"{key:30s} {value}")
            logger.info("=" * 80)
            logger.info("")

            # Read all data
            grants = self.read_grants()
            documents = self.read_documents()

            # Get embedding count
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            self.stats["embeddings_read"] = cursor.fetchone()[0]

            # Create metadata backup
            if not skip_backup and not dry_run:
                self.create_metadata_backup(grants, documents)

            # Upload to Pinecone
            self.upload_vectors_to_pinecone(dry_run=dry_run)

            # Print summary
            self.print_summary()

            if dry_run:
                logger.info("")
                logger.info("DRY RUN COMPLETE - No data was uploaded")
                logger.info("Run without --dry-run to perform actual migration")

        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            raise

        finally:
            self.conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate grants and embeddings from SQLite to Pinecone"
    )
    parser.add_argument(
        "--db",
        default="grants.db",
        help="Path to SQLite database (default: grants.db)"
    )
    parser.add_argument(
        "--index-name",
        default="ailsa-grants",
        help="Pinecone index name (default: ailsa-grants)"
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=1536,
        help="Embedding dimension (default: 1536)"
    )
    parser.add_argument(
        "--metric",
        default="cosine",
        choices=["cosine", "euclidean", "dotproduct"],
        help="Distance metric (default: cosine)"
    )
    parser.add_argument(
        "--cloud",
        default="aws",
        choices=["aws", "gcp", "azure"],
        help="Cloud provider (default: aws)"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="Cloud region (default: us-east-1)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Vectors per upload batch (default: 100)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without uploading"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip metadata backup file creation"
    )
    parser.add_argument(
        "--pinecone-api-key",
        help="Pinecone API key (or set PINECONE_API_KEY env var)"
    )

    args = parser.parse_args()

    # Get Pinecone API key
    pinecone_api_key = args.pinecone_api_key or os.getenv("PINECONE_API_KEY")
    if not pinecone_api_key:
        logger.error("Pinecone API key not provided!")
        logger.error("Set PINECONE_API_KEY env var or use --pinecone-api-key flag")
        return 1

    # Verify database exists
    if not Path(args.db).exists():
        logger.error(f"Database not found: {args.db}")
        return 1

    # Create migrator
    migrator = PineconeMigrator(
        db_path=args.db,
        pinecone_api_key=pinecone_api_key,
        index_name=args.index_name,
        dimension=args.dimension,
        metric=args.metric,
        cloud=args.cloud,
        region=args.region,
        batch_size=args.batch_size,
    )

    # Run migration
    migrator.run(dry_run=args.dry_run, skip_backup=args.skip_backup)

    return 0


if __name__ == "__main__":
    sys.exit(main())
