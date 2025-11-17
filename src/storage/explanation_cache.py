"""
Cache for GPT-5 explanations.

Stores explanations to avoid duplicate API calls.
"""

import json
import hashlib
import logging
from typing import Optional, Dict, Any

from .db import Database


logger = logging.getLogger(__name__)


class ExplanationCache:
    """
    Cache for GPT-5 search explanations.

    Features:
    - Query-based caching with hash keys
    - Access tracking (count + last access time)
    - TTL/cleanup support
    """

    def __init__(self, db_path: str = "grants.db"):
        """Initialize explanation cache."""
        self.db = Database(db_path)
        logger.info("ExplanationCache initialized")

    def _hash_query(self, query: str, model: str) -> str:
        """
        Generate hash key for query + model.

        Args:
            query: Search query (normalized to lowercase)
            model: Model name

        Returns:
            SHA256 hash
        """
        normalized = query.strip().lower()
        key = f"{normalized}:{model}"
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, query: str, model: str = "gpt-5-mini") -> Optional[Dict[str, Any]]:
        """
        Get cached explanation for query.

        Args:
            query: Search query
            model: Model name

        Returns:
            Dict with explanation and metadata, or None if not cached
        """
        query_hash = self._hash_query(query, model)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT explanation, referenced_grants, created_at, access_count
                FROM explanations
                WHERE query_hash = ?
                """,
                (query_hash,)
            )

            row = cursor.fetchone()

            if not row:
                return None

            # Update access tracking
            cursor.execute(
                """
                UPDATE explanations
                SET accessed_at = CURRENT_TIMESTAMP,
                    access_count = access_count + 1
                WHERE query_hash = ?
                """,
                (query_hash,)
            )

        logger.info(f"Cache HIT: {query} (accessed {row['access_count']} times)")

        return {
            "explanation": row["explanation"],
            "referenced_grants": json.loads(row["referenced_grants"]),
            "created_at": row["created_at"],
            "from_cache": True,
        }

    def set(
        self,
        query: str,
        explanation: str,
        model: str,
        referenced_grants: list,
    ) -> None:
        """
        Store explanation in cache.

        Args:
            query: Search query
            explanation: GPT-5 explanation text
            model: Model name
            referenced_grants: List of referenced grant dicts
        """
        query_hash = self._hash_query(query, model)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO explanations (
                    query_hash, query, explanation, model,
                    referenced_grants, created_at, accessed_at, access_count
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                """,
                (
                    query_hash,
                    query.strip(),
                    explanation,
                    model,
                    json.dumps(referenced_grants),
                ),
            )

        logger.info(f"Cache SET: {query}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM explanations")
            total = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT SUM(access_count) as total FROM explanations"
            )
            total_accesses = cursor.fetchone()["total"] or 0

            cursor.execute(
                "SELECT AVG(access_count) as avg FROM explanations"
            )
            avg_accesses = cursor.fetchone()["avg"] or 0

        return {
            "total_cached": total,
            "total_accesses": total_accesses,
            "avg_accesses": avg_accesses,
        }
